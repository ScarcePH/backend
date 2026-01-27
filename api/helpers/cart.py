from db.models import Inventory, InventoryVariation, Cart, CartItem
from db.database import db


def get_or_create_cart(customer_id=None, guest_id=None):
    if customer_id:
        cart = Cart.query.filter_by(customer_id=customer_id, is_active=True).first()
    else:
        cart = Cart.query.filter_by(guest_id=guest_id, is_active=True).first()

    if not cart:
        cart = Cart(
            customer_id=customer_id,
            guest_id=guest_id
        )
        db.session.add(cart)
        db.session.commit()

    return cart


def get_active_cart(customer_id=None, guest_id=None):
    if customer_id:
        return Cart.query.filter_by(customer_id=customer_id, is_active=True).first()

    if guest_id:
        return Cart.query.filter_by(guest_id=guest_id, is_active=True).first()

    return None


def merge_guest_cart_to_user(customer_id, guest_id):
    if not customer_id or not guest_id:
        return False

    guest_cart = Cart.query.filter_by(guest_id=guest_id, is_active=True).first()
    if not guest_cart:
        return False

    user_cart = Cart.query.filter_by(customer_id=customer_id, is_active=True).first()
    if not user_cart:
        user_cart = Cart(customer_id=customer_id, is_active=True)
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


