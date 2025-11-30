from flask import request
from .inventory import search_item
from .handover import set_handover, clear_handover, is_in_handover
from .quick_replies import QUICK_REPLIES
from .auto_reply import get_auto_reply
from .gpt_response import get_gpt_response
from .send_text import send_text_message
from .gpt_analysis import get_gpt_analysis

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
                    clear_handover(sender_id)
                    welcome_text = (
                        "Hi there! Welcome to Scarceᴾᴴ 👋\n"
                        "How can we help you today?\n"
                        "Here are some quick options:"
                    )
                    send_text_message(sender_id, welcome_text, quick_replies=QUICK_REPLIES)
                    continue
                continue

            if is_in_handover(sender_id):
                return "ok", 200

            if "message" not in event:
                continue

            message = event["message"]

            if "text" not in message:
                continue

            chat = message["text"].lower().strip()

            auto_reply = get_auto_reply(chat, sender_id)
            if auto_reply:
                send_text_message(sender_id, auto_reply, quick_replies=QUICK_REPLIES)
                continue

            analysis = get_gpt_analysis(chat)

            
            intent = analysis.get("intent")
            item = analysis.get("item", "")
            size = analysis.get("size", "")
            draft_reply = analysis.get("reply", "Okay.")

            if intent == "handover":
                send_text_message(sender_id, "Okay, a human agent will assist you shortly. 👤")
                set_handover(sender_id)
                continue

            if intent in ["check_product", "ask_price", "ask_availability"]:
                inv = search_item(item, size)

                if inv.get("found"):
                    final_reply = inv.get("message")
                else:
                    final_reply = f"Sorry, we currently don't have '{item}' available."

                send_text_message(sender_id, final_reply, quick_replies=QUICK_REPLIES)
                continue

            send_text_message(sender_id, draft_reply, quick_replies=QUICK_REPLIES)

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