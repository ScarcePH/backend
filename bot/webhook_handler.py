import hashlib
import hmac
import json
import os
import time

from flask import Blueprint, abort, current_app, request

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


bot_bp = Blueprint("bot", __name__)
EVENT_DEDUP_TTL_SECONDS = 24 * 60 * 60
SENDER_LOCK_TIMEOUT_SECONDS = 300


def normalize_event(event):
    """Return a safe, JSON-serializable event or None for malformed entries."""
    if not isinstance(event, dict):
        return None
    sender = event.get("sender")
    if not isinstance(sender, dict) or not sender.get("id"):
        return None

    # A JSON round trip rejects non-serializable objects and breaks references to
    # Flask's request payload before handlers can mutate it.
    try:
        normalized = json.loads(json.dumps(event, separators=(",", ":")))
    except (TypeError, ValueError):
        return None

    normalized["sender"]["id"] = str(normalized["sender"]["id"])
    recipient = normalized.get("recipient")
    if isinstance(recipient, dict) and recipient.get("id") is not None:
        recipient["id"] = str(recipient["id"])
    return normalized


def event_digest(event):
    message = event.get("message") if isinstance(event.get("message"), dict) else {}
    mid = message.get("mid")
    if mid and len(str(mid)) <= 250:
        identity = f"mid:{mid}"
    else:
        identity = json.dumps(event, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(identity.encode("utf-8")).hexdigest()


def _completed_key(digest):
    return f"messenger:event:completed:{digest}"


def _process_event(event):
    """Dispatch one event while holding its sender lock."""
    sender_id = event["sender"]["id"]
    digest = event_digest(event)
    completed_key = _completed_key(digest)
    lock = redis_client.lock(
        f"messenger:sender:{sender_id}",
        timeout=SENDER_LOCK_TIMEOUT_SECONDS,
        blocking_timeout=0,
    )
    acquired = False
    try:
        acquired = lock.acquire(blocking=False)
        if not acquired:
            return "deferred"
        if redis_client.exists(completed_key):
            increment("webhook_duplicates")
            return "completed"

        prior_state = get_state(sender_id)
        prior_handover = get_handover(sender_id)
        started_at = time.monotonic()
        try:
            dispatch_event(event)
        except Exception:
            try:
                set_state(sender_id, prior_state)
                restore_handover(sender_id, prior_handover)
            except Exception as restore_exc:
                current_app.logger.error(
                    "messenger_state_restore_failed error_class=%s",
                    type(restore_exc).__name__,
                )
            raise

        redis_client.setex(completed_key, EVENT_DEDUP_TTL_SECONDS, "1")
        current_app.logger.info(
            "messenger_event_completed duration_ms=%s",
            int((time.monotonic() - started_at) * 1000),
        )
        return "completed"
    finally:
        if acquired:
            try:
                lock.release()
            except Exception as exc:
                current_app.logger.warning(
                    "messenger_sender_lock_release_failed error_class=%s",
                    type(exc).__name__,
                )


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

    failed_senders = set()
    retry_needed = False
    for event in normalized:
        sender_id = event["sender"]["id"]
        if sender_id in failed_senders:
            continue
        try:
            result = _process_event(event)
            if result != "completed":
                retry_needed = True
                failed_senders.add(sender_id)
        except Exception as exc:
            retry_needed = True
            failed_senders.add(sender_id)
            increment("messenger_processing_failures")
            current_app.logger.error(
                "messenger_event_processing_failed error_class=%s",
                type(exc).__name__,
            )

    if retry_needed:
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
