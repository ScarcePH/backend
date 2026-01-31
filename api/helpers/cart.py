from db.models import  Cart, CartItem
from db.database import db

from uuid import uuid4
from flask import request
from flask_jwt_extended import verify_jwt_in_request, get_jwt_identity
from db.models import Customers


def get_or_create_cart(user_id=None, guest_id=None):
    if user_id:
        cart = Cart.query.filter_by(user_id=user_id, is_active=True).first()
    else:
        cart = Cart.query.filter_by(guest_id=guest_id, is_active=True).first()

    if not cart:
        cart = Cart(
            user_id=user_id,
            guest_id=guest_id
        )
        db.session.add(cart)
        db.session.commit()

    return cart


def get_active_cart(user_id=None, guest_id=None):
    if user_id:
        return Cart.query.filter_by(user_id=user_id, is_active=True).first()

    if guest_id:
        return Cart.query.filter_by(guest_id=guest_id, is_active=True).first()

    return None


def merge_guest_cart_to_user(user_id, guest_id):
    if not user_id or not guest_id:
        return False

    guest_cart = Cart.query.filter_by(guest_id=guest_id, is_active=True).first()
    if not guest_cart:
        return False

    user_cart = Cart.query.filter_by(user_id=user_id, is_active=True).first()
    if not user_cart:
        user_cart = Cart(user_id=user_id, is_active=True)
        db.session.add(user_cart)
        db.session.flush() 

    # move items FIRST
    for guest_item in list(guest_cart.items):
        existing_item = CartItem.query.filter_by(
            cart_id=user_cart.id,
            inventory_id=guest_item.inventory_id,
            variation_id=guest_item.variation_id
        ).first()

        if existing_item:
            existing_item.quantity += guest_item.quantity
            db.session.delete(guest_item)
        else:
            guest_item.cart = user_cart  

    db.session.flush()  

    db.session.delete(guest_cart)
    db.session.commit()

    return True


def get_current_customer_context():
    user_id = None
    guest_id = None
    new_guest_created = False

    try:
        verify_jwt_in_request(optional=True)
        user_id = get_jwt_identity()
    except Exception:
        user_id = None

    guest_id = request.cookies.get("guest_id")

    if not user_id and not guest_id:
        guest_id = str(uuid4())
        new_guest_created = True

    return {
        "user_id": user_id,
        "guest_id": guest_id,
        "new_guest_created": new_guest_created
    }





