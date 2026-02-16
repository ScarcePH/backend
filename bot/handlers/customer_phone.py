from bot.services.messenger import reply
from bot.state.manager import reset_state
from bot.core.constants import CONFIRM_HEADER
from db.repository.customer import save_customer,get_customer,update_customer
from bot.state.manager import set_state
from bot.services.confirm_order import confirm_order


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

    set_state(sender_id, {
        **state,
        "customer_address": phone
    })

    confirm_order(sender_id)

    
