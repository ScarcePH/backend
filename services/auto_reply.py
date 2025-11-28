from services.handover import set_handover
from .quick_replies import AUTO_REPLIES

def get_auto_reply(message, sender_id):
    for keyword, reply in AUTO_REPLIES.items():
        if keyword in message:
            if "talk to human" in keyword:
                set_handover(sender_id)
            return reply
    return None
