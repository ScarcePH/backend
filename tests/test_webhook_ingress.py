import hashlib
import hmac
import json
import os
import unittest
from unittest.mock import patch

os.environ.setdefault("APP_SECRET", "webhook-test-secret")
os.environ.setdefault("OPENAI_API_KEY", "test-key")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")

from flask import Flask

from bot import webhook_handler
from db.database import db
from db.models.users import User  # noqa: F401 - registers relationship target
from db.models.messenger_event import MessengerEvent
from task.messenger import TaskEnqueueError


class _Lock:
    def acquire(self, blocking=False):
        return True

    def release(self):
        return None


class WebhookIngressTestCase(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.config.update(
            TESTING=True,
            SQLALCHEMY_DATABASE_URI="sqlite:///:memory:",
            SQLALCHEMY_TRACK_MODIFICATIONS=False,
        )
        db.init_app(self.app)
        self.app.register_blueprint(webhook_handler.bot_bp)
        self.client = self.app.test_client()
        with self.app.app_context():
            MessengerEvent.__table__.create(db.engine)

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            MessengerEvent.__table__.drop(db.engine)

    def post_webhook(self, payload, valid_signature=True):
        body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        secret = os.environ["APP_SECRET"] if valid_signature else "wrong-secret"
        signature = "sha256=" + hmac.new(
            secret.encode("utf-8"), body, hashlib.sha256
        ).hexdigest()
        return self.client.post(
            "/webhook",
            data=body,
            content_type="application/json",
            headers={"X-Hub-Signature-256": signature},
        )

    @staticmethod
    def payload(*events):
        return {"object": "page", "entry": [{"messaging": list(events)}]}

    @staticmethod
    def message(mid, sender="sender-1", text="hello"):
        return {
            "sender": {"id": sender},
            "recipient": {"id": "page-1"},
            "timestamp": 123,
            "message": {"mid": mid, "text": text},
        }

    def test_rejects_invalid_signature(self):
        response = self.post_webhook(
            self.payload(self.message("m-1")), valid_signature=False
        )
        self.assertEqual(response.status_code, 403)

    def test_malformed_json_is_a_client_error(self):
        body = b"not-json"
        signature = "sha256=" + hmac.new(
            os.environ["APP_SECRET"].encode(), body, hashlib.sha256
        ).hexdigest()
        response = self.client.post(
            "/webhook",
            data=body,
            content_type="application/json",
            headers={"X-Hub-Signature-256": signature},
        )
        self.assertEqual(response.status_code, 400)

    def test_records_and_enqueues_every_event_in_batch(self):
        with patch.object(
            webhook_handler, "enqueue_messenger_event", return_value=True
        ) as enqueue:
            response = self.post_webhook(
                self.payload(
                    self.message("m-1", sender="sender-1"),
                    self.message("m-2", sender="sender-2"),
                )
            )

        self.assertEqual(response.status_code, 200)
        with self.app.app_context():
            records = MessengerEvent.query.order_by(MessengerEvent.id).all()
            self.assertEqual([record.event_key for record in records], ["mid:m-1", "mid:m-2"])
            self.assertEqual([record.status for record in records], ["pending", "pending"])
        self.assertEqual(enqueue.call_count, 2)

    def test_duplicate_delivery_reuses_single_durable_event(self):
        payload = self.payload(self.message("same-mid"))
        with patch.object(webhook_handler, "enqueue_messenger_event", return_value=True):
            first = self.post_webhook(payload)
            second = self.post_webhook(payload)

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        with self.app.app_context():
            self.assertEqual(MessengerEvent.query.count(), 1)

    def test_postback_without_mid_has_deterministic_key(self):
        event = {
            "sender": {"id": "sender-1"},
            "recipient": {"id": "page-1"},
            "timestamp": 456,
            "postback": {"payload": "ORDER_CONFIRM"},
        }
        with patch.object(webhook_handler, "enqueue_messenger_event", return_value=True):
            self.post_webhook(self.payload(event))
            self.post_webhook(self.payload(event))
        with self.app.app_context():
            record = MessengerEvent.query.one()
            self.assertTrue(record.event_key.startswith("sha256:"))

    def test_echo_and_unknown_events_are_durably_classified(self):
        echo = self.message("echo-mid")
        echo["message"]["is_echo"] = True
        unknown = {
            "sender": {"id": "sender-2"},
            "recipient": {"id": "page-1"},
            "timestamp": 789,
            "delivery": {"mids": ["delivered-mid"]},
        }
        with patch.object(webhook_handler, "enqueue_messenger_event", return_value=True):
            response = self.post_webhook(self.payload(echo, unknown))

        self.assertEqual(response.status_code, 200)
        with self.app.app_context():
            event_types = {
                record.event_type for record in MessengerEvent.query.order_by(MessengerEvent.id)
            }
            self.assertEqual(event_types, {"echo", "unknown"})

    def test_internal_worker_reports_completed_event(self):
        with patch.object(
            webhook_handler, "cloud_tasks_configured", return_value=False
        ), patch.object(
            webhook_handler, "process_event_record", return_value="completed"
        ) as process:
            response = self.client.post(
                "/internal/tasks/messenger-events", json={"event_id": 42}
            )

        self.assertEqual(response.status_code, 204)
        process.assert_called_once_with(42, force=False)

    def test_sync_fallback_completes_all_events(self):
        with patch.object(
            webhook_handler, "enqueue_messenger_event", return_value=False
        ), patch.object(
            webhook_handler.redis_client, "lock", return_value=_Lock()
        ), patch.object(
            webhook_handler, "get_state", return_value={"state": "idle"}
        ), patch.object(
            webhook_handler, "get_handover", return_value=None
        ), patch.object(webhook_handler, "dispatch_event") as dispatch:
            response = self.post_webhook(
                self.payload(self.message("m-1"), self.message("m-2"))
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(dispatch.call_count, 2)
        with self.app.app_context():
            self.assertEqual(
                {record.status for record in MessengerEvent.query.all()}, {"completed"}
            )

    def test_missing_timestamp_does_not_deadlock_sender_ordering(self):
        first = self.message("m-no-time")
        first.pop("timestamp")
        second = self.message("m-with-time")
        with patch.object(
            webhook_handler, "enqueue_messenger_event", return_value=False
        ), patch.object(
            webhook_handler.redis_client, "lock", return_value=_Lock()
        ), patch.object(
            webhook_handler, "get_state", return_value={"state": "idle"}
        ), patch.object(
            webhook_handler, "get_handover", return_value=None
        ), patch.object(webhook_handler, "dispatch_event") as dispatch:
            response = self.post_webhook(self.payload(first, second))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(dispatch.call_count, 2)

    def test_enqueue_failure_requests_webhook_retry(self):
        with patch.object(
            webhook_handler,
            "enqueue_messenger_event",
            side_effect=TaskEnqueueError("unavailable"),
        ):
            response = self.post_webhook(self.payload(self.message("m-1")))
        self.assertEqual(response.status_code, 503)
        with self.app.app_context():
            self.assertEqual(MessengerEvent.query.one().status, "pending")

    def test_guided_quick_reply_dispatches_stable_payload(self):
        event = {
            "sender": {"id": "sender-1"},
            "message": {
                "text": "Yes, place my order",
                "quick_reply": {"payload": "ORDER_CONFIRM"},
            },
        }
        with patch.object(
            webhook_handler, "is_in_handover", return_value=False
        ), patch.object(webhook_handler, "handle_message") as handle:
            webhook_handler.dispatch_event(event)
        handle.assert_called_once_with("sender-1", "ORDER_CONFIRM")

    def test_cancel_reaches_router_during_handover(self):
        event = {
            "sender": {"id": "sender-1"},
            "message": {
                "text": "Cancel checkout",
                "quick_reply": {"payload": "ORDER_CANCEL"},
            },
        }
        with patch.object(
            webhook_handler, "is_in_handover", return_value=True
        ), patch.object(webhook_handler, "handle_message") as handle:
            webhook_handler.dispatch_event(event)
        handle.assert_called_once_with("sender-1", "ORDER_CANCEL")

    def test_processing_failure_is_retryable_and_records_only_error_class(self):
        with self.app.app_context():
            record = MessengerEvent(
                event_key="mid:failure",
                sender_id="sender-1",
                event_type="message",
                payload=self.message("failure"),
                meta_timestamp=123,
            )
            db.session.add(record)
            db.session.commit()
            event_id = record.id
            with patch.object(
                webhook_handler.redis_client, "lock", return_value=_Lock()
            ), patch.object(
                webhook_handler, "get_state", return_value={"state": "idle"}
            ), patch.object(
                webhook_handler, "get_handover", return_value=None
            ), patch.object(
                webhook_handler, "set_state"
            ) as restore_state, patch.object(
                webhook_handler, "restore_handover"
            ) as restore_handover, patch.object(
                webhook_handler, "dispatch_event", side_effect=RuntimeError("private body")
            ):
                result = webhook_handler.process_event_record(event_id)

            restore_state.assert_called_once_with("sender-1", {"state": "idle"})
            restore_handover.assert_called_once_with("sender-1", None)

            self.assertEqual(result, "failed")
            failed = db.session.get(MessengerEvent, event_id)
            self.assertEqual(failed.status, "failed")
            self.assertEqual(failed.attempts, 1)
            self.assertEqual(failed.last_error, "RuntimeError")


if __name__ == "__main__":
    unittest.main()
