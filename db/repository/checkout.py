from flask import jsonify
from db.database import db
from db.models.checkout_session import CheckoutSession
from db.models.inventory_variation import InventoryVariation
from db.repository.customer_service import get_or_create_customer

def start_checkout(items: list[dict], user_id=None, guest_id=None, sender_id=None):

    customer = get_or_create_customer(
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

    session = CheckoutSession(
        customer_id=customer.id,
        items_json=validated_items,
        total_price=total
    )

    db.session.add(session)
    db.session.commit()

    return {"checkout_session_id": str(session.id)}
