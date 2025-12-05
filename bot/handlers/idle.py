from bot.services.messenger import reply
from bot.services.nlp import get_gpt_analysis
from bot.services.stock import ask_item, stock_confirmation
from bot.state.manager import set_handover

def handle(sender_id, chat, state):
    analysis = get_gpt_analysis(chat)
    intent, item, size = analysis.get("intent"), analysis.get("item"), analysis.get("size")
    draft = analysis.get("reply", "Okay.")

    if intent == "handover":
        set_handover(sender_id)

    if item and size:
        ask_item(sender_id, intent, item, size, draft)
        stock = stock_confirmation(sender_id, item, size)
        reply(sender_id, stock)
        return

    inquiry = ask_item(sender_id, intent, item, size, draft)
    reply(sender_id, inquiry)
