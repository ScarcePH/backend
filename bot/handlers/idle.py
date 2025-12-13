from bot.services.messenger import reply,send_carousel
from bot.services.nlp import get_gpt_analysis
from bot.services.stock import ask_item, stock_confirmation
from bot.state.manager import set_handover,set_state,reset_state

from db.repository.inventory import search_items, get_item_sizes,get_inventory_with_size
from bot.core.constants import QUICK_REPLIES,NOTIFY_USER

def handle(sender_id, chat, state):
    analysis = get_gpt_analysis(chat)
    intent, item, size = analysis.get("intent"), analysis.get("item"), analysis.get("size")
    draft = analysis.get("reply", "Okay.")

    if intent == "handover":
        set_handover(sender_id)
        reply(sender_id, draft)
        return 

    if not item or intent not in ["check_product", "ask_price", "ask_availability"]:
        reply(sender_id, draft, QUICK_REPLIES)
        return 

    if item and size:
        stocks = get_inventory_with_size(item, size)

        if stocks.get("found"):
            reply(sender_id, f"We have {item} in size {size}us")
            send_carousel(sender_id, stocks["items"])
            return "ok", 200
        not_available = f"We Currently Don't have {item} in size {size}us"
        reply(sender_id, not_available , NOTIFY_USER)
        set_state(sender_id, {
            "size": size,
            "name": item
        })
        return "ok", 200
    
    if not size:
        set_state(sender_id, {
            "state": "awaiting_size",
            "item": item
        })

        reply(sender_id, f"What size for '{item}'?")
        return "ok", 200
