from bot.services.messenger import reply
from bot.state.manager import reset_state, set_state

def handle(sender_id, chat, state):
    item, size = state["item"], state["size"]

    if chat not in ["yes", "y", "no", "n"]:
        reply(sender_id, f"Please reply with 'Yes' or 'No'.\nDo you want to reserve '{item}' (Size {size}us)?", None)
        return

    if chat in ["no", "n"]:
        reset_state(sender_id)
        reply(sender_id, "No worries! Let me know if you want to check another item.")
        return

    set_state(sender_id, {**state, "state": "handle_payment_method"})
    reply(sender_id, "Great! how do you wish to pay? (COD/COP/Pay now)\n\nNOTE: COD/COP requires ₱500 deposit.", None)
