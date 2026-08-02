import os
from decimal import Decimal, InvalidOperation

from bot.services.messenger import reply
from bot.state.manager import transition_state
from bot.core.constants import GLOBAL_CHECKOUT_ACTIONS, PAYMENT_METHOD
from bot.handlers.guided import expire_checkout, reject_input

PAYMENT_ACTIONS = {
    "PAYMENT_COD": "cod",
    "PAYMENT_COP": "cop",
    "PAYMENT_FULL": "full_payment",
}

def handle_payment_method(sender_id, chat_lower, state):
    action = str(chat_lower or "").strip().upper()
    if action not in PAYMENT_ACTIONS:
        return reject_input(sender_id, state, "Please choose a payment method below.", PAYMENT_METHOD)

    if not state.get("price") or not state.get("checkout_session_id"):
        return expire_checkout(sender_id)

    payment_method = PAYMENT_ACTIONS[action]
    is_cod = payment_method in ["cod", "cop"]
    try:
        price = Decimal(str(state["price"]))
        configured_deposit = Decimal(os.environ.get("BOT_DEPOSIT_AMOUNT", "1000"))
    except (InvalidOperation, ValueError):
        return expire_checkout(sender_id)
    if price <= 0 or configured_deposit <= 0:
        return expire_checkout(sender_id)
    amount = min(price, configured_deposit) if state.get('status') == 'preorder' or is_cod else price
    amount_text = format(amount, "f")
  

    transition_state(
        sender_id,
        state,
        "handle_verify_payment",
        expected_input="payment_screenshot",
        payment_method=payment_method,
        expected_payment_amount=amount_text,
    )

    reply(sender_id,
        f"To proceed with your order, please deposit ₱{amount_text} and send a screenshot of the payment for verification.\n\n"
        "Gcash: 09352894676 – Marion Rosete",
        GLOBAL_CHECKOUT_ACTIONS
    )
