from flask import request
from .inventory import search_item
from  states.handover import set_handover, clear_handover, is_in_handover
from .quick_replies import QUICK_REPLIES
from .auto_reply import get_auto_reply
from .gpt_response import get_gpt_response
from .send_text import send_text_message
from .gpt_analysis import get_gpt_analysis
from states.user_state import get_state, set_state, reset_state
from utils.extract_size import extract_size
from services.machine_state.index import ask_item, stock_confirmation

def webhook():
    data = request.get_json()

    if data.get("object") != "page":
        return "ignored", 200

    for entry in data.get("entry", []):
        if "standby" in entry:
            print("[STANDBY] Event received while in Human Mode")
            continue
        for event in entry.get("messaging", []):
            sender_id = event["sender"]["id"]

            if "postback" in event:
                payload = event["postback"].get("payload")

                if payload == "GET_STARTED":
                    clear_handover(sender_id)
                    reset_state(sender_id)
                    send_text_message(
                        sender_id,
                        "Hi there! Welcome to Scarceᴾᴴ 👋\n"
                        "How can we help you today?\n",
                        QUICK_REPLIES
                    )
                    continue

           

            if "take_thread_control" in event:
                # Human agent took over
                set_handover(sender_id)
                print(f"[take_thread_control]: Human agent took over {sender_id}")
                return "ok", 200

            if "pass_thread_control" in event:
                # Bot was returned control
                clear_handover(sender_id)
                print(f"[pass_thread_control]: Bot regained control for {sender_id}")
                return "ok", 200
            
            if "message" in event and event["message"].get("is_echo"):
                print(f"[ECHO] Message sent by Page Admin to {sender_id}")
                # Optional: You can trigger set_handover(sender_id) here if you want 
                # the bot to shut up automatically the moment a human types.
                return "ok", 200
            
            if is_in_handover(sender_id):
                print(f"[HANDOVER] Message from {sender_id} ignored.")
                # clear_handover(sender_id)
                return "ok", 200
            

            if "message" not in event or "text" not in event["message"]:
                continue

            chat = event["message"]["text"].strip()
            chat_lower = chat.lower()   

            auto_reply = get_auto_reply(chat_lower, sender_id)
            if auto_reply:
                send_text_message(sender_id, auto_reply, quick_replies=QUICK_REPLIES)
                continue

            state = get_state(sender_id)
            current_state = state.get("state")

            return "ok", 200
            if current_state == "idle":
                analysis = get_gpt_analysis(chat_lower)
                intent = analysis.get("intent")
                item = analysis.get("item")
                size = analysis.get("size")
                draft_reply = analysis.get("reply", "Okay.")

                if item and size:
                    ask_item(sender_id, intent, item, size, draft_reply)
                    stock = stock_confirmation(sender_id, item, size)+"\n Scarceᴾᴴ Bot"
                   
                    send_text_message(sender_id, stock, quick_replies=QUICK_REPLIES)
                    continue

                inquire = ask_item(sender_id, intent, item, size, draft_reply)+"\n Scarceᴾᴴ Bot"
                
                # send_text_message(sender_id, inquire, quick_replies=QUICK_REPLIES)
                continue

            if current_state == "awaiting_size":
                item = state["item"]
                size = extract_size(chat_lower)
                stock = stock_confirmation(sender_id, item, size)+"\n Scarceᴾᴴ Bot"
                send_text_message(sender_id, stock, quick_replies=QUICK_REPLIES)
                continue
                

            if current_state == "awaiting_confirmation":
                if chat_lower not in ["yes", "y", "no", "n"]:
                    item = state["item"]
                    size = state["size"]
                    msg = (
                        f"Please reply with 'Yes' or 'No'.\n"
                        f"Do you want to reserve '{item}' (Size {size}us)? \n Scarceᴾᴴ Bot "
                    )
                    send_text_message(sender_id, msg, quick_replies=QUICK_REPLIES)
                    continue

                if chat_lower in ["no", "n"]:
                    reset_state(sender_id)
                    msg = "No worries! Let me know if you want to check another item. "
                    send_text_message(sender_id, msg, quick_replies=QUICK_REPLIES)
                    continue

                set_state(sender_id, {
                    **state,
                    "state": "awaiting_customer_name"
                })
                send_text_message(sender_id, "Great! Please provide your full name:  ")
                continue

            if current_state == "awaiting_customer_name":
                name = chat.strip()

                set_state(sender_id, {
                    **state,
                    "state": "awaiting_customer_address",
                    "customer_name": name
                })
                msg = f"Thanks, {name}! Can I have your delivery address next? "
                send_text_message(sender_id, msg)
                continue

            if current_state == "awaiting_customer_address":
                address = chat.strip()

                set_state(sender_id, {
                    **state,
                    "state": "awaiting_customer_phone",
                    "customer_address": address
                })
                msg = "Thanks! Lastly, what’s your phone number?."
                send_text_message(sender_id, msg)
                continue

            if current_state == "awaiting_customer_phone":
                phone = chat.strip()

                order = {
                    "item": state["item"],
                    "size": state["size"],
                    "price": state["price"],
                    "customer_name": state["customer_name"],
                    "customer_phone": phone,
                    'customer_address': state["customer_address"],
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
                    f"Address: {order['customer_address']}\n\n"
                    f"We’ll contact you shortly. You can also view the item here:\n{order['url']} \n Scarceᴾᴴ Bot "
                )
                send_text_message(sender_id, confirmation, quick_replies=QUICK_REPLIES)
                continue

      
            msg = "I didn’t catch that. What item are you looking for? \n Scarceᴾᴴ Bot "
            send_text_message(sender_id, msg, quick_replies=QUICK_REPLIES)
    
    return "ok", 200


