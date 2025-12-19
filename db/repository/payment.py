from db.models import Payment
from db.database import db
from db.models import Customers, Inventory, InventoryVariation


def save_payment(data: dict):
    payment = Payment(**data)
    db.session.add(payment)
    db.session.commit()
    return payment