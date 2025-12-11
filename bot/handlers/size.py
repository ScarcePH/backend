from bot.utils.extract_size import extract_size
from bot.services.messenger import reply,send_carousel
from bot.services.stock import stock_confirmation
from db.repository.inventory import search_items

def handle(sender_id, chat_lower, state):
    item = state["item"]
    size = extract_size(chat_lower)
    if size:
        stocks = search_items(sender_id, item, size)
        if stocks.get("found"):
            reply(sender_id, f"We have {item} in size {size}us")
            send_carousel(sender_id, stocks["items"])
            return
        reply(sender_id, f"We have {item} in size {size}us")
