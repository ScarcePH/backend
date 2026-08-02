from bot.core.constants import GLOBAL_CHECKOUT_ACTIONS
from bot.services.messenger import reply
from bot.state.manager import record_invalid_attempt, reset_state


EXPIRED_MESSAGE = "Your checkout session expired. Please select the pair again to restart."


def expire_checkout(sender_id):
    reset_state(sender_id)
    reply(sender_id, EXPIRED_MESSAGE, None)


def reject_input(sender_id, state, message, controls=None, reason="unexpected_input"):
    _, handed_over = record_invalid_attempt(sender_id, state, reason=reason)
    if handed_over:
        reply(
            sender_id,
            "I’ve saved your checkout and asked our team to help. A person will reply here shortly.",
            None,
        )
        return True
    reply(sender_id, message, controls if controls is not None else GLOBAL_CHECKOUT_ACTIONS)
    return False
