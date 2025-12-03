from flask import request
from .message_handler import handle_postback, handle_message
from states.handover import set_handover, is_in_handover


def webhook():
    data = request.get_json()

    if data.get("object") != "page":
        return "ignored", 200

    for entry in data.get("entry", []):
        for event in entry.get("messaging", []):
            print(f"[EVENT]: {event}")
            sender_id = event["sender"]["id"]

            # SET HUMAN REPLY ONLY WHEN CHATING WITH USER
            if event.get("message", {}).get("is_echo"):
                user_psid = event["recipient"]["id"]
                print(f"[ECHO] ADMIN MESSAGE BOT MUST STOP")
                set_handover(user_psid)
                return "ok",200

            # HUMAN REPLIES 
            if is_in_handover(sender_id):
                print(f"[HANDOVER] Message from {sender_id} Handover to Admin")
                return "ok", 200
            
              # GET STARTED
            if "postback" in event:
                payload = event["postback"].get("payload")
                handle_postback(sender_id, payload)
                return 'ok', 200

            # BOT RECEIVING MESSAGES 
            if "message" in event and "text" in event["message"]:
                chat = event["message"]["text"].strip()
                handle_message(sender_id, chat)
                print("BOT REPLIED")
                return 'ok', 200

    return "ok", 200