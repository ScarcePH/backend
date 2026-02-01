from uuid import uuid4
from datetime import datetime
from flask import request, jsonify
from sqlalchemy import func
from flask import Blueprint, request, jsonify
from db.models import InventoryVariation, CheckoutSession
from db.database import db
from helpers.cart import get_active_cart, get_current_customer_context



checkout_bp = Blueprint("checkout", __name__)


@checkout_bp.route("/api/checkout/start", methods=["POST"])
def start_checkout():
    data = request.json
    ctx = get_current_customer_context()


    source = data.get("source")  

    if source == "cart":
        cart =  get_active_cart(user_id=ctx["user_id"], guest_id=ctx["guest_id"])
        items = cart.items

    else:
        items = data.get("items")

    if not items:
        return jsonify({"error": "No items"}), 400

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
        user_id=ctx["user_id"],
        guest_id=ctx["guest_id"],
        items_json=validated_items,
        total_price=total
    )

    db.session.add(session)
    db.session.commit()

    return jsonify({"checkout_session_id": str(session.id)})
