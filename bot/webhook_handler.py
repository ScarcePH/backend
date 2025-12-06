from flask import Blueprint, request
from bot.core.router import handle_message
from bot.handlers.postback import handle_postback
from bot.state.manager import set_handover, is_in_handover, get_state
from bot.utils.redis_client import redis_client
import os

bot_bp = Blueprint("bot", __name__)
PAGE_APP_ID = str(os.environ.get("PAGE_APP_ID"))

@bot_bp.post("/webhook")
def webhook():
    data = request.json

    if data.get("object") != "page":
        return {"status": "ignored"}

    for entry in data.get("entry", []):
        for event in entry.get("messaging", []):
            sender_id = event["sender"]["id"]

            # prevent duplicate messages
            mid = event.get("message", {}).get("mid")
            if mid:
                key = f"mid:{mid}"
                if redis_client.exists(key):
                    return {"status": "ok"}
                redis_client.setex(key, 120, 1)

            # postback
            if "postback" in event:
                handle_postback(sender_id, event["postback"].get("payload"))
                return {"status": "ok"}

            if is_in_handover(sender_id):
                return {"status": "ok"}

            is_echo = event.get("message", {}).get("is_echo")
            app_id = str(event.get("message", {}).get("app_id"))

            if app_id == PAGE_APP_ID and "text" in event["message"]:
                set_handover(event["recipient"]["id"])
                return {"status": "ok"}

            if not is_echo and "message" in event:
                msg = event["message"]
                if "text" in msg:
                    handle_message(sender_id, msg["text"].strip())
                    return {"status": "ok"}

                state = get_state(sender_id)
                if state.get("state") == 'handle_verify_payment':
                    for attachment in msg.get("attachments", []):
                        if attachment["type"] == "image":
                            handle_message(sender_id, attachment["payload"]["url"])
                    return {"status": "ok"}

    return {"status": "ok"}
