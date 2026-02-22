import re

from bot.services.messenger import reply
from bot.state.manager import set_state
from db.repository.customer import get_customer, save_customer, update_customer
from bot.core.constants import USE_OR_CHANGE_ADDRESS


def _is_valid_email(email: str) -> bool:
    pattern = r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$"
    return re.match(pattern, email or "") is not None


def handle(sender_id, chat, state):
    email = (chat or "").strip().lower()

    if not _is_valid_email(email):
        reply(sender_id, "Please send a valid email address (example: juan@gmail.com).", None)
        return

    customer = get_customer(sender_id)
    if not customer:
        save_customer({
            "sender_id": sender_id,
            "email": email,
        })
        customer = get_customer(sender_id)
    else:
        update_customer(sender_id, email=email)
        customer = get_customer(sender_id)

    name = customer.name if customer else None
    address = customer.address if customer else None
    phone = customer.phone if customer else None

    if name and address and phone:
        msg = (
            "We have your most recent Shipment info.\n"
            f"Name: {name}\n"
            f"Address: {address}\n"
            f"Phone: {phone}\n\n"
            "Would you like to use this address for your order?"
        )
        set_state(sender_id, {
            **state,
            "state": "repeat_customer_confirm",
            "customer_name": name,
            "customer_address": address,
            "customer_phone": phone,
            "email": email,
        })
        reply(sender_id, msg, USE_OR_CHANGE_ADDRESS)
        return

    set_state(sender_id, {
        **state,
        "state": "awaiting_customer_name",
        "email": email,
    })
    reply(sender_id, "Thanks! Now please provide your full name for shipping.", None)
