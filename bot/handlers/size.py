from bot.utils.extract_size import extract_size
from bot.services.messenger import reply
from bot.services.stock import stock_confirmation

def handle(sender_id, chat_lower, state):
    item = state["item"]
    size = extract_size(chat_lower)
    stock = stock_confirmation(sender_id, item, size)
    reply(sender_id, stock)
