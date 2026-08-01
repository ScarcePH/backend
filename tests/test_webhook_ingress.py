import hashlib
import hmac
import json
import os
import re
import unittest
from unittest.mock import patch

os.environ.setdefault("APP_SECRET", "webhook-test-secret")
os.environ.setdefault("OPENAI_API_KEY", "test-key")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")

from flask import Flask

from bot import webhook_handler


class _Lock:
    def __init__(self, acquired=True):
        self.acquired = acquired
        self.released = False

    def acquire(self, blocking=False):
        return self.acquired

    def release(self):
        self.released = True


class FakeRedis:
    def __init__(self):
        self.values = {}
        self.ttls = {}
        self.lock_results = {}
        self.lock_calls = []

    def lock(self, name, timeout, blocking_timeout):
        self.lock_calls.append((name, timeout, blocking_timeout))
        result = self.lock_results.get(name, True)
        if isinstance(result, list):
            result = result.pop(0)
        return _Lock(result)

    def exists(self, key):
        return int(key in self.values)

    def setex(self, key, ttl, value):
        self.values[key] = value
        self.ttls[key] = ttl


class WebhookIngressTestCase(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.config.update(TESTING=True)
        self.app.register_blueprint(webhook_handler.bot_bp)
        self.client = self.app.test_client()
        self.redis = FakeRedis()
        self.patches = [
            patch.object(webhook_handler, "redis_client", self.redis),
            patch.object(webhook_handler, "get_state", return_value={"state": "idle"}),
            patch.object(webhook_handler, "get_handover", return_value=None),
        ]
        for active_patch in self.patches:
            active_patch.start()

    def tearDown(self):
        for active_patch in reversed(self.patches):
            active_patch.stop()

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

    def test_dispatches_every_valid_batch_event_and_ignores_malformed_entries(self):
        with patch.object(webhook_handler, "dispatch_event") as dispatch:
            response = self.post_webhook(
                {
                    "object": "page",
                    "entry": [
                        {
                            "messaging": [
                                self.message("m-1", sender="sender-1"),
                                "not-an-event",
                                {"message": {"mid": "missing-sender"}},
                                self.message("m-2", sender="sender-2"),
                            ]
                        },
                        {"messaging": "not-a-list"},
                    ],
                }
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [call.args[0]["message"]["mid"] for call in dispatch.call_args_list],
            ["m-1", "m-2"],
        )

    def test_duplicate_delivery_is_skipped_with_hashed_24_hour_key(self):
        payload = self.payload(self.message("private-message-id", text="private body"))
        with patch.object(webhook_handler, "dispatch_event") as dispatch:
            first = self.post_webhook(payload)
            second = self.post_webhook(payload)

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        dispatch.assert_called_once()
        self.assertEqual(len(self.redis.values), 1)
        key = next(iter(self.redis.values))
        self.assertRegex(key, r"^messenger:event:completed:[0-9a-f]{64}$")
        self.assertNotIn("private-message-id", key)
        self.assertNotIn("private body", key)
        self.assertEqual(
            self.redis.ttls[key], webhook_handler.EVENT_DEDUP_TTL_SECONDS
        )

    def test_postback_without_mid_has_deterministic_hashed_identifier(self):
        event = {
            "sender": {"id": "sender-1"},
            "recipient": {"id": "page-1"},
            "timestamp": 456,
            "postback": {"payload": "ORDER_CONFIRM"},
        }
        digest = webhook_handler.event_digest(event)
        self.assertEqual(digest, webhook_handler.event_digest(event))
        self.assertTrue(re.fullmatch(r"[0-9a-f]{64}", digest))
        self.assertNotIn("ORDER_CONFIRM", digest)

    def test_removed_internal_messenger_worker_returns_not_found(self):
        response = self.client.post(
            "/internal/tasks/messenger-events", json={"event_id": 42}
        )
        self.assertEqual(response.status_code, 404)

    def test_lock_failure_requests_retry_but_independent_sender_progresses(self):
        self.redis.lock_results["messenger:sender:sender-1"] = False
        with patch.object(webhook_handler, "dispatch_event") as dispatch:
            response = self.post_webhook(
                self.payload(
                    self.message("m-1", sender="sender-1"),
                    self.message("m-2", sender="sender-2"),
                )
            )

        self.assertEqual(response.status_code, 503)
        dispatch.assert_called_once()
        self.assertEqual(dispatch.call_args.args[0]["sender"]["id"], "sender-2")

    def test_failure_defers_later_same_sender_and_processes_independent_sender(self):
        def fail_first(event):
            if event["message"]["mid"] == "m-1":
                raise RuntimeError("private body")

        with patch.object(
            webhook_handler, "dispatch_event", side_effect=fail_first
        ) as dispatch, patch.object(
            webhook_handler, "set_state"
        ) as restore_state, patch.object(
            webhook_handler, "restore_handover"
        ) as restore_handover:
            response = self.post_webhook(
                self.payload(
                    self.message("m-1", sender="sender-1"),
                    self.message("m-2", sender="sender-1"),
                    self.message("m-3", sender="sender-2"),
                )
            )

        self.assertEqual(response.status_code, 503)
        self.assertEqual(
            [call.args[0]["message"]["mid"] for call in dispatch.call_args_list],
            ["m-1", "m-3"],
        )
        restore_state.assert_called_once_with("sender-1", {"state": "idle"})
        restore_handover.assert_called_once_with("sender-1", None)
        completed_digests = {key.rsplit(":", 1)[-1] for key in self.redis.values}
        self.assertNotIn(
            webhook_handler.event_digest(self.message("m-1", sender="sender-1")),
            completed_digests,
        )

    def test_retry_dispatches_failed_sender_in_order_and_skips_prior_successes(self):
        events = (
            self.message("m-1", sender="sender-1"),
            self.message("m-2", sender="sender-1"),
            self.message("m-3", sender="sender-2"),
        )
        attempted = []

        def fail_once(event):
            mid = event["message"]["mid"]
            attempted.append(mid)
            if mid == "m-1":
                raise RuntimeError("temporary")

        with patch.object(
            webhook_handler, "dispatch_event", side_effect=fail_once
        ), patch.object(webhook_handler, "set_state"), patch.object(
            webhook_handler, "restore_handover"
        ):
            first = self.post_webhook(self.payload(*events))
        self.assertEqual(first.status_code, 503)

        with patch.object(webhook_handler, "dispatch_event") as retry_dispatch:
            second = self.post_webhook(self.payload(*events))

        self.assertEqual(second.status_code, 200)
        self.assertEqual(attempted, ["m-1", "m-3"])
        self.assertEqual(
            [call.args[0]["message"]["mid"] for call in retry_dispatch.call_args_list],
            ["m-1", "m-2"],
        )

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

    def test_postback_dispatches_to_postback_handler(self):
        event = {
            "sender": {"id": "sender-1"},
            "postback": {"payload": "GET_STARTED"},
        }
        with patch.object(
            webhook_handler, "is_in_handover", return_value=False
        ), patch.object(webhook_handler, "handle_postback") as handle:
            webhook_handler.dispatch_event(event)
        handle.assert_called_once_with("sender-1", "GET_STARTED", event)

    def test_text_dispatches_to_message_router(self):
        event = {"sender": {"id": "sender-1"}, "message": {"text": " hello "}}
        with patch.object(
            webhook_handler, "is_in_handover", return_value=False
        ), patch.object(webhook_handler, "handle_message") as handle:
            webhook_handler.dispatch_event(event)
        handle.assert_called_once_with("sender-1", "hello")

    def test_echo_is_ignored(self):
        event = {
            "sender": {"id": "sender-1"},
            "message": {"mid": "echo", "is_echo": True},
        }
        with patch.object(
            webhook_handler, "is_in_handover", return_value=False
        ), patch.object(webhook_handler, "handle_message") as handle:
            webhook_handler.dispatch_event(event)
        handle.assert_not_called()

    def test_payment_image_attachment_dispatches_its_url(self):
        event = {
            "sender": {"id": "sender-1"},
            "message": {
                "attachments": [
                    {"type": "image", "payload": {"url": "https://cdn.example/proof"}}
                ]
            },
        }
        with patch.object(
            webhook_handler, "is_in_handover", return_value=False
        ), patch.object(
            webhook_handler,
            "get_state",
            return_value={"state": "handle_verify_payment"},
        ), patch.object(webhook_handler, "handle_message") as handle:
            webhook_handler.dispatch_event(event)
        handle.assert_called_once_with("sender-1", "https://cdn.example/proof")


if __name__ == "__main__":
    unittest.main()
