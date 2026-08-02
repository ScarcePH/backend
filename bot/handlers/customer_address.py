from bot.services.messenger import reply
from bot.core.constants import GLOBAL_CHECKOUT_ACTIONS
from bot.handlers.guided import reject_input
from bot.state.manager import transition_state

def handle(sender_id, chat, state):
    address = str(chat or "").strip()
    if not 10 <= len(address) <= 500:
        return reject_input(
            sender_id, state, "Please enter a complete address between 10 and 500 characters.",
            GLOBAL_CHECKOUT_ACTIONS, reason="invalid_address",
        )
    transition_state(
        sender_id, state, "awaiting_customer_phone",
        expected_input="customer_phone", customer_address=address,
    )
    reply(sender_id, "Thanks! Lastly, send your Philippine mobile number.", GLOBAL_CHECKOUT_ACTIONS)
