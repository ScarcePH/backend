from bot.services.messenger import reply
from bot.core.constants import GLOBAL_CHECKOUT_ACTIONS
from bot.handlers.guided import reject_input
from bot.state.manager import transition_state

def handle(sender_id, chat, state):
    name = str(chat or "").strip()
    if not 2 <= len(name) <= 100:
        return reject_input(
            sender_id, state, "Please enter a full name between 2 and 100 characters.",
            GLOBAL_CHECKOUT_ACTIONS, reason="invalid_name",
        )
    transition_state(
        sender_id, state, "awaiting_customer_address",
        expected_input="customer_address", customer_name=name,
    )
    reply(sender_id, f"Thanks, {name}! Please send your complete delivery address.", GLOBAL_CHECKOUT_ACTIONS)
