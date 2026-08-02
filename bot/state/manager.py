import json
import uuid

from bot.observability import increment
from bot.utils.redis_client import redis_client


STATE_VERSION = 1
STATE_PREFIX = "user_state:"
HANDOVER_PREFIX = "handover:"
TTL_SECONDS = 1800
HANDOVER_TTL_SECONDS = 7 * 24 * 60 * 60
MAX_INVALID_ATTEMPTS = 2

DEFAULT_STATE = {
    "state": "idle",
    "state_version": STATE_VERSION,
    "checkout_session_id": None,
    "expected_input": None,
    "invalid_attempts": 0,
}


ALLOWED_TRANSITIONS = {
    "idle": {"awaiting_size", "awaiting_confirmation"},
    "awaiting_size": {"awaiting_confirmation", "idle"},
    "awaiting_confirmation": {"handle_payment_method", "idle"},
    "handle_payment_method": {"handle_verify_payment", "idle"},
    "handle_verify_payment": {"awaiting_customer_email", "idle"},
    "awaiting_customer_email": {"awaiting_customer_name", "repeat_customer_confirm", "idle"},
    "awaiting_customer_name": {"awaiting_customer_address", "idle"},
    "awaiting_customer_address": {"awaiting_customer_phone", "idle"},
    "awaiting_customer_phone": {"idle"},
    "repeat_customer_confirm": {"awaiting_customer_name", "idle"},
}


def _state_key(user_id):
    return f"{STATE_PREFIX}{user_id}"


def new_checkout_state(state_name="awaiting_confirmation", **values):
    return {
        **DEFAULT_STATE,
        "state": state_name,
        "checkout_session_id": values.pop("checkout_session_id", None) or str(uuid.uuid4()),
        **values,
    }


def normalize_state(state_dict):
    state = {**DEFAULT_STATE, **(state_dict or {})}
    if state.get("state_version") != STATE_VERSION:
        return DEFAULT_STATE.copy()
    return state


def get_state(user_id):
    raw = redis_client.get(_state_key(user_id))
    if raw is None:
        return DEFAULT_STATE.copy()
    try:
        return normalize_state(json.loads(raw))
    except (TypeError, ValueError, json.JSONDecodeError):
        return DEFAULT_STATE.copy()


def set_state(user_id, state_dict):
    state = normalize_state(state_dict)
    redis_client.setex(_state_key(user_id), TTL_SECONDS, json.dumps(state))
    return state


def transition_state(user_id, current_state, next_state, expected_input=None, **values):
    current_name = (current_state or {}).get("state", "idle")
    if next_state not in ALLOWED_TRANSITIONS.get(current_name, set()):
        increment("invalid_state_transitions")
        raise ValueError(f"Invalid checkout transition: {current_name} -> {next_state}")
    return set_state(user_id, {
        **(current_state or {}),
        **values,
        "state": next_state,
        "state_version": STATE_VERSION,
        "expected_input": expected_input,
        "invalid_attempts": 0,
    })


def reset_state(user_id):
    redis_client.delete(_state_key(user_id))


def set_handover(sender_id, reason="customer_requested", state=None, summary=None):
    state = normalize_state(state or get_state(sender_id))
    context = {
        "reason": reason,
        "originating_state": state.get("state", "idle"),
        "checkout_session_id": state.get("checkout_session_id"),
        "summary": summary or "Customer needs staff assistance.",
    }
    redis_client.setex(
        HANDOVER_PREFIX + sender_id,
        HANDOVER_TTL_SECONDS,
        json.dumps(context),
    )
    increment("messenger_handovers")
    return context


def get_handover(sender_id):
    raw = redis_client.get(HANDOVER_PREFIX + sender_id)
    if not raw:
        return None
    try:
        return json.loads(raw)
    except (TypeError, ValueError, json.JSONDecodeError):
        return {"reason": "unknown"}


def restore_handover(sender_id, context):
    key = HANDOVER_PREFIX + sender_id
    if context is None:
        redis_client.delete(key)
    else:
        redis_client.setex(key, HANDOVER_TTL_SECONDS, json.dumps(context))


def clear_handover(sender_id, reset=True):
    redis_client.delete(HANDOVER_PREFIX + sender_id)
    if reset:
        reset_state(sender_id)


def is_in_handover(sender_id):
    return redis_client.exists(HANDOVER_PREFIX + sender_id) == 1


def record_invalid_attempt(sender_id, state, reason="unexpected_input"):
    attempts = int((state or {}).get("invalid_attempts") or 0) + 1
    updated = set_state(sender_id, {**state, "invalid_attempts": attempts})
    if attempts >= MAX_INVALID_ATTEMPTS:
        set_handover(
            sender_id,
            reason=reason,
            state=updated,
            summary="Checkout paused after repeated invalid input.",
        )
        return updated, True
    return updated, False
