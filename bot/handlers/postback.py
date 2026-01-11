from bot.services.messenger import reply
from bot.core.constants import WELCOME_MSG,YES_OR_NO
from bot.state.manager import reset_state, clear_handover,set_state, get_state
from db.repository.inventory import get_all_available_inventory
from bot.services.messenger import send_carousel
import json

def handle_postback(sender_id, payload,event):
    if payload == "GET_STARTED":
        clear_handover(sender_id)
        reset_state(sender_id)
        reply(sender_id, WELCOME_MSG)
        return "ok"


    order_payload = json.loads(event["postback"]["payload"])

    if order_payload["action"] == "ORDER":
        print("[POSTBACK EVENT]:", event)
        clear_handover(sender_id)
        set_state(sender_id, {
            "state": "awaiting_confirmation",
            "item": order_payload["item"],
            "size": order_payload["size"],
            "price": order_payload["price"],
            "url": order_payload["url"],
            "inventory_id": order_payload["inventory_id"],
            "variation_id": order_payload["variation_id"],
            "status": order_payload['status']
        })
        status = "📦 PREORDER \n 🔒 DP ₱1000 required to process order. the rest upon arrival" if order_payload["status"] == 'preorder' else  order_payload["status"]

        msg = (
            f"{order_payload['item']} \n"
            f"📏 Size: {order_payload['size']}us \n"
            f"🏷️ ₱{order_payload['price']} only. \n"
            f"{status} \n\n"
            "Would you like to order this pair? (Yes / No)"
        )
        
        reply(sender_id,msg, YES_OR_NO)

    print("payload",payload)


   
    if payload.startswith("PAGE_"):
        page = int(payload.split("_")[1])
        pairs = get_all_available_inventory(page)
        if pairs.get("found"):
            send_carousel(sender_id, pairs["items"], quick_replies=pairs["quick_replies"])
        return
