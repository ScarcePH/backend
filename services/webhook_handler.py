from flask import request
from .inventory import search_item
from .handover import set_handover, clear_handover, is_in_handover
from .quick_replies import QUICK_REPLIES
from .auto_reply import get_auto_reply
from .gpt_response import get_gpt_response
from .send_text import send_text_message

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

            inv_result = search_item(chat)

            if inv_result:
                reply = get_gpt_response(chat, inv_result)
                send_text_message(sender_id, reply, quick_replies=QUICK_REPLIES)
                continue
            
            send_text_message(sender_id, "👦 Human agent will assist.", quick_replies=QUICK_REPLIES)
            set_handover(sender_id)

    return "ok", 200
