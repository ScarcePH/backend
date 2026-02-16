from bot.services.messenger import reply
from bot.state.manager import set_state
from bot.core.constants import PAYMENT_METHOD

def handle_payment_method(sender_id, chat_lower, state):
    if chat_lower not in ['cop', 'cod', 'pay now', 'full payment']:
        reply(sender_id, "Please reply with: 'cop', 'cod', or 'full payment'" ,PAYMENT_METHOD)
        return

    is_cod = chat_lower in ["cod", "cop"]
    amount = "1000" if state['status'] == 'preorder' or is_cod else state['price']
  

    set_state(sender_id, {
        **state,
        "state": "handle_verify_payment",
        "payment_method": chat_lower
    })

    reply(sender_id,
        f"To proceed with your order, please deposit ₱{amount} and send a screenshot of the payment for verification.\n\n"
        "Gcash: 09352894676 – Marion Rosete",
        None
    )
