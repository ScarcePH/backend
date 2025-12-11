from bot.services.messenger import reply
from bot.core.constants import WELCOME_MSG, QUICK_REPLIES
from bot.state.manager import reset_state, clear_handover

def handle_postback(sender_id, payload):
    if payload == "GET_STARTED":
        clear_handover(sender_id)
        reset_state(sender_id)
        reply(sender_id, WELCOME_MSG,QUICK_REPLIES)