from bot.handlers import (
    idle,
    awaiting_size,
    awaiting_confirmation,
    handle_payment_method,
    verify_payment,
    awaiting_customer_name,
    awaiting_customer_address,
    awaiting_customer_phone,
    repeat_customer_confirm
    
)
from bot.services.nlp import get_auto_reply
from bot.services.messenger import reply
from bot.state.manager import get_state
from bot.core.constants import ERROR_MSG

STATE_HANDLERS = {
    "idle": idle,
    "awaiting_size": awaiting_size,
    "awaiting_confirmation": awaiting_confirmation,
    "handle_payment_method": handle_payment_method,
    "handle_verify_payment": verify_payment,
    "awaiting_customer_name": awaiting_customer_name,
    "awaiting_customer_address": awaiting_customer_address,
    "awaiting_customer_phone": awaiting_customer_phone,
    "repeat_customer_confirm": repeat_customer_confirm
}

def handle_message(sender_id, chat):
    state = get_state(sender_id)
    current = state.get("state", "idle")

    chat_lower = chat.lower() if current != "handle_verify_payment" else chat

    auto = get_auto_reply(chat_lower, sender_id, state)
    if auto:
        reply(sender_id, auto)
        return "ok",200

    handler = STATE_HANDLERS.get(current)
    if handler:
        handler(sender_id, chat_lower, state)
        return "ok",200

    reply(sender_id, ERROR_MSG)
    return "ok",200
