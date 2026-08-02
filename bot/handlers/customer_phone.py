import re

from db.repository.customer import save_customer,get_customer,update_customer
from bot.state.manager import set_state
from bot.services.confirm_order import confirm_order
from bot.core.constants import GLOBAL_CHECKOUT_ACTIONS
from bot.handlers.guided import expire_checkout, reject_input


def normalize_ph_phone(value):
    phone = re.sub(r"[\s\-()]", "", str(value or "").strip())
    if re.fullmatch(r"09\d{9}", phone):
        return "+63" + phone[1:]
    if re.fullmatch(r"\+639\d{9}", phone):
        return phone
    return None


def handle(sender_id, chat, state):
    phone = normalize_ph_phone(chat)

    if not state.get("customer_name") or not state.get("customer_address"):
        return expire_checkout(sender_id)

    if not phone:
        return reject_input(
            sender_id,
            state,
            "Please use 09xxxxxxxxx or +639xxxxxxxxx for your mobile number.",
            GLOBAL_CHECKOUT_ACTIONS,
            reason="invalid_phone",
        )

    customer_payload = {
        "sender_id": sender_id,
        "name": state["customer_name"],
        "phone": phone,
        "address": state["customer_address"]
    }
    customer_exists = get_customer(sender_id)
    if(not customer_exists):
        save_customer(customer_payload)

    customer = update_customer(
        sender_id,
        state["customer_name"],
        phone,
        state["customer_address"]
    )

    set_state(sender_id, {
        **state,
        "customer_phone": phone,
        "expected_input": None,
        "invalid_attempts": 0,
    })

    confirm_order(sender_id)

    
