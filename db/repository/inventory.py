from db.models import Inventory, InventoryVariation
from db.database import db
import re


def save_inventory(data: dict):
    inventory = Inventory(**data)
    db.session.add(inventory)
    db.session.commit()
    return inventory

def save_variation(item_id, data:dict):
    variation = InventoryVariation(
        inventory_id=item_id,
       **data
    )
    db.session.add(variation)
    db.session.commit()
    return variation

def get_all_inventory():
    items = Inventory.query.all()
    result = []
    for i in items:
        result.append({
            "id": i.id,
            "name": i.name,
            "description": i.description,
        })
    return result

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
            "url": item.url,
            "image": item.image,
            "status": item.status,
            "condition": item.condition
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

def get_inventory_with_size(name, size):
    query = (
        Inventory.query
        .filter(Inventory.name.ilike(f"%{name}%"))
        .join(InventoryVariation)
        
    )
    if size:
        query = query.filter(InventoryVariation.size == size)

    inventories = query.all()

    result = []
    for item in inventories:
        result.append({
            "id": item.id,
            "name": item.name,
            "variations": [
                {
                    "id": v.id,
                    "size": v.size,
                    "condition": v.condition,
                    "price": v.price,
                    "stock": v.stock
                }
                for v in item.variations if v.size == size 
            ],
            "instocks": [
                {
                    "id": v.id,
                    "size": v.size,
                    "condition": v.condition,
                    "price": v.price,
                    "stock": v.stock
                }
                for v in item.variations
            ],
        })

    return {
        "found": len(result)>0,
        "count": len(result),
        "items": result
    }