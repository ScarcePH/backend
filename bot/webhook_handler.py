from flask import request
from bot.state.manager import set_handover, is_in_handover
from bot.utils.redis_client import redis_client
import os

from bot.core.router import handle_message
from bot.handlers.postback import handle_postback

BOT_APP_ID = str(os.environ.get("BOT_APP_ID"))


def webhook():
    data = request.get_json()

    if data.get("object") != "page":
        return "ignored", 200

    for entry in data.get("entry", []):
        for event in entry.get("messaging", []):
            print(f"[EVENT]: {event}")
            sender_id = event["sender"]["id"]

            ## STOP META RETRIES WHEN RENDER IS DOWN
            mid = event.get("message", {}).get("mid")
            if mid:
                key = f"mid:{mid}"
                if redis_client.exists(key):
                    print(f"[SKIP] Duplicate message id {mid}")
                    return "ok", 200
                ## 2 MINS 
                redis_client.setex(key, 120, 1)

            if "postback" in event:
                payload = event["postback"].get("payload")
                handle_postback(sender_id, payload)
                return "ok", 200

            if is_in_handover(sender_id):
                print(f"[HANDOVER] Message from {sender_id} Handover to Admin")
                return "ok", 200

             ## ECHO IS ACITVATED TO CAPTURE ADMIN OWN MESSAGE TO SHUTUP BOT
            is_echo = event.get("message", {}).get("is_echo")
            app_id = str(event.get("message", {}).get("app_id"))
            
            if is_echo and app_id != BOT_APP_ID:
                user_psid = event["recipient"]["id"]
                print(f"[ECHO] ADMIN REPLIES THE CHAT")
                set_handover(user_psid)
                return "ok",200
            
            if not is_echo:
                if "message" in event:

                    msg = event["message"]

                    if "text" in msg:
                        chat = msg["text"].strip()
                        handle_message(sender_id, chat)
                        print("BOT REPLIED")
                        return "ok", 200
                    


                    if "attachments" in msg:
                        for attachment in msg["attachments"]:
                            if attachment["type"] == "image":
                                image_url = attachment["payload"]["url"]
                                print(f"[IMAGE_RECEIVED] {image_url}")
                                handle_message(sender_id, image_url)

                        return "ok", 200


    return "ok", 200