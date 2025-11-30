from services.inventory import search_item
from services.send_text import send_text_message
from services.user_state import set_state
from services.gpt_analysis import get_gpt_analysis

def ask_item(sender_id, intent, item, size, draft_reply):
   
    if not item & intent not in ["check_product", "ask_price", "ask_availability"]:
        send_text_message(sender_id, draft_reply)

    if not size:
        set_state(sender_id, {
            "state": "awaiting_size",
            "item": item
        })
        send_text_message(sender_id, f"What size for '{item}'?")
        

def stock_confirmation(sender_id, item, size):

    inv = search_item(item, size)
    if not inv.get("found"):
        size_available = search_item(item)  
        send_text_message(sender_id, 
        f"Sorry, we currently don't have '{item}' available in size {size}." 
        f"we only have {size_available.get('size')} available.")

    set_state(sender_id, {
        "state": "awaiting_confirmation",
        "item": inv["name"],
        "size": inv["size"],
        "price": inv["price"],
        "url": inv["url"]
    })

    msg = (
        f"Great! We have {inv['name']} (Size {inv['size']}) for only ₱{inv['price']}.\n"
        f"Please check details here: {inv['url']}\n"
        "Would you like to reserve this pair? (Yes / No)"
    )

    send_text_message(sender_id, msg)


