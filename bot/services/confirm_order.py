from datetime import datetime

from bot.state.manager import reset_state, get_state
from bot.core.constants import CONFIRM_HEADER
from bot.services.messenger import reply
from db.database import db
from db.models import CheckoutSession, Inventory, InventoryVariation
from db.models.users import User
from db.repository.checkout import submit_checkout_for_review
from task.email import enqueue_email

def _notify_staff_once(session_id):
    session = (
        CheckoutSession.query
        .filter_by(id=session_id)
        .with_for_update()
        .one_or_none()
    )
    if not session:
        raise RuntimeError("Checkout session missing during staff notification")
    if session.review_notified_at is not None:
        return
    admin = User.query.filter_by(role="super_admin").first()
    if not admin or not admin.email:
        raise RuntimeError("No super-admin email is configured")

    from api.checkout import _build_admin_action_urls

    approve_url, decline_url = _build_admin_action_urls(str(session.id))
    items = []
    for line in session.items_json or []:
        inventory = Inventory.query.get(line.get("inventory_id"))
        variation = InventoryVariation.query.get(line.get("variation_id"))
        items.append({
            "name": inventory.name if inventory else "Item",
            "size": f"{variation.size}us" if variation and variation.size else None,
            "price": str(variation.price) if variation and variation.price is not None else None,
        })
    enqueue_email({
        "type": "admin_order_notification",
        "to": admin.email,
        "template_variables": {
            "order_id": str(session.id),
            "customer_name": session.customer.name if session.customer and session.customer.name else "Customer",
            "customer_phone": session.customer.phone if session.customer else None,
            "customer_address": session.customer.address if session.customer else None,
            "items": items,
            "total": str(session.total_price),
            "payment_ss": session.proof_image_url,
            "approve_url": approve_url,
            "decline_url": decline_url,
        },
    }, task_id=f"checkout-review-{session.id}")
    session.review_notified_at = datetime.utcnow()
    db.session.commit()


def confirm_order(sender_id):
    state = get_state(sender_id)
    required = [
        "customer_name",
        "customer_address",
        "customer_phone",
        "checkout_session_id",
        "payment_ss",
    ]
    if any(state.get(key) is None for key in required):
        reset_state(sender_id)
        return reply(sender_id, "Your checkout session expired. Please select the pair again to restart.", None)

    result, status_code = submit_checkout_for_review(
        state["checkout_session_id"],
        payment_method=state.get("payment_method"),
        expected_amount=state.get("expected_payment_amount"),
    )
    if status_code != 200:
        reset_state(sender_id)
        return reply(sender_id, result["message"] + ". Please select the pair again to restart.", None)

    session = result["session"]
    first_line = (session.items_json or [{}])[0]
    inventory = Inventory.query.get(first_line.get("inventory_id"))
    variation = InventoryVariation.query.get(first_line.get("variation_id"))
    msg = (
        f"{CONFIRM_HEADER}"
        f"Item: {inventory.name if inventory else 'Item'}\n"
        f"Size: {variation.size if variation else ''}\n"
        f"Price: ₱{session.total_price}\n"
        f"Name: {state['customer_name']}\n"
        f"Address: {state['customer_address']}\n\n"
        f"Phone: {state['customer_phone']}\n\n"
        "Your payment proof is pending human review. We'll contact you after approval."
    )

    _notify_staff_once(session.id)
    reset_state(sender_id)
    return reply(sender_id, msg)
