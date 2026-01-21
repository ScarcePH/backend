from sqlalchemy import func
from db.models import Inventory, InventoryVariation
from db.database import db
import re
from sqlalchemy.orm import contains_eager



def save_inventory(data: dict):

    inventory_id = data.get("id")

    if inventory_id:
        inventory = Inventory.query.get(inventory_id)

        if not inventory:
            raise ValueError("Inventory not found")

        for key, value in data.items():
            if key != "id":
                setattr(inventory, key, value)

    else:
        inventory = Inventory(**data)
        db.session.add(inventory)

    db.session.commit()

    return Inventory.to_dict(inventory)


def save_variations(inventory_id: int, variations: list[dict]):
  

    existing_variations = (
        InventoryVariation.query
        .filter_by(inventory_id=inventory_id)
        .all()
    )

    existing_map = {v.id: v for v in existing_variations}

    incoming_ids = set()
    
    for data in variations:
        variation_id = data.get("id")

        if variation_id and variation_id in existing_map:
            variation = existing_map[variation_id]
            incoming_ids.add(variation_id)

            for key, value in data.items():
                if key != "id":
                    setattr(variation, key, value)

        else:
            variation = InventoryVariation(
                inventory_id=inventory_id,
                **{k: v for k, v in data.items() if k != "id"}
            )
            db.session.add(variation)

    for variation in existing_variations:
        if variation.id not in incoming_ids:
            db.session.delete(variation)

    db.session.commit()

    res = InventoryVariation.query.filter_by(inventory_id=inventory_id).all()
    res = [InventoryVariation.to_dict(item) for item in res]    
    return res


def get_all_inventory():
    items = Inventory.query.all()
    result = [Inventory.to_dict(item) for item in items]
    return result

def get_all_available():
    items = (
        Inventory.query
        .join(InventoryVariation)
        .filter(InventoryVariation.status != "sold")
        .options(contains_eager(Inventory.variations))
        .all()
    )
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

def get_all_available_inventory(page=1):
    per_page=10
    offset = (page - 1) * per_page

    query = (
        Inventory.query
        .join(InventoryVariation)
        .filter(InventoryVariation.status != "sold")
        .options(contains_eager(Inventory.variations))
        .limit(per_page)
        .offset(offset)
        .all()
    )


    result = [Inventory.to_dict(item) for item in query]

    total = (
        db.session.query(func.count(Inventory.id))
        .join(InventoryVariation)
        .filter(InventoryVariation.status != "sold")
        .scalar()
    )

    has_next = page * per_page < total
    has_prev = page > 1

    buttons = []

    if has_prev:
        buttons.append({
            "content_type":"text",
            "title": "⬅ Previous",
            "payload": f"PAGE_{page-1}"
        })

    if has_next:
        buttons.append({
            "content_type":"text",
            "title": "Next ➡",
            "payload": f"PAGE_{page+1}"
        })

    return {
        "found": len(result)>0,
        "count": len(result),
        "items": result,
        "quick_replies": buttons

    }

