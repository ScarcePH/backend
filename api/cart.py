from flask import Blueprint, request, jsonify
from flask_jwt_extended import verify_jwt_in_request, get_jwt_identity
from db.models import Inventory, InventoryVariation, Cart, CartItem
from uuid import uuid4
from db.database import db
from api.helpers.cart import get_or_create_cart, get_active_cart


cart_bp = Blueprint("cart", __name__)

@cart_bp.route("/cart/add", methods=["POST"])
def add_to_cart():
    data = request.json

    inventory_id = data.get("inventory_id")
    variation_id = data.get("variation_id")  
    quantity = int(data.get("quantity", 1))

    if not inventory_id or quantity < 1:
        return jsonify({"error": "Invalid data"}), 400

    customer_id = None
    try:
        customer_id = get_jwt_identity()
    except:
        pass


    guest_id = request.cookies.get("guest_id")
    if not customer_id and not guest_id:
        guest_id = str(uuid4())



    cart = get_or_create_cart(customer_id=customer_id, guest_id=guest_id)


    inventory = Inventory.query.get_or_404(inventory_id)

    variation = None
    if variation_id:
        variation = InventoryVariation.query.get_or_404(variation_id)

        if variation.stock < quantity:
            return jsonify({"error": "Not enough stock"}), 400

        price = variation.price
    else:
        if inventory.stock < quantity:
            return jsonify({"error": "Not enough stock"}), 400

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
                "error": max_limit_msg,
                "available_stock": variation.stock
            }), 400

        existing_item.quantity = new_quantity

    else:

        if quantity > variation.stock:
            return jsonify({
                "error": max_limit_msg,
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

    if guest_id:
        response.set_cookie("guest_id", guest_id, httponly=True, max_age=60*60*24*30)

    return response, 200






@cart_bp.route("/cart/get", methods=["GET"])
def get_cart():
    customer_id = None
    try:
        verify_jwt_in_request(optional=True)
        customer_id = get_jwt_identity()
    except Exception:
        customer_id = None


    guest_id = request.cookies.get("guest_id")

    cart = get_active_cart(customer_id=customer_id, guest_id=guest_id)

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
            "subtotal": subtotal
        })

    return jsonify({
        "items": cart_items,
        "total": round(total, 2)
    }), 200


