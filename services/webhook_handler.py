from flask import request
from .message_handler import handle_postback, handle_message
from states.handover import set_handover, is_in_handover


def webhook():
    data = request.get_json()

    if data.get("object") != "page":
        return "ignored", 200

    for entry in data.get("entry", []):
        for event in entry.get("messaging", []):
            sender_id = event["sender"]["id"]

            # GET STARTED
            if "postback" in event:
                payload = event["postback"].get("payload")
                handle_postback(sender_id, payload)
                continue

            # SET HUMAN REPLY ONLY WHEN CHATING WITH USER
            if event.get("message", {}).get("is_echo"):
                user_psid = event["recipient"]["id"]
                print(f"[ECHO] Message echo received for {user_psid}")
                set_handover(user_psid)
                continue

            # HUMAN REPLIES 
            if is_in_handover(sender_id):
                print(f"[HANDOVER] Message from {sender_id}")
                return "ok", 200

            # BOT RECEIVING MESSAGES 
            if "message" in event and "text" in event["message"]:
                chat = event["message"]["text"].strip()
                handle_message(sender_id, chat)
                continue

    return "ok", 200