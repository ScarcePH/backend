from flask import Blueprint, request, jsonify
from flask_jwt_extended import verify_jwt_in_request, get_jwt_identity
from db.models import Inventory, InventoryVariation, Cart, CartItem
from uuid import uuid4
from db.database import db
from api.helpers.cart import get_or_create_cart, get_active_cart, get_current_customer_context


cart_bp = Blueprint("cart", __name__)

@cart_bp.route("/cart/add", methods=["POST"])
def add_to_cart():
    data = request.json

    inventory_id = data.get("inventory_id")
    variation_id = data.get("variation_id")  
    quantity = int(data.get("quantity", 1))

    if not inventory_id or quantity < 1:
        return jsonify({"message": "Invalid data"}), 400

    ctx = get_current_customer_context()



    cart = get_or_create_cart(user_id=ctx["user_id"], guest_id=ctx["guest_id"])


    inventory = Inventory.query.get_or_404(inventory_id)

    variation = None
    if variation_id:
        variation = InventoryVariation.query.get_or_404(variation_id)

        if variation.stock < quantity:
            return jsonify({"message": "Not enough stock"}), 400

        price = variation.price
    else:
        if inventory.stock < quantity:
            return jsonify({"message": "Not enough stock"}), 400

        price = inventory.price

    existing_item = CartItem.query.filter_by(
        cart_id=cart.id,
        inventory_id=inventory_id,
        variation_id=variation_id
    ).first()

    max_limit_msg = f"Only {variation.stock} item(s) are available for this selection. Please adjust your quantity."

    if existing_item:
        new_quantity = existing_item.quantity + quantity

        if new_quantity > variation.stock:
            return jsonify({
                "message": max_limit_msg,
                "available_stock": variation.stock
            }), 400

        existing_item.quantity = new_quantity

    else:

        if quantity > variation.stock:
            return jsonify({
                "message": max_limit_msg,
                "available_stock": variation.stock
            }), 400
        
        item = CartItem(
            cart_id=cart.id,
            inventory_id=inventory_id,
            variation_id=variation_id,
            quantity=quantity,
            price_at_add=price
        )
        db.session.add(item)

    db.session.commit()

    response = jsonify({"message": "Item added to cart"})

    if ctx["new_guest_created"]:
        response.set_cookie("guest_id", ctx["guest_id"], max_age=60*60*24*30)

    return response, 200


@cart_bp.route("/cart/remove", methods=["POST"])
def remove_from_cart():
    data = request.json or {}

    inventory_id = data.get("inventory_id")
    variation_id = data.get("variation_id")

    try:
        inventory_id = int(inventory_id)
    except (TypeError, ValueError):
        return jsonify({"message": "Invalid inventory_id"}), 400

    try:
        variation_id = int(variation_id) if variation_id is not None else None
    except (TypeError, ValueError):
        return jsonify({"message": "Invalid variation_id"}), 400

    ctx = get_current_customer_context()
    cart = get_active_cart(user_id=ctx["user_id"], guest_id=ctx["guest_id"])

    if not cart:
        return jsonify({"message": "Cart not found"}), 404

    item = CartItem.query.filter_by(
        cart_id=cart.id,
        inventory_id=inventory_id,
        variation_id=variation_id
    ).first()

    if not item:
        return jsonify({"message": "Item not found in cart"}), 404

    db.session.delete(item)
    db.session.flush()

    remaining_items = CartItem.query.filter_by(cart_id=cart.id).count()
    if remaining_items == 0:
        db.session.delete(cart)

    db.session.commit()

    return jsonify({"message": "Item removed from cart"}), 200






@cart_bp.route("/cart/get", methods=["GET"])
def get_cart():
    ctx = get_current_customer_context()

    cart = get_active_cart(user_id=ctx["user_id"], guest_id=ctx["guest_id"])

    if not cart:
        return jsonify({
            "items": [],
            "total": 0,
            "message": "Cart is empty"
        }), 200

    cart_items = []
    total = 0

    for item in cart.items:
        variation = InventoryVariation.query.get(item.variation_id)
        inventory = Inventory.query.get(item.inventory_id)

        subtotal = float(item.price_at_add) * item.quantity
        total += subtotal

        cart_items.append({
            "inventory_id": inventory.id,
            "variation_id": variation.id,
            "inventory_name": inventory.name,
            "condition": variation.condition,
            "size": variation.size,
            "price": float(item.price_at_add),
            "quantity": item.quantity,
            "subtotal": subtotal,
            "image":inventory.image
        })

    return jsonify({
        "items": cart_items,
        "total": round(total, 2)
    }), 200

