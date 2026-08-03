from sqlalchemy import func
from db.models import Inventory, InventoryVariation
from db.database import db
import re
from difflib import SequenceMatcher
from sqlalchemy.orm import contains_eager, selectinload
from db.repository.promotion import active_promotion_prices

try:
    from rapidfuzz import fuzz
except ImportError:  # pragma: no cover - local fallback if rapidfuzz is unavailable
    fuzz = None



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

def is_variation_sellable(variation):
    status = (variation.status or "").lower()
    return (variation.stock or 0) > 0 and status not in ("sold", "unavailable", "inactive")


_variation_is_available = is_variation_sellable


def _catalog_item_to_dict(item, promotion=None, promotion_prices=None):
    data = Inventory.to_dict(item)
    promotion_prices = promotion_prices or {}
    for variation in data["variations"]:
        regular_price = variation["price"]
        promo_price = promotion_prices.get(variation["id"])
        variation.update({
            "effective_price": float(promo_price) if promo_price is not None else regular_price,
            "promo_price": float(promo_price) if promo_price is not None else None,
            "promotion_id": promotion.id if promo_price is not None and promotion else None,
            "is_on_promotion": promo_price is not None,
        })
    has_available_variation = any(
        _variation_is_available(variation)
        for variation in item.variations
    )
    data["is_sold"] = not has_available_variation
    data["availability_status"] = "sold" if data["is_sold"] else "available"
    return data


def get_public_catalog_inventory():
    promotion, promotion_prices = active_promotion_prices()
    items = (
        Inventory.query
        .options(selectinload(Inventory.variations))
        .all()
    )
    items = sorted(
        items,
        key=lambda item: (
            not any(
                _variation_is_available(variation)
                for variation in item.variations
            ),
            item.id,
        )
    )
    result = [
        _catalog_item_to_dict(item, promotion=promotion, promotion_prices=promotion_prices)
        for item in items
    ]
    return result


def get_all_available():
    items = (
        Inventory.query
        .join(InventoryVariation)
        .filter(
            InventoryVariation.stock > 0,
            ~func.lower(func.coalesce(InventoryVariation.status, "")).in_(
                ("sold", "unavailable", "inactive")
            ),
        )
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
            InventoryVariation.stock > 0,
            ~func.lower(func.coalesce(InventoryVariation.status, "")).in_(
                ("sold", "unavailable", "inactive")
            ),
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


def _normalize_text(value):
    return re.sub(r"[^a-z0-9]+", " ", str(value or "").lower()).strip()


def _normalize_size(value):
    if value is None:
        return ""
    text = str(value).lower().replace("us", "").strip()
    match = re.search(r"\d+(?:\.\d+)?", text)
    if not match:
        return text
    number = match.group(0)
    if "." in number:
        number = number.rstrip("0").rstrip(".")
    return number


def _name_score(query, candidate):
    query = _normalize_text(query)
    candidate = _normalize_text(candidate)
    if not query or not candidate:
        return 0
    if query in candidate:
        return 100
    if fuzz:
        return int(fuzz.partial_ratio(query, candidate))
    return int(SequenceMatcher(None, query, candidate).ratio() * 100)


def _available_variations(variations):
    return [
        variation
        for variation in variations
        if is_variation_sellable(variation)
    ]


def _item_with_variations(item, variations):
    data = Inventory.to_dict(item)
    data["variations"] = [variation.to_dict() for variation in variations]
    return data


def _matched_inventory_candidates(name, threshold=70):
    items = (
        Inventory.query
        .options(selectinload(Inventory.variations))
        .all()
    )
    matches = []
    for item in items:
        score = _name_score(name, item.name)
        if score >= threshold:
            reason = "exact" if _normalize_text(name) in _normalize_text(item.name) else "fuzzy"
            matches.append((score, reason, item))
    matches.sort(key=lambda row: (-row[0], row[2].id))
    return matches


def search_inventory_matches(name=None, size=None, limit=10):
    """
    Search inventory for sales inquiries and include fallback suggestions.
    Returns available exact size matches, same-item alternate sizes, and
    same-size alternate items without changing public API payload shape.
    """
    normalized_size = _normalize_size(size)
    matched_items = _matched_inventory_candidates(name) if name else []
    exact_items = []
    alternate_sizes = []
    same_size_items = []
    match_reason = None

    for score, reason, item in matched_items:
        available = _available_variations(item.variations)
        if not available:
            continue
        if match_reason is None:
            match_reason = reason

        if normalized_size:
            exact_variations = [
                variation
                for variation in available
                if _normalize_size(variation.size) == normalized_size
            ]
            if exact_variations:
                exact_items.append(_item_with_variations(item, exact_variations))
            elif not exact_items:
                alternate_sizes.append(_item_with_variations(item, available))
        else:
            exact_items.append(_item_with_variations(item, available))

        if len(exact_items) >= limit:
            break

    if normalized_size and not exact_items:
        all_items = (
            Inventory.query
            .join(InventoryVariation)
            .filter(
                InventoryVariation.stock > 0,
                ~func.lower(func.coalesce(InventoryVariation.status, "")).in_(
                    ("sold", "unavailable", "inactive")
                ),
            )
            .options(contains_eager(Inventory.variations))
            .all()
        )
        for item in all_items:
            variations = [
                variation
                for variation in item.variations
                if is_variation_sellable(variation)
                and _normalize_size(variation.size) == normalized_size
            ]
            if variations:
                same_size_items.append(_item_with_variations(item, variations))
            if len(same_size_items) >= limit:
                break

    return {
        "found": len(exact_items) > 0,
        "count": len(exact_items),
        "items": exact_items[:limit],
        "match_reason": match_reason,
        "alternate_sizes": alternate_sizes[:limit],
        "same_size_items": same_size_items[:limit],
    }

def get_inventory_with_size(name, size):
    return search_inventory_matches(name=name, size=size)

def get_all_available_inventory(page=1):
    per_page=10
    offset = (page - 1) * per_page

    query = (
        Inventory.query
        .join(InventoryVariation)
        .filter(
            InventoryVariation.stock > 0,
            ~func.lower(func.coalesce(InventoryVariation.status, "")).in_(
                ("sold", "unavailable", "inactive")
            ),
        )
        .options(contains_eager(Inventory.variations))
        .order_by(Inventory.id, InventoryVariation.id)
        .limit(per_page)
        .offset(offset)
        .all()
    )


    result = [Inventory.to_dict(item) for item in query]

    total = (
        db.session.query(func.count(Inventory.id))
        .join(InventoryVariation)
        .filter(
            InventoryVariation.stock > 0,
            ~func.lower(func.coalesce(InventoryVariation.status, "")).in_(
                ("sold", "unavailable", "inactive")
            ),
        )
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
