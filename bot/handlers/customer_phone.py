from bot.services.messenger import reply
from bot.state.manager import reset_state
from bot.core.constants import CONFIRM_HEADER
from db.repository.customer import save_customer,get_customer,update_customer
from db.repository.order import save_order

def handle(sender_id, chat, state):
    print("[STATE]:", state)
    phone = chat.strip()

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
        state["customer_name"],
        phone,
        state["customer_address"]
    )
    order = {

        "customer_id": customer.id,
        "inventory_id": state['inventory_id'],
        "variation_id": state["variation_id"],
        "payment_ss": state["payment_ss"]
    }
    save_order(order)

    msg = (
        f"{CONFIRM_HEADER}"
        f"Item: {state['item']}\n"
        f"Size: {state['size']}\n"
        f"Price: ₱{state['price']}\n"
        f"Name: {state['customer_name']}\n"
        f"Phone: {phone}\n\n"
        f"Address: {state['customer_address']}\n\n"
        "We'll verify your payment and contact you shortly."
    )

    return reply(sender_id, msg)
