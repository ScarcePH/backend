from bot.services.messenger import reply
from bot.state.manager import set_state

def handle(sender_id, screenshot, state):
    set_state(sender_id, {
        **state,
        "state": "awaiting_customer_name",
        "verify_payment": screenshot
    })
    reply(sender_id, "Great! Please provide your full name:", None)
