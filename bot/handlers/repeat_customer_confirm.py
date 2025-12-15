from bot.services.messenger import reply
from bot.state.manager import set_state,reset_state
from bot.core.constants import CONFIRM_HEADER
from db.repository.order import save_order

def repeat_customer_confirm(sender_id,chat,state):
    res = chat.strip()
    customer_name = state['customer_name']
    customer_address = state['customer_address']
    customer_phone = state['customer_phone']
    if res not in ["yes", "y", "no", "n"]:
        msg = ("Please answer yes or no only. \n"
            "You want to confirm this shipping address? \n"
            f"name:{customer_name} \n"
            f"address: {customer_address} \n"
            f"phone {customer_phone} \n"
        )
        return reply(sender_id,msg, None)
    if res in ["no", "n"]:
        set_state(sender_id, {**state,
            "state": "awaiting_customer_name",
        })
        return reply(sender_id, "Great! Please provide your full name:", None)
    msg = (
        f"{CONFIRM_HEADER}"
        f"Item: {state['item']}\n"
        f"Size: {state['size']}\n"
        f"Price: ₱{state['price']}\n"
        f"Name: {customer_name}\n"
        f"Address: {customer_address}\n\n"
        f"Phone: {customer_phone}\n\n"
        "We'll verify your payment and contact you shortly."
    )
    order = {
        "customer_id": state['customer_id'],
        "inventory_id": state['inventory_id'],
        "variation_id": state["variation_id"],
        "payment_ss": state["verify_payment"]
    }
    save_order(order)
    reset_state(sender_id)
    return reply(sender_id, msg)
