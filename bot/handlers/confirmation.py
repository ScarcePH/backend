from bot.services.messenger import reply
from bot.state.manager import reset_state, transition_state
from bot.core.constants import YES_OR_NO
from bot.handlers.guided import reject_input
from db.repository.customer_service import get_or_create_customer
from db.repository.checkout import start_checkout
from bot.core.constants import PAYMENT_METHOD


def handle(sender_id, chat, state):
    item, size = state.get("item"), state.get("size")
    required = ["item", "size", "inventory_id", "variation_id", "price", "status"]
    if any(state.get(key) is None for key in required):
        reset_state(sender_id)
        return reply(sender_id, "Your checkout session expired. Please select the pair again to restart.", None)

    action = str(chat or "").strip().upper()

    if action != "ORDER_CONFIRM":
        return reject_input(
            sender_id,
            state,
            f"Please use the buttons below. Do you want to order '{item}' (US {size})?",
            YES_OR_NO,
        )

    customer = get_or_create_customer(sender_id=sender_id)
    if not customer:
        reset_state(sender_id)
        return reply(sender_id, "We couldn't start checkout. Please try selecting the pair again.", None)

    checkout_item = [{
        "inventory_id":state["inventory_id"],
        "variation_id": state["variation_id"],
        "qty":1
    }]
    
    checkout = start_checkout(
        items=checkout_item,   
        sender_id=customer.sender_id
    )

    if isinstance(checkout, tuple) or not isinstance(checkout, dict) or not checkout.get("checkout_session_id"):
        reset_state(sender_id)
        return reply(
            sender_id,
            "That pair is no longer available. Please choose another available pair.",
            None,
        )


    transition_state(
        sender_id,
        state,
        "handle_payment_method",
        expected_input="payment_method",
        payment_method=None,
        checkout_session_id=checkout["checkout_session_id"],
    )


    

    reply(sender_id,
        "Please select your payment method. For COP, use your preferred LBC branch as the delivery address.",
        PAYMENT_METHOD
    )
