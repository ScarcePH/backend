from datetime import datetime
from flask import jsonify
from db.database import db
from db.models.checkout_session import CheckoutSession
from db.models.inventory import Inventory
from db.models.inventory_variation import InventoryVariation
from db.models.payment import Payment
from db.repository.customer_service import get_or_create_customer
from db.repository.order import save_order
from bot.services.messenger import send_carousel, reply
from task.email import enqueue_email

def start_checkout(items: list[dict], customer_id=None, user_id=None, guest_id=None, sender_id=None):
    
    if not isinstance(items, list):
        return {"error": "items must be a list of objects"}

    customer = get_or_create_customer(
        customer_id=customer_id,
        user_id=user_id,
        guest_id=guest_id,
        sender_id=sender_id
    )

    if not customer:
        return jsonify({"error": "Unable to resolve customer"}), 400

    validated_items = []
    total = 0

    for item in items:
        variation = InventoryVariation.query.get(item["variation_id"])

        if not variation or variation.stock < item["qty"]:
            return jsonify({"error": "Item unavailable"}), 400

        price = variation.price
        total += price * item["qty"]

        validated_items.append({
            "inventory_id": item["inventory_id"],
            "variation_id": item["variation_id"],
            "qty": item["qty"],
            "price": float(price)
        })

    existing_session = (
        CheckoutSession.query
        .filter(CheckoutSession.customer_id == customer.id)
        .filter(CheckoutSession.status == "pending")
        .filter(CheckoutSession.expires_at > datetime.utcnow())
        .order_by(CheckoutSession.created_at.desc())
        .first()
    )

    if existing_session:
        if existing_session.items_json == validated_items:
            return {"checkout_session_id": str(existing_session.id)}
        existing_session.status = "expired"


    if(customer_id):
        session = CheckoutSession(
            customer_id=customer.id,
            items_json=validated_items,
            total_price=total,
            status='added_by_admin'
        )
    else:
        session = CheckoutSession(
            customer_id=customer.id,
            items_json=validated_items,
            total_price=total
        )



    db.session.add(session)
    db.session.commit()

    return {"checkout_session_id": str(session.id), "items":session.items_json}


def approve_checkout_session(session_id, received_amount=0):
    session = CheckoutSession.query.get(session_id)
    if not session:
        return {"message": "Checkout session not found"}, 404

    if session.is_expired():
        session.status = "expired"
        db.session.commit()
        return {
            "message": "Checkout session expired",
            "id": str(session.id),
            "status": session.status
        }, 400

    try:
        session.approve()
    except ValueError as exc:
        return {
            "message": str(exc),
            "id": str(session.id),
            "status": session.status
        }, 400

    for item in session.items_json or []:
        variation = InventoryVariation.query.get(item["variation_id"])
        if variation:
            variation.status = "sold"

    try:
        order = save_order(str(session.id))
    except Exception as exc:
        db.session.rollback()
        return {
            "message": f"Failed to create order: {exc}",
            "id": str(session.id),
            "status": session.status
        }, 400

    try:
        order_id = order.get("id") if isinstance(order, dict) else None
        if order_id:
            payment = Payment.query.filter_by(order_id=order_id).first()
            if not payment:
                payment = Payment(
                    order_id=order_id,
                    total_amount=session.total_price,
                    received_amount=received_amount if received_amount is not None else 0,
                    payment_ss=session.proof_image_url
                )
                db.session.add(payment)
    except Exception as exc:
        db.session.rollback()
        return {
            "message": f"Failed to create payment: {exc}",
            "id": str(session.id),
            "status": session.status
        }, 400

    db.session.commit()

    approved_items = []
    for item in session.items_json or []:
        inventory = Inventory.query.get(item.get("inventory_id"))
        variation = InventoryVariation.query.get(item["variation_id"])
        approved_items.append({
            "image_url": inventory.image if inventory else None,
            "name": inventory.name if inventory else "Item",
            "condition": variation.condition if variation else None,
            "size": f"{variation.size}us" if variation and variation.size else None,
            "price": str(variation.price) if variation and variation.price is not None else None
        })

    remaining_balance = session.total_price - int(received_amount)

    if session.customer and session.customer.email:
        payload = {
            "type": "approve_payment",
            "to": session.customer.email,
            "template_variables": {
                "customer_name": session.customer.name if session.customer.name else "Customer",
                "items": approved_items,
                "total": str(session.total_price) if session.total_price is not None else None,
                "remaining_balance": str(remaining_balance) ,
                "fulfillment_eta": "3-8 days",
                "year": "2024",
                "store_name": "Scarceᴾᴴ"
            }
        }
        enqueue_email(payload)

    print("MESSENGER LOGIC",isinstance(order, dict), order.get("payment"), order.get("items"))

    if session.customer and session.customer.sender_id:
        if isinstance(order, dict) and order.get("items"):
            send_carousel(session.customer.sender_id, [order], is_my_order=True)
        reply(session.customer.sender_id, "Your order is approved.", None)

    return {"session": session, "order": order}, 200


def reject_checkout_session(session_id, reject_reason=None):
    session = CheckoutSession.query.get(session_id)
    if not session:
        return {"message": "Checkout session not found"}, 404

    # if session.is_expired():
    #     session.status = "expired"
    #     db.session.commit()
    #     return {
    #         "message": "Checkout session expired",
    #         "id": str(session.id),
    #         "status": session.status
    #     }, 400

    try:
        session.reject()
    except ValueError as exc:
        return {
            "message": str(exc),
            "id": str(session.id),
            "status": session.status
        }, 400

    db.session.commit()

    declined_items = []
    for item in session.items_json or []:
        inventory = Inventory.query.get(item.get("inventory_id"))
        variation = InventoryVariation.query.get(item["variation_id"])
        declined_items.append({
            "image_url": inventory.image if inventory else None,
            "name": inventory.name if inventory else "Item",
            "category": variation.condition if variation and variation.condition else None,
            "size": f"{variation.size}us" if variation and variation.size else None,
            "price": str(variation.price) if variation and variation.price is not None else None
        })

    if session.customer and session.customer.sender_id:
        message = "Your checkout was rejected."
        if reject_reason:
            message = f"{message} Reason: {reject_reason}"
        reply(session.customer.sender_id, message, None)

    if session.customer and session.customer.email:
        payload = {
            "type": "decline_payment",
            "to": session.customer.email,
            "template_variables": {
                "customer_name": session.customer.name if session.customer.name else "Customer",
                "decline_reason": reject_reason if reject_reason else "Payment could not be validated",
                "items": declined_items,
                "total": str(session.total_price) if session.total_price is not None else None,
                "year": "2024",
                "store_name": "Scarceᴾᴴ"
            }
        }
        enqueue_email(payload)

    return {"session": session}, 200
