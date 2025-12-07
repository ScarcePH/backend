from db.models import Inventory
from db.database import db


def save_inventory(data: dict):
    inventory = Inventory(**data)
    db.session.add(inventory)
    db.session.commit()
    return inventory

def get_all_inventory():
    items = Inventory.query.all()
    return [
        {
            "id": item.id,
            "name": item.name,
            "description": item.description,
            "condition": item.condition,
            "size": item.size,
            "price": item.price,
            "status": item.status,
            "url": item.url
        }
        for item in items
    ]
