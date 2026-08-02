from bot.services.messenger import reply
from bot.state.manager import transition_state
from bot.core.constants import USE_OR_CHANGE_ADDRESS
from bot.services.confirm_order import confirm_order
from bot.handlers.guided import expire_checkout, reject_input

def repeat_customer_confirm(sender_id,chat,state):
    res = str(chat or "").strip().upper()
    customer_name = state.get('customer_name')
    customer_address = state.get('customer_address')
    customer_phone = state.get('customer_phone')
    if not customer_name or not customer_address or not customer_phone:
        return expire_checkout(sender_id)

    if res not in ["ADDRESS_USE", "ADDRESS_CHANGE"]:
        msg = ("We have your most recent Shipment info."
            f"name:{customer_name} \n"
            f"address: {customer_address} \n"
            f"phone {customer_phone} \n"
            "Would you like to use this address for your order?"
        )
        return reject_input(sender_id, state, msg, USE_OR_CHANGE_ADDRESS)
    
    if res == "ADDRESS_CHANGE":
        transition_state(
            sender_id, state, "awaiting_customer_name", expected_input="customer_name",
        )
        return reply(sender_id, "Please provide your full name.", USE_OR_CHANGE_ADDRESS[2:])
    
    return confirm_order(sender_id)
