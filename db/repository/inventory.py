from db.models import Inventory
from db.database import db
import re


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

def search_items(name, size=None):

    query = Inventory.query.filter(
        Inventory.name.ilike(f"%{name}%")
    )

    if size:
        query = query.filter(Inventory.size.ilike(f"%{size}%"))

    # Return ALL matches
    items = query.all()

    if not items:
        return {"found": False, "reason": "not_found"}

    results = []
    for item in items:
        results.append({
            "id": item.id,
            "name": item.name,
            "size": item.size,
            "price": item.price,
            "url": item.url
        })

    return {
        "found": True,
        "count": len(results),
        "items": results
    }

def extract_size(query):
    match = re.search(r'\b\d+(\.\d+)?\b', query)
    if match:
        return match.group(0)
    return None


def get_item_sizes(size, item_name):
    # Get DB session
   

    query = Inventory.query.filter(Inventory.size.ilike(f"%{size}%"))

    if not query:
        return []

    available_items = [x.name for x in query]

    formatted_list = ", ".join(f"'{name}'" for name in available_items)

    return (
        f"We don't have '{item_name}' in size {size}us. "
        f"However, these are available in size {size}us: {formatted_list}."
    )