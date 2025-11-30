from flask import request
from .inventory import search_item
from .handover import set_handover, clear_handover, is_in_handover
from .quick_replies import QUICK_REPLIES
from .auto_reply import get_auto_reply
from .gpt_response import get_gpt_response
from .send_text import send_text_message
from .gpt_analysis import get_gpt_analysis
from .user_state import get_state, set_state, reset_state

def webhook():
    data = request.get_json()

    if data.get("object") != "page":
        return "ignored", 200

    for entry in data.get("entry", []):
        for event in entry.get("messaging", []):
            sender_id = event["sender"]["id"]

            if "postback" in event:
                payload = event["postback"].get("payload")

                if payload == "GET_STARTED":
                    reset_state(sender_id)
                    send_text_message(
                        sender_id,
                        "Hi! What item are you looking for today?"
                    )
                    continue

            if is_in_handover(sender_id):
                return "ok", 200

            if "message" not in event or "text" not in event["message"]:
                continue

            chat = event["message"]["text"].strip()
            chat_lower = chat.lower()

            state = get_state(sender_id)
            current_state = state.get("state")


            if current_state == "idle":
                analysis = get_gpt_analysis(chat_lower)
                intent = analysis.get("intent")
                item = analysis.get("item")

                if not item:
                    send_text_message(sender_id, "What item are you looking for?")
                    continue

                set_state(sender_id, {
                    "state": "awaiting_size",
                    "item": item
                })

                send_text_message(sender_id, f"What size for '{item}'?")
                continue

            if current_state == "awaiting_size":
                item = state["item"]
                size = chat_lower

                inv = search_item(item, size)

                if not inv.get("found"):
                    send_text_message(sender_id, f"'{item}' in size {size} is not available. Try another size:")
                    continue

                set_state(sender_id, {
                    "state": "awaiting_confirmation",
                    "item": inv["name"],
                    "size": inv["size"],
                    "price": inv["price"],
                    "url": inv["url"]
                })

                msg = (
                    f"Great! We have {inv['name']} (Size {inv['size']}) for ₱{inv['price']}.\n"
                    "Would you like to reserve this pair? (Yes / No)"
                )
                send_text_message(sender_id, msg)
                continue

            if current_state == "awaiting_confirmation":
                if chat_lower not in ["yes", "y", "no", "n"]:
                    send_text_message(sender_id, "Please answer Yes or No.")
                    continue

                if chat_lower in ["no", "n"]:
                    reset_state(sender_id)
                    send_text_message(sender_id, "No worries! Let me know if you want to check another item.")
                    continue

                set_state(sender_id, {
                    **state,
                    "state": "awaiting_customer_name"
                })

                send_text_message(sender_id, "Great! Please provide your full name:")
                continue

            if current_state == "awaiting_customer_name":
                name = chat.strip()

                set_state(sender_id, {
                    **state,
                    "state": "awaiting_customer_phone",
                    "customer_name": name
                })

                send_text_message(sender_id, "Thanks! Lastly, what’s your phone number?")
                continue

            if current_state == "awaiting_customer_phone":
                phone = chat.strip()

                order = {
                    "item": state["item"],
                    "size": state["size"],
                    "price": state["price"],
                    "customer_name": state["customer_name"],
                    "customer_phone": phone,
                    "url": state["url"]
                }

             

                reset_state(sender_id)

                confirmation = (
                    f"All set!\n\n"
                    f"🛒 **Order Reserved**\n"
                    f"Item: {order['item']}\n"
                    f"Size: {order['size']}\n"
                    f"Price: ₱{order['price']}\n"
                    f"Name: {order['customer_name']}\n"
                    f"Phone: {order['customer_phone']}\n\n"
                    f"We’ll contact you shortly. You can also view the item here:\n{order['url']}"
                )

                send_text_message(sender_id, confirmation)
                continue

      
            send_text_message(sender_id, "I didn’t catch that. What item are you looking for?")
    
    return "ok", 200


# def test():
#     data = request.get_json()
#     chat = data.get("chat")
#     analysis = get_gpt_analysis(chat)
       
#     intent = analysis.get("intent")
#     item = analysis.get("item", "")
#     size = analysis.get("size", "")
#     draft_reply = analysis.get("reply", "Okay.")

#     if intent == "handover":
#             return "Okay, a human agent will assist you shortly. 👤"
    
#     if intent in ["check_product", "ask_price", "ask_availability"]:
#         inv = search_item(item, size)
#         if inv.get("found"):
#              final_reply = inv.get("message")
#         else:
#             final_reply = f"Sorry, we currently don't have '{item}' available."

#         return final_reply