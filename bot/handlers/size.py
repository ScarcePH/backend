from bot.utils.extract_size import extract_size
from bot.services.messenger import reply,send_carousel
from db.repository.inventory import get_inventory_with_size
from bot.core.constants import NOTIFY_USER, SIZE_QUICK_REPLIES
from bot.state.manager import set_state

def handle(sender_id, chat_lower, state):
    item = state["item"]
    size = extract_size(chat_lower)
    if size:
        stocks = get_inventory_with_size(item, size)
        if stocks.get("found"):
            reply(sender_id, f"We have {item} in size {size}us")
            send_carousel(sender_id, stocks["items"])
            return "ok"
        not_available = f"We Currently Don't have {item} in size {size}us.\n Would like me to notify you when it is available? "
        reply(sender_id, not_available , NOTIFY_USER)
        set_state(sender_id, {
            "size": size,
            "item": item
        })
        return "ok"
    

    reply(sender_id, "What size are you looking for? (US Format)", SIZE_QUICK_REPLIES)


