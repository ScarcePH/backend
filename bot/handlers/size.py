from bot.utils.extract_size import extract_size
from bot.services.messenger import reply,send_carousel
from bot.services.stock import stock_confirmation
from db.repository.inventory import search_items
from bot.core.constants import NOTIFY_USER

def handle(sender_id, chat_lower, state):
    item = state["item"]
    size = extract_size(chat_lower)
    if size:
        stocks = search_items(item, size)
        if stocks.get("found"):
            reply(sender_id, f"We have {item} in size {size}us")
            send_carousel(sender_id, stocks["items"])
            return
        not_available = f"We Currently Don't have {item} in size {size}us"
        reply(sender_id, not_available , NOTIFY_USER)

        ##NEXT STEP IF NOT AVAILABLE SAVE TO LEADS AND NOTIFY IF AVAILABLE
