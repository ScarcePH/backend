from services.inventory import search_item,get_item_sizes
from states.user_state import set_state
from states.handover import set_handover

def ask_item(sender_id, intent, item, size, draft_reply):
   
    if not item or intent not in ["check_product", "ask_price", "ask_availability"]:
        return draft_reply

    if not size:
        set_state(sender_id, {
            "state": "awaiting_size",
            "item": item
        })
        return f"What size for '{item}'?"
        

def stock_confirmation(sender_id, item, size):

    if not size:
        set_state(sender_id, {
            "state": "idle",
            "item": item
        })
        return f"Your inquiry of '{item}' is Cancelled."

    inv = search_item(item, size)
       
    print("INVENTORY SEARCH RESULT:", inv)
    if not inv.get("found"):
        ## RESET STATE TO IDLE
        set_state(sender_id, {
            "state": "idle"
        })
        if inv.get("name", ""):
            size_available = search_item(item)  
            if size_available.get("found"):
                sizes = size_available["size"]
                return f"Sorry, '{item}' is not available in size {size}us. Available size(s): {sizes}. "
        
        item_available_in_size = get_item_sizes(size,item)
        print("[ITEMS AVAILABLE IN SIZE]:", item_available_in_size)
        if item_available_in_size:
            return item_available_in_size
        
        return f"Sorry, we currently don't have '{item}' available in size {size}."


    set_state(sender_id, {
        "state": "awaiting_confirmation",
        "item": inv["name"],
        "size": inv["size"],
        "price": inv["price"],
        "url": inv["url"]
    })

    msg = (
        f"Great! We have {inv['name']} (Size {inv['size']})us for only ₱{inv['price']}.\n"
        f"Please check details here: {inv['url']}\n"
        "Would you like to reserve this pair? (Yes / No)"
    )

    return msg



