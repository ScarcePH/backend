from db.models import Inventory, InventoryVariation
from db.database import db
import re
from sqlalchemy.orm import contains_eager



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
    result = [Inventory.to_dict(item) for item in items]
    return result



def extract_size(query):
    match = re.search(r'\b\d+(\.\d+)?\b', query)
    if match:
        return match.group(0)
    return None


def get_item_sizes(size):   

    query = (
        Inventory.query
        .join(InventoryVariation)
        .filter(
            InventoryVariation.size == size, 
            InventoryVariation.status != "sold"
        )
        .options(contains_eager(Inventory.variations))
        .all()
    )


    result = [Inventory.to_dict(item) for item in query]
    
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
        ).options(contains_eager(Inventory.variations))


    inventories = query.all()


    result = [Inventory.to_dict(item) for item in query]

    return {
        "found": len(result)>0,
        "count": len(result),
        "items": result
    }

def get_all_available_inventory():
    query = (
        Inventory.query
        .join(InventoryVariation)
        .filter(InventoryVariation.status != "sold")
        .options(contains_eager(Inventory.variations))
        .all()
    )


    result = [Inventory.to_dict(item) for item in query]    

    return {
        "found": len(result)>0,
        "count": len(result),
        "items": result
    }

