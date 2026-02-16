from bot.services.messenger import reply
from bot.state.manager import reset_state, set_state
from bot.core.constants import YES_OR_NO
import re
from db.repository.customer_service import get_or_create_customer
from db.repository.checkout import start_checkout
from bot.core.constants import PAYMENT_METHOD


def handle(sender_id, chat, state):
    item, size = state["item"], state["size"]

    clean = re.sub(r'[^a-zA-Z]', '', chat)

    if clean not in ["yes", "y", "no", "n"]:
        reply(sender_id, f"Please reply with 'Yes' or 'No'.\nDo you want to order '{item}' (Size {size}us)?", YES_OR_NO)
        return

    if clean in ["no", "n"]:
        reset_state(sender_id)
        reply(sender_id, "No worries! Let me know if you want to check another item.")
        return

    customer = get_or_create_customer(sender_id=sender_id)

    checkout_item = [{
        "inventory_id":state["inventory_id"],
        "variation_id": state["variation_id"],
        "qty":1
    }]
    
    checkout = start_checkout(
        items=checkout_item,   
        sender_id=customer.sender_id
    )


    set_state(sender_id, {
        **state,
        "state": "handle_payment_method",
        "payment_method": "gcash",
        "checkout_session_id":checkout["checkout_session_id"]
    })


    

    reply(sender_id,
        f"Please select prefered payment method: COP, COD, or Full Payment \n\n Note: for COP Please use the address of LBC Branch",
        PAYMENT_METHOD
    )
