from bot.services.messenger import reply
from bot.state.manager import set_state

def handle(sender_id, chat, state):
    name = chat.strip()
    set_state(sender_id, {
        **state,
        "state": "awaiting_customer_address",
        "customer_name": name
    })
    reply(sender_id, f"Thanks, {name}! Please send your complete delivery address so we can proceed with your order.", None)
