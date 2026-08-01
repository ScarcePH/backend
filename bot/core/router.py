from bot.handlers import (
    idle,
    awaiting_size,
    awaiting_confirmation,
    handle_payment_method,
    verify_payment,
    awaiting_customer_email,
    awaiting_customer_name,
    awaiting_customer_address,
    awaiting_customer_phone,
    repeat_customer_confirm
    
)
from bot.services.nlp import get_auto_reply
from bot.services.messenger import reply
from bot.state.manager import clear_handover, get_state, reset_state, set_handover
from bot.core.constants import ERROR_MSG
from bot.observability import increment

STATE_HANDLERS = {
    "idle": idle,
    "awaiting_size": awaiting_size,
    "awaiting_confirmation": awaiting_confirmation,
    "handle_payment_method": handle_payment_method,
    "handle_verify_payment": verify_payment,
    "awaiting_customer_email": awaiting_customer_email,
    "awaiting_customer_name": awaiting_customer_name,
    "awaiting_customer_address": awaiting_customer_address,
    "awaiting_customer_phone": awaiting_customer_phone,
    "repeat_customer_confirm": repeat_customer_confirm
}

ACTIVE_CHECKOUT_STATES = {
    "awaiting_confirmation",
    "handle_payment_method",
    "handle_verify_payment",
    "awaiting_customer_email",
    "awaiting_customer_name",
    "awaiting_customer_address",
    "awaiting_customer_phone",
    "repeat_customer_confirm",
}


def is_active_checkout_state(state_name):
    return state_name in ACTIVE_CHECKOUT_STATES


def handle_message(sender_id, chat):
    state = get_state(sender_id)
    current = state.get("state", "idle")

    action = str(chat or "").strip()
    normalized = action.casefold()
    if action == "ORDER_CANCEL" or normalized in {"cancel", "❌ no"}:
        if is_active_checkout_state(current):
            increment("abandoned_checkouts")
            checkout_id = state.get("checkout_session_id")
            if checkout_id:
                from db.repository.checkout import abandon_checkout_session

                result, status = abandon_checkout_session(checkout_id)
                if status == 409:
                    return reply(sender_id, result["message"] + ". Please talk to our team for help.", None)
        reset_state(sender_id)
        reply(sender_id, "Checkout cancelled. Tell me the pair and US size whenever you're ready.")
        return "ok", 200
    if action == "CHECKOUT_RESTART" or normalized == "start over":
        if is_active_checkout_state(current):
            increment("abandoned_checkouts")
            checkout_id = state.get("checkout_session_id")
            if checkout_id:
                from db.repository.checkout import abandon_checkout_session

                result, status = abandon_checkout_session(
                    checkout_id,
                    reason="Customer restarted checkout",
                )
                if status == 409:
                    return reply(sender_id, result["message"] + ". Please talk to our team for help.", None)
        clear_handover(sender_id)
        reply(sender_id, "Let's start over. What pair and US size are you looking for?")
        return "ok", 200
    if action == "TALK_TO_HUMAN" or "talk to human" in normalized:
        set_handover(
            sender_id,
            reason="customer_requested",
            state=state,
            summary="Customer requested a person during checkout.",
        )
        reply(sender_id, "Your checkout is saved. A member of our team will reply here shortly.", None)
        return "ok", 200

    chat_lower = action.lower() if current != "handle_verify_payment" else action

    # Checkout is deterministic: GPT/FAQ classification is only used while idle.
    if not is_active_checkout_state(current):
        auto = get_auto_reply(chat_lower, sender_id, state)
        if auto:
            reply(sender_id, auto)
            return "ok",200

    handler = STATE_HANDLERS.get(current)
    if handler:
        handler(sender_id, chat_lower, state)
        return "ok",200

    reset_state(sender_id)
    reply(sender_id, f"{ERROR_MSG} You can tell me the pair and US size to start again.")
    return "ok",200
