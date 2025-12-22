from db.models import Inventory, InventoryVariation
from db.database import db
import re


def save_inventory(data: dict):
    inventory = Inventory(**data)
    db.session.add(inventory)
    db.session.commit()
    return inventory

def save_variation(inventory_id, data:dict):
    variation = InventoryVariation(
        inventory_id=inventory_id,
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



def extract_size(query):
    match = re.search(r'\b\d+(\.\d+)?\b', query)
    if match:
        return match.group(0)
    return None


def get_item_sizes(size):   

    query = Inventory.query.filter(
        InventoryVariation.size == size,
        InventoryVariation.status != "sold"
    ).join(InventoryVariation).all()

    result = inventory_json(query)
    
    return {
        "found": len(result)>0,
        "count": len(result),
        "items": result
    }

    

def get_inventory_with_size(name, size):
    query = (
        Inventory.query
        .filter(Inventory.name.ilike(f"%{name}%"))
        .join(InventoryVariation)
        
    )
    if size:
        query = query.filter(
            InventoryVariation.size == size,
            InventoryVariation.status != "sold"
        )

    inventories = query.all()

    result = inventory_json(inventories)

    return {
        "found": len(result)>0,
        "count": len(result),
        "items": result
    }

def get_all_available_inventory():
    query = Inventory.query.filter(
        InventoryVariation.status != "sold"
    ).join(InventoryVariation).all()

    result = inventory_json(query)
    return {
        "found": len(result)>0,
        "count": len(result),
        "items": result
    }

def inventory_json(items):
    result = []
    for i in items:
        result.append({
            "id": i.id,
            "name": i.name,
            "description": i.description,
            "variations": [
                {
                    "id": v.id,
                    "size": v.size,
                    "condition": v.condition,
                    "price": v.price,
                    "stock": v.stock,
                    "url": v.url,
                    "image": v.image,
                    "status": v.status
                }
                for v in i.variations
            ],
        })
    return result