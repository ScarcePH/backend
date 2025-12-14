from bot.services.messenger import reply
from bot.core.constants import WELCOME_MSG
from bot.state.manager import reset_state, clear_handover,set_state, get_state
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

        set_state(sender_id, {
            "state": "awaiting_confirmation",
            "item": order_payload["item"],
            "size": order_payload["size"],
            "price": order_payload["price"],
            "url": order_payload["url"],
            "item_id": order_payload["item_id"],
            "variation_id": order_payload["variation_id"]
        })

        msg = (
            f"Great! We have {order_payload['name']} (Size {order_payload['size']})us for only ₱{order_payload['price']}.\n"
            f"Please check details here: {order_payload['url']}\n"
            "Would you like to reserve this pair? (Yes / No)"
        )
        
        reply(sender_id,msg,None)