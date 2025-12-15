from bot.services.messenger import reply
from bot.state.manager import reset_state
from bot.core.constants import CONFIRM_HEADER
from db.repository.customer import save_customer,get_customer,update_customer
from db.repository.order import save_order

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

    customer_payload = {
        "sender_id": sender_id,
        "name": state["customer_name"],
        "phone": phone,
        "address": state["customer_address"]
    }
    customer_exists = get_customer(sender_id)
    if(not customer_exists):
        customer = save_customer(customer_payload)
        print(f"[CUSTOMER]:{customer.id}")

    customer = update_customer(
        sender_id,
        order["customer_name"],
        order["customer_phone"],
        order["customer_address"]
    )
    order = {

        "customer_id": customer.id,
        "item_id": state['inventory_id'],
        "variation_id": state["inventory_variation_id"],
        "payment_ss": state["verify_payment"]
    }
    save_order(order)

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

    return reply(sender_id, msg)
