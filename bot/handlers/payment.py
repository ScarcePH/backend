from bot.services.messenger import reply
from bot.state.manager import set_state

def handle_payment_method(sender_id, chat_lower, state):
    if chat_lower not in ['cop', 'cod', 'pay now', 'payment 1st']:
        reply(sender_id, "Please reply with: 'cop', 'cod', or 'pay now'")
        return

    amount = state.get("amount") if chat_lower == "pay now" else 500

    set_state(sender_id, {
        **state,
        "state": "handle_verify_payment",
        "payment_method": chat_lower
    })

    reply(sender_id,
        f"Please deposit ₱{amount} and send a screenshot.\n\n"
        "Gcash: 09352894676 – Marion Rosete")
