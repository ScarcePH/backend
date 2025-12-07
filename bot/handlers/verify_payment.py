from bot.services.messenger import reply
from bot.state.manager import set_state
from db.repository.customer import get_customer

def handle(sender_id, screenshot, state):
    set_state(sender_id, {
        **state,
        "verify_payment": screenshot
    })
    customer = get_customer(sender_id)

    if customer:
        name = customer.name
        address = customer.address
        phone = customer.phone

        msg=("We have your previous shipping address before \n"
        f"Name: {name}\n"
        f"address:{address}\n"
        f"phone:{phone}\n"
        "Do you want to continue with this address?(yes/no)")

        set_state(sender_id,{**state,
            "state":"repeat_customer_confirm",
            "customer_name":name,
            "customer_address":address,
            "customer_phone":phone,
        })
        return reply(sender_id,msg,None)
    set_state(sender_id, {**state,
        "state": "awaiting_customer_name",
    })
    return reply(sender_id, "Great! Please provide your full name:", None)

