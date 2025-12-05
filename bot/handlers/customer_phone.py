from bot.services.messenger import reply
from bot.state.manager import reset_state
from bot.core.constants import CONFIRM_HEADER

def handle(sender_id, chat, state):
    phone = chat.strip()

    order = {
        "item": state["item"],
        "size": state["size"],
        "price": state["price"],
        "customer_name": state["customer_name"],
        "customer_phone": phone,
        "customer_address": state["customer_address"],
        "url": state["url"]
    }

    reset_state(sender_id)

    msg = (
        f"{CONFIRM_HEADER}"
        f"Item: {order['item']}\n"
        f"Size: {order['size']}\n"
        f"Price: ₱{order['price']}\n"
        f"Name: {order['customer_name']}\n"
        f"Phone: {order['customer_phone']}\n\n"
        f"Address: {order['customer_address']}\n\n"
        "We'll verify your payment and contact you shortly."
    )

    reply(sender_id, msg)
