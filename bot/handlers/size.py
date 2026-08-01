from bot.services.inquiry import handle_inquiry
from bot.services.messenger import reply
from bot.core.constants import SIZE_QUICK_REPLIES
from bot.state.manager import reset_state

def handle(sender_id, chat_lower, state):
    item = state.get("item")
    if not item:
        reset_state(sender_id)
        reply(sender_id, "I lost the pair we were checking. What pair are you looking for?", None)
        return "ok"

    result = handle_inquiry(sender_id, chat_lower, state, known_item=item)
    if result:
        return result

    reply(sender_id, "What size are you looking for? (US Format)", SIZE_QUICK_REPLIES)
    return "ok"

