from bot.services.messenger import reply
from bot.state.manager import set_state
from db.repository.customer import get_customer
from bot.core.constants import SAVED_ADDRESS

def handle(sender_id, screenshot, state):
    customer = get_customer(sender_id)

    if customer:
        name = customer.name
        address = customer.address
        phone = customer.phone

        msg=("We have your most recent Shipment info.\n"
        f"Name: {name}\n"
        f"address:{address}\n"
        f"phone:{phone}\n"
        "Would you like to use this address for your order?")

        set_state(sender_id,{**state,
            "state":"repeat_customer_confirm",
            "customer_name":name,
            "customer_address":address,
            "customer_phone":phone,
            "customer_id": customer.id,
            "payment_ss": screenshot
        })
        return reply(sender_id,msg, SAVED_ADDRESS)
    set_state(sender_id, {**state,
        "state": "awaiting_customer_name",
    })
    return reply(sender_id, "Great! To proceed with shipping, please provide your full name.", None)

