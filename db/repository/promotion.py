from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from sqlalchemy.orm import selectinload

from db.models.promotion import Promotion
from db.models.promotion_item import PromotionItem
from db.models.inventory_variation import InventoryVariation


MANILA_TZ = ZoneInfo("Asia/Manila")


def manila_now():
    return datetime.now(MANILA_TZ)


def manila_today():
    return manila_now().date()


def promotion_status(promotion, today=None):
    today = today or manila_today()
    if promotion.early_ended_at is not None or today > promotion.end_date:
        return "ended"
    if today < promotion.start_date:
        return "scheduled"
    return "active"


def get_active_promotion(today=None):
    today = today or manila_today()
    return (
        Promotion.query
        .options(selectinload(Promotion.items).joinedload(PromotionItem.variation))
        .filter(
            Promotion.early_ended_at.is_(None),
            Promotion.start_date <= today,
            Promotion.end_date >= today,
        )
        .order_by(Promotion.start_date, Promotion.id)
        .first()
    )


def active_promotion_prices(today=None):
    promotion = get_active_promotion(today=today)
    if not promotion:
        return None, {}
    return promotion, {
        item.variation_id: Decimal(str(item.promo_price))
        for item in promotion.items
    }


def effective_price_for_variation(variation, prices=None, today=None):
    promotion = None
    if prices is None:
        promotion, prices = active_promotion_prices(today=today)
    promo_price = prices.get(variation.id)
    return promo_price if promo_price is not None else Decimal(str(variation.price)), promotion


def serialize_promotion(promotion, include_products=True, today=None):
    data = {
        "id": promotion.id,
        "name": promotion.name,
        "description": promotion.description,
        "start_date": promotion.start_date.isoformat(),
        "end_date": promotion.end_date.isoformat(),
        "early_ended_at": (
            promotion.early_ended_at.isoformat() if promotion.early_ended_at else None
        ),
        "status": promotion_status(promotion, today=today),
        "created_at": promotion.created_at.isoformat() if promotion.created_at else None,
        "updated_at": promotion.updated_at.isoformat() if promotion.updated_at else None,
        "items": [],
    }
    for item in promotion.items:
        variation = item.variation
        line = {
            "id": item.id,
            "variation_id": item.variation_id,
            "promo_price": float(item.promo_price),
            "regular_price": float(variation.price) if variation else None,
        }
        if include_products and variation:
            line.update({
                "inventory_id": variation.inventory_id,
                "inventory_name": variation.inventory.name,
                "inventory_image": variation.inventory.image,
                "size": variation.size,
                "condition": variation.condition,
                "status": variation.status,
                "stock": variation.stock,
            })
        data["items"].append(line)
    return data


def promotion_query():
    return Promotion.query.options(
        selectinload(Promotion.items)
        .joinedload(PromotionItem.variation)
        .joinedload(InventoryVariation.inventory)
    )
