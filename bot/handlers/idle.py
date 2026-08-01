from bot.services.inquiry import handle_inquiry

def handle(sender_id, chat, state):
    return handle_inquiry(sender_id, chat, state)
