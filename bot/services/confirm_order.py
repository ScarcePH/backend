from bot.state.manager import reset_state,get_state
from bot.core.constants import CONFIRM_HEADER
from db.repository.order import save_order
from bot.services.messenger import reply
from db.repository.payment import save_payment


def confirm_order(sender_id):
    state = get_state(sender_id)

    msg = (
        f"{CONFIRM_HEADER}"
        f"Item: {state['item']}\n"
        f"Size: {state['size']}\n"
        f"Price: ₱{state['price']}\n"
        f"Name: {state['customer_name']}\n"
        f"Address: {state['customer_address']}\n\n"
        f"Phone: {state['customer_phone']}\n\n"
        "We'll verify your payment and contact you shortly."
    )

    order_payload = {
        "customer_id": state['customer_id'],
        "inventory_id": state['inventory_id'],
        "variation_id": state["variation_id"],
    }

    order = save_order(order_payload)
    payment = {
        "payment_ss": state['payment_ss'],
        "total_amount": state['price'],
        "order_id": order['id']
    }
    save_payment(payment)
    reset_state(sender_id)
    return reply(sender_id, msg)
