from bot.services.messenger import reply
from bot.state.manager import set_state

def handle(sender_id, chat, state):
    address = chat.strip()
    set_state(sender_id, {
        **state,
        "state": "awaiting_customer_phone",
        "customer_address": address
    })
    reply(sender_id, "Thanks! Lastly, what's your phone number?")
