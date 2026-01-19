from bot.services.messenger import reply
from bot.state.manager import reset_state, set_state
from bot.core.constants import YES_OR_NO
import re

def handle(sender_id, chat, state):
    item, size = state["item"], state["size"]

    clean = re.sub(r'[^a-zA-Z]', '', chat)

    if clean not in ["yes", "y", "no", "n"]:
        reply(sender_id, f"Please reply with 'Yes' or 'No'.\nDo you want to order '{item}' (Size {size}us)?", YES_OR_NO)
        return

    if clean in ["no", "n"]:
        reset_state(sender_id)
        reply(sender_id, "No worries! Let me know if you want to check another item.")
        return

    # set_state(sender_id, {**state, "state": "handle_payment_method"})
    # reply(sender_id, "Great! how do you wish to pay? (COD/COP/Pay now)\n\nNOTE: COD/COP requires ₱500 deposit.", None)

    set_state(sender_id, {
        **state,
        "state": "handle_verify_payment",
        "payment_method": "gcash"
    })

    to_pay = "1000" if state['status'] == 'preorder' else state['price']

    reply(sender_id,
        f"Please deposit ₱{to_pay} and send a screenshot.\n\n"
        "Gcash: 09352894676 – Marion Rosete",
        None
    )
