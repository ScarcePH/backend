from db.repository.inventory import get_all_available_inventory
from bot.services.messenger import send_carousel

def handle_carousel_postback(sender_id,payload):
    if payload.startswith("PAGE_"):
        page = int(payload.split("_")[1])
        pairs = get_all_available_inventory(page)
        if pairs.get("found"):
            send_carousel(sender_id, pairs["items"], quick_replies=pairs["quick_replies"])
        return