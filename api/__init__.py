from api.customers import customers_bp
from api.inventory import inventory_bp
from api.orders import orders_bp
from api.auth import auth_bp
from api.dashboard import dashboard_bp
from api.cart import cart_bp
from api.checkout import checkout_bp

__all__ = [
    "customers_bp",
    "inventory_bp",
    "orders_bp",
    "auth_bp",
    'dashboard_bp',
    'cart_bp',
    "checkout_bp"
]
