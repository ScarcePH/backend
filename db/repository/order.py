from db.models import Order
from db.database import db

def save_order(data: dict):
    order = Order(**data)
    db.session.add(order)
    db.session.commit()
    return order