from .quick_replies import QUICK_REPLIES
from .auto_reply import get_auto_reply
from .gpt_analysis import get_gpt_analysis
from .send_text import send_text_message
from states.user_state import get_state, set_state, reset_state
from states.handover import clear_handover
from utils.extract_size import extract_size
from services.machine_state.index import ask_item, stock_confirmation


def handle_postback(sender_id, payload):
    if payload == "GET_STARTED":
        clear_handover(sender_id)
        reset_state(sender_id)
        send_text_message(
            sender_id,
            "Hi there! Welcome to Scarceᴾᴴ 👋\n"
            "How can we help you today?\n",
            QUICK_REPLIES
        )
        return


def handle_idle_state(sender_id, chat, state):
    analysis = get_gpt_analysis(chat)
    intent = analysis.get("intent")
    item = analysis.get("item")
    size = analysis.get("size")
    draft_reply = analysis.get("reply", "Okay.")

    if item and size:
        ask_item(sender_id, intent, item, size, draft_reply)
        stock = stock_confirmation(sender_id, item, size) + "\n Scarceᴾᴴ Bot"
        send_text_message(sender_id, stock, quick_replies=QUICK_REPLIES)
        return

    inquire = ask_item(sender_id, intent, item, size, draft_reply) + "\n Scarceᴾᴴ Bot"
    send_text_message(sender_id, inquire, quick_replies=QUICK_REPLIES)
    return


def handle_awaiting_size(sender_id, chat_lower, state):
    item = state["item"]
    size = extract_size(chat_lower)
    stock = stock_confirmation(sender_id, item, size) + "\n Scarceᴾᴴ Bot"
    send_text_message(sender_id, stock, quick_replies=QUICK_REPLIES)
    return 


def handle_awaiting_confirmation(sender_id, chat_lower, state):
    if chat_lower not in ["yes", "y", "no", "n"]:
        item = state["item"]
        size = state["size"]
        msg = (
            f"Please reply with 'Yes' or 'No'.\n"
            f"Do you want to reserve '{item}' (Size {size}us)? \n Scarceᴾᴴ Bot"
        )
        send_text_message(sender_id, msg, quick_replies=QUICK_REPLIES)
        return

    if chat_lower in ["no", "n"]:
        reset_state(sender_id)
        msg = "No worries! Let me know if you want to check another item."
        send_text_message(sender_id, msg, quick_replies=QUICK_REPLIES)
        return

    set_state(sender_id, {**state, "state": "awaiting_customer_name"})
    send_text_message(sender_id, "Great! Please provide your full name:")
    return


def handle_awaiting_customer_name(sender_id, chat, state):
    """Handle customer name input"""
    name = chat.strip()
    set_state(sender_id, {
        **state,
        "state": "awaiting_customer_address",
        "customer_name": name
    })
    msg = f"Thanks, {name}! Can I have your delivery address next?"
    send_text_message(sender_id, msg)
    return


def handle_awaiting_customer_address(sender_id, chat, state):
    """Handle customer address input"""
    address = chat.strip()
    set_state(sender_id, {
        **state,
        "state": "awaiting_customer_phone",
        "customer_address": address
    })
    msg = "Thanks! Lastly, what's your phone number?"
    send_text_message(sender_id, msg)
    return


def handle_awaiting_customer_phone(sender_id, chat, state):
    """Handle customer phone input and complete order"""
    phone = chat.strip()
    order = {
        "item": state["item"],
        "size": state["size"],
        "price": state["price"],
        "customer_name": state["customer_name"],
        "customer_phone": phone,
        "customer_address": state["customer_address"],
        "url": state["url"]
    }

    reset_state(sender_id)

    confirmation = (
        f"All set!\n\n"
        f"🛒 **Order Reserved**\n"
        f"Item: {order['item']}\n"
        f"Size: {order['size']}\n"
        f"Price: ₱{order['price']}\n"
        f"Name: {order['customer_name']}\n"
        f"Phone: {order['customer_phone']}\n\n"
        f"Address: {order['customer_address']}\n\n"
        f"We'll contact you shortly. You can also view the item here:\n{order['url']} \n Scarceᴾᴴ Bot"
    )
    send_text_message(sender_id, confirmation, quick_replies=QUICK_REPLIES)
    return


STATE_HANDLERS = {
    "idle": handle_idle_state,
    "awaiting_size": handle_awaiting_size,
    "awaiting_confirmation": handle_awaiting_confirmation,
    "awaiting_customer_name": handle_awaiting_customer_name,
    "awaiting_customer_address": handle_awaiting_customer_address,
    "awaiting_customer_phone": handle_awaiting_customer_phone,
}


def handle_message(sender_id, chat):
    """Route message to appropriate handler based on user state"""
    chat_lower = chat.lower()

    auto_reply = get_auto_reply(chat_lower, sender_id)
    if auto_reply:
        send_text_message(sender_id, auto_reply, quick_replies=QUICK_REPLIES)
        return

    # Get current state and route to handler
    state = get_state(sender_id)
    current_state = state.get("state", "idle")

    handler = STATE_HANDLERS.get(current_state)
    if handler:
        handler(sender_id, chat, state)
    else:
        # Fallback for unknown state
        msg = "I didn't catch that. What item are you looking for? \n Scarceᴾᴴ Bot"
        send_text_message(sender_id, msg, quick_replies=QUICK_REPLIES)
        return