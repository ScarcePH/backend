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
    return Cart.query.filter_by(guest_id=guest_id, is_active=True).first()
