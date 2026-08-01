import hashlib
import hmac
import json
import os
import time
from datetime import datetime

from flask import Blueprint, abort, current_app, request
from sqlalchemy import and_, or_
from sqlalchemy.exc import IntegrityError

from bot.core.constants import IMAGE_SENT_MSG
from bot.core.router import handle_message, is_active_checkout_state
from bot.handlers.postback import handle_postback
from bot.observability import increment
from bot.services.carousel_pagination import handle_carousel_postback
from bot.services.messenger import reply
from bot.state.manager import (
    get_handover,
    get_state,
    is_in_handover,
    restore_handover,
    set_handover,
    set_state,
)
from bot.utils.redis_client import redis_client
from db.database import db
from db.models.messenger_event import MessengerEvent
from task.messenger import TaskEnqueueError, cloud_tasks_configured, enqueue_messenger_event


bot_bp = Blueprint("bot", __name__)
MAX_PROCESSING_ATTEMPTS = max(
    1,
    int(os.environ.get("MESSENGER_MAX_PROCESSING_ATTEMPTS", "5")),
)


def _event_type(event):
    message = event.get("message") if isinstance(event.get("message"), dict) else {}
    if isinstance(event.get("postback"), dict):
        return "postback"
    if isinstance(message.get("quick_reply"), dict):
        return "quick_reply"
    if message.get("is_echo"):
        return "echo"
    if "text" in message:
        return "message"
    if isinstance(message.get("attachments"), list):
        return "attachment"
    return "unknown"


def normalize_event(event):
    """Return a safe, JSON-serializable event or None for malformed entries."""
    if not isinstance(event, dict):
        return None
    sender = event.get("sender")
    if not isinstance(sender, dict) or not sender.get("id"):
        return None

    # A JSON round trip rejects non-serializable objects and breaks references to
    # Flask's request payload before it is persisted.
    try:
        normalized = json.loads(json.dumps(event, separators=(",", ":")))
    except (TypeError, ValueError):
        return None

    normalized["sender"]["id"] = str(normalized["sender"]["id"])
    recipient = normalized.get("recipient")
    if isinstance(recipient, dict) and recipient.get("id") is not None:
        recipient["id"] = str(recipient["id"])
    return normalized


def event_key(event):
    message = event.get("message") if isinstance(event.get("message"), dict) else {}
    mid = message.get("mid")
    if mid and len(str(mid)) <= 250:
        return f"mid:{mid}"
    canonical = json.dumps(event, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _record_events(events):
    records = []
    for payload in events:
        key = event_key(payload)
        try:
            meta_timestamp = int(payload.get("timestamp"))
        except (TypeError, ValueError):
            meta_timestamp = None
        record = MessengerEvent(
            event_key=key,
            sender_id=payload["sender"]["id"],
            event_type=_event_type(payload),
            payload=payload,
            meta_timestamp=meta_timestamp,
            status="pending",
            attempts=0,
        )
        try:
            with db.session.begin_nested():
                db.session.add(record)
                db.session.flush()
            records.append(record)
        except IntegrityError:
            increment("webhook_duplicates")
            existing = MessengerEvent.query.filter_by(event_key=key).first()
            if existing is not None:
                records.append(existing)
    db.session.commit()
    return records


@bot_bp.route("/webhook", methods=["POST"])
def webhook():
    verify_signature(request)
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return {"status": "invalid payload"}, 400
    if data.get("object") != "page":
        return {"status": "ignored"}

    normalized = []
    entries = data.get("entry", [])
    if not isinstance(entries, list):
        entries = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        messaging = entry.get("messaging", [])
        if not isinstance(messaging, list):
            continue
        for raw_event in messaging:
            event = normalize_event(raw_event)
            if event is not None:
                normalized.append(event)

    try:
        records = _record_events(normalized)
    except Exception as exc:
        db.session.rollback()
        increment("messenger_processing_failures")
        current_app.logger.error(
            "messenger_event_record_failed error_class=%s", type(exc).__name__
        )
        return {"status": "retry"}, 503

    enqueue_failed = False
    for record in records:
        if record.status == "completed":
            continue
        try:
            enqueued = enqueue_messenger_event(record.id)
            if not enqueued:
                result = process_event_record(record.id)
                enqueue_failed = enqueue_failed or result not in {"completed", "dead_letter"}
        except TaskEnqueueError as exc:
            enqueue_failed = True
            increment("messenger_processing_failures")
            current_app.logger.error(
                "messenger_event_enqueue_failed event_id=%s error_class=%s",
                record.id,
                type(exc.__cause__).__name__ if exc.__cause__ else type(exc).__name__,
            )

    if enqueue_failed:
        return {"status": "retry"}, 503
    return {"status": "ok"}


def dispatch_event(event):
    """Run the existing bot behavior for one normalized Messenger event."""
    sender_id = event["sender"]["id"]
    message = event.get("message") if isinstance(event.get("message"), dict) else {}

    postback = event.get("postback") if isinstance(event.get("postback"), dict) else {}
    quick_reply = message.get("quick_reply")
    action_payload = postback.get("payload")
    if isinstance(quick_reply, dict):
        action_payload = quick_reply.get("payload")
    action = action_payload
    if isinstance(action_payload, str) and action_payload.startswith("{"):
        try:
            action = json.loads(action_payload).get("action")
        except (TypeError, ValueError):
            action = None
    if action is None and isinstance(message.get("text"), str):
        typed_action = message["text"].strip().casefold()
        action = {
            "cancel": "ORDER_CANCEL",
            "❌ no": "ORDER_CANCEL",
            "start over": "CHECKOUT_RESTART",
            "talk to human": "TALK_TO_HUMAN",
            "💬 talk to human": "TALK_TO_HUMAN",
        }.get(typed_action)
    if is_in_handover(sender_id) and action not in {
        "ORDER_CANCEL",
        "CHECKOUT_RESTART",
        "TALK_TO_HUMAN",
        "GET_STARTED",
    }:
        return

    if "postback" in event:
        handle_postback(sender_id, postback.get("payload"), event)
        return

    if isinstance(quick_reply, dict):
        payload = quick_reply.get("payload", "")
        if not isinstance(payload, str):
            payload = ""
        if "PAGE" in payload or "available pairs" in payload.lower():
            state = get_state(sender_id)
            if is_active_checkout_state(state.get("state")):
                reply(
                    sender_id,
                    "Please finish your current checkout first, or tap Talk to Human if you need help.",
                    None,
                )
                return
            handle_carousel_postback(sender_id, payload)
            return
        if payload:
            # Stable quick-reply actions, rather than their localized display
            # labels, drive the guided state machine.
            handle_message(sender_id, payload)
            return

    app_id = str(message.get("app_id"))
    page_app_id = os.environ.get("PAGE_APP_ID")
    if page_app_id and app_id == str(page_app_id) and "text" in message:
        recipient = event.get("recipient") or {}
        if recipient.get("id"):
            set_handover(str(recipient["id"]))
        return

    if message.get("is_echo") or not message:
        return
    if "text" in message:
        handle_message(sender_id, str(message["text"]).strip())
        return

    for attachment in message.get("attachments", []):
        if not isinstance(attachment, dict) or attachment.get("type") != "image":
            continue
        state = get_state(sender_id)
        if state.get("state") == "handle_verify_payment":
            payload = attachment.get("payload") or {}
            if payload.get("url"):
                handle_message(sender_id, payload["url"])
                return
        reply(sender_id, IMAGE_SENT_MSG)
        return


def process_event_record(event_id, force=False):
    record = db.session.get(MessengerEvent, event_id)
    if record is None:
        return "missing"
    if record.status == "completed":
        return "completed"
    if record.status == "dead_letter" and not force:
        return "dead_letter"
    if force and record.status == "dead_letter":
        record.status = "pending"
        record.attempts = 0
        record.last_error = None
        db.session.commit()

    lock = redis_client.lock(
        f"messenger:sender:{record.sender_id}", timeout=300, blocking_timeout=0
    )
    acquired = False
    try:
        acquired = lock.acquire(blocking=False)
        if not acquired:
            return "deferred"

        if record.meta_timestamp is None:
            earlier_order = MessengerEvent.id < record.id
        else:
            earlier_order = or_(
                MessengerEvent.meta_timestamp < record.meta_timestamp,
                and_(
                    MessengerEvent.meta_timestamp == record.meta_timestamp,
                    MessengerEvent.id < record.id,
                ),
                and_(
                    MessengerEvent.meta_timestamp.is_(None),
                    MessengerEvent.id < record.id,
                ),
            )
        earlier = MessengerEvent.query.filter(
            MessengerEvent.sender_id == record.sender_id,
            MessengerEvent.id != record.id,
            MessengerEvent.status.notin_(("completed", "dead_letter")),
            earlier_order,
        ).first()
        if earlier is not None:
            return "deferred"

        record.status = "processing"
        record.attempts = (record.attempts or 0) + 1
        record.last_error = None
        db.session.commit()
        started_at = time.monotonic()
        prior_state = get_state(record.sender_id)
        prior_handover = get_handover(record.sender_id)
        try:
            dispatch_event(record.payload)
        except Exception as exc:
            # Handlers persist state before sending controls. Restore the event's
            # starting point so a Cloud Tasks retry replays the same transition.
            try:
                set_state(record.sender_id, prior_state)
                restore_handover(record.sender_id, prior_handover)
            except Exception as restore_exc:
                current_app.logger.error(
                    "messenger_state_restore_failed event_id=%s error_class=%s",
                    record.id,
                    type(restore_exc).__name__,
                )
            increment("messenger_processing_failures")
            record.status = (
                "dead_letter"
                if record.attempts >= MAX_PROCESSING_ATTEMPTS
                else "failed"
            )
            record.last_error = type(exc).__name__
            db.session.commit()
            current_app.logger.error(
                "messenger_event_processing_failed event_id=%s error_class=%s",
                record.id,
                type(exc).__name__,
            )
            return record.status

        record.status = "completed"
        record.processed_at = datetime.utcnow()
        record.last_error = None
        db.session.commit()
        current_app.logger.info(
            "messenger_event_completed event_id=%s event_type=%s duration_ms=%s",
            record.id,
            record.event_type,
            int((time.monotonic() - started_at) * 1000),
        )
        return "completed"
    finally:
        if acquired:
            lock.release()


def _verify_worker_request():
    if not cloud_tasks_configured():
        return bool(current_app.testing)
    authorization = request.headers.get("Authorization", "")
    if not authorization.startswith("Bearer "):
        return False
    try:
        from google.auth.transport.requests import Request as GoogleRequest
        from google.oauth2 import id_token

        claims = id_token.verify_oauth2_token(
            authorization.removeprefix("Bearer "),
            GoogleRequest(),
            audience=os.environ.get(
                "MESSENGER_TASK_AUDIENCE", os.environ["MESSENGER_WORKER_URL"]
            ),
        )
        return claims.get("email") == os.environ["TASKS_SERVICE_ACCOUNT_EMAIL"]
    except Exception:
        return False


@bot_bp.route("/internal/tasks/messenger-events", methods=["POST"])
def messenger_event_worker():
    if not _verify_worker_request():
        abort(401)
    payload = request.get_json(silent=True) or {}
    event_id = payload.get("event_id")
    if not isinstance(event_id, int) or isinstance(event_id, bool):
        return {"status": "invalid payload"}, 400
    result = process_event_record(event_id, force=payload.get("force") is True)
    if result in {"completed", "dead_letter"}:
        return "", 204
    if result in {"deferred", "failed"}:
        return {"status": result}, 503
    return {"status": "not found"}, 404


@bot_bp.route("/webhook", methods=["GET"])
def verify():
    if request.args.get("hub.verify_token") == os.environ.get("VERIFY_TOKEN"):
        return request.args.get("hub.challenge")
    return "Verification failed", 403


def verify_signature(req):
    signature = req.headers.get("X-Hub-Signature-256")
    app_secret = os.environ.get("APP_SECRET")
    if not signature or not app_secret:
        abort(403)
    expected = "sha256=" + hmac.new(
        app_secret.encode("utf-8"), req.get_data(), hashlib.sha256
    ).hexdigest()
    if not hmac.compare_digest(expected, signature):
        abort(403)
