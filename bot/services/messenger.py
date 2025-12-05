from bot.services.send_text import send_text_message
from bot.core.constants import BOT_TAG, QUICK_REPLIES

def reply(sender_id, message, quick_replies=QUICK_REPLIES):
    send_text_message(sender_id, f"{message}\n{BOT_TAG}", quick_replies)
