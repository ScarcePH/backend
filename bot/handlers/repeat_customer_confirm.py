from bot.services.messenger import reply
from bot.state.manager import set_state
from bot.core.constants import USE_OR_CHANGE_ADDRESS
from bot.services.confirm_order import confirm_order

def repeat_customer_confirm(sender_id,chat,state):
    print("[STATE]:", state)
    res = chat.strip()
    customer_name = state['customer_name']
    customer_address = state['customer_address']
    customer_phone = state['customer_phone']

    if res not in ["yes", "y", "no", "n", "use this address", "change address"]:
        msg = ("We have your most recent Shipment info."
            f"name:{customer_name} \n"
            f"address: {customer_address} \n"
            f"phone {customer_phone} \n"
            "Would you like to use this address for your order?"
        )
        return reply(sender_id,msg, USE_OR_CHANGE_ADDRESS)
    
    if str(res).lower() in ["no", "n", "change address"]:
        set_state(sender_id, {**state,
            "state": "awaiting_customer_name",
        })
        return reply(sender_id, "We will start with your name, please provide your full name.", None)
    
    return confirm_order(sender_id)
