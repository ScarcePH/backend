from flask import request
from .message_handler import handle_postback, handle_message
from states.handover import set_handover, is_in_handover
import os

BOT_APP_ID = str(os.environ.get("BOT_APP_ID"))


def webhook():
    data = request.get_json()

    if data.get("object") != "page":
        return "ignored", 200

    for entry in data.get("entry", []):
        for event in entry.get("messaging", []):
            print(f"[EVENT]: {event}")
            sender_id = event["sender"]["id"]

            is_echo = event.get("message", {}).get("is_echo")
            app_id = str(event.get("message", {}).get("app_id"))
            
            if  is_echo and app_id != BOT_APP_ID:
                user_psid = event["recipient"]["id"]
                print(f"[ECHO] ADMIN MESSAGE THE USER BOT MUST STOP")
                set_handover(user_psid)
                return "ok",200

            if is_in_handover(sender_id):
                print(f"[HANDOVER] Message from {sender_id} Handover to Admin")
                return "ok", 200
            
            if "postback" in event:
                payload = event["postback"].get("payload")
                handle_postback(sender_id, payload)
                continue

            if "message" in event and "text" in event["message"]:
                chat = event["message"]["text"].strip()
                handle_message(sender_id, chat)
                print("BOT REPLIED")
                continue

    return "ok", 200