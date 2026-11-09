from datetime import date
from decimal import Decimal, InvalidOperation

from sqlalchemy.orm import selectinload

from db.database import db
from db.models import (
    InventoryVariation,
    Order,
    OrderItem,
    Purchase,
    PurchaseItem,
)


CENT = Decimal("0.01")


def fifo_inventory_accounting():
    purchases = (
        Purchase.query.options(selectinload(Purchase.items))
        .order_by(Purchase.purchase_date, Purchase.id)
        .all()
    )
    layers_by_variation = {}
    for purchase in purchases:
        serialized_items = purchase.to_dict()["items"]
        for item, serialized in zip(purchase.items, serialized_items):
            if item.variation_id is None:
                continue
            layers_by_variation.setdefault(item.variation_id, []).append({
                "purchase_date": purchase.purchase_date,
                "remaining": item.quantity,
                "unit_cost": Decimal(str(serialized["actual_unit_cost"])),
            })

    order_items = (
        OrderItem.query.join(Order)
        .filter(Order.status.in_(("confirmed", "completed")))
        .order_by(Order.created_at, Order.id, OrderItem.id)
        .all()
    )
    costs = {}
    layer_positions = {}
    for order_item in order_items:
        sale_date = order_item.order.created_at.date()
        units_remaining = order_item.quantity
        total_cost = Decimal("0.00")
        layers = layers_by_variation.get(order_item.variation_id, [])
        layer_index = layer_positions.get(order_item.variation_id, 0)
        while units_remaining and layer_index < len(layers):
            layer = layers[layer_index]
            if layer["purchase_date"] > sale_date:
                break
            if layer["remaining"] <= 0:
                layer_index += 1
                continue
            allocated_quantity = min(units_remaining, layer["remaining"])
            total_cost += layer["unit_cost"] * allocated_quantity
            layer["remaining"] -= allocated_quantity
            units_remaining -= allocated_quantity
            if layer["remaining"] == 0:
                layer_index += 1
        layer_positions[order_item.variation_id] = layer_index
        costs[order_item.id] = {
            "cost": total_cost.quantize(CENT),
            "complete": units_remaining == 0,
        }
    remaining_cost_by_variation = {
        variation_id: sum(
            (
                layer["unit_cost"] * layer["remaining"]
                for layer in layers
            ),
            Decimal("0.00"),
        ).quantize(CENT)
        for variation_id, layers in layers_by_variation.items()
    }
    return costs, remaining_cost_by_variation


def fifo_costs_by_order_item():
    return fifo_inventory_accounting()[0]


def _money(value, field):
    try:
        amount = Decimal(str(value))
        rounded = amount.quantize(CENT)
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError(f"{field} must be a non-negative amount with at most 2 decimal places")

    if not amount.is_finite() or amount < 0 or rounded != amount or amount > Decimal("9999999999.99"):
        raise ValueError(f"{field} must be a non-negative amount with at most 2 decimal places")
    return amount


def _positive_integer(value, field):
    if isinstance(value, bool):
        raise ValueError(f"{field} must be a positive integer")
    try:
        result = int(value)
    except (TypeError, ValueError):
        raise ValueError(f"{field} must be a positive integer")
    if result <= 0 or str(value).strip() != str(result):
        raise ValueError(f"{field} must be a positive integer")
    return result


def create_purchase(data):
    if not isinstance(data, dict):
        raise ValueError("Request body must be a JSON object")

    raw_items = data.get("items")
    if not isinstance(raw_items, list) or not raw_items:
        raise ValueError("items must be a non-empty list")

    supplier = data.get("supplier")
    notes = data.get("notes")
    if supplier is not None and (not isinstance(supplier, str) or len(supplier) > 255):
        raise ValueError("supplier must be a string of at most 255 characters")
    if notes is not None and (not isinstance(notes, str) or len(notes) > 5000):
        raise ValueError("notes must be a string of at most 5000 characters")

    raw_purchase_date = data.get("purchase_date")
    try:
        purchase_date = (
            date.fromisoformat(raw_purchase_date)
            if raw_purchase_date is not None
            else date.today()
        )
    except (TypeError, ValueError):
        raise ValueError("purchase_date must use YYYY-MM-DD format")

    lines = []
    for index, raw_item in enumerate(raw_items):
        if not isinstance(raw_item, dict):
            raise ValueError(f"items[{index}] must be an object")

        variation_id = _positive_integer(
            raw_item.get("variation_id"),
            f"items[{index}].variation_id",
        )
        quantity = _positive_integer(
            raw_item.get("quantity"),
            f"items[{index}].quantity",
        )
        unit_cost = _money(raw_item.get("unit_cost"), f"items[{index}].unit_cost")
        variation = db.session.get(InventoryVariation, variation_id)
        if variation is None:
            raise ValueError(f"Inventory variation {variation_id} not found")
        lines.append((variation, quantity, unit_cost))

    purchase = Purchase(
        supplier=supplier.strip() if supplier else None,
        purchase_date=purchase_date,
        shipping_fees=_money(data.get("shipping_fees", 0), "shipping_fees"),
        other_fees=_money(data.get("other_fees", 0), "other_fees"),
        notes=notes.strip() if notes else None,
    )

    for variation, quantity, unit_cost in lines:
        purchase.items.append(PurchaseItem(
            variation=variation,
            inventory_name=variation.inventory.name,
            condition=variation.condition,
            size=variation.size,
            quantity=quantity,
            unit_cost=unit_cost,
            listed_price=variation.price,
        ))

    db.session.add(purchase)
    db.session.commit()
    return purchase


def list_purchases(start_date=None, end_date=None, limit=100, offset=0):
    query = Purchase.query.options(selectinload(Purchase.items))
    if start_date is not None:
        query = query.filter(Purchase.purchase_date >= start_date)
    if end_date is not None:
        query = query.filter(Purchase.purchase_date < end_date)
    return (
        query.order_by(Purchase.purchase_date.desc(), Purchase.id.desc())
        .limit(limit)
        .offset(offset)
        .all()
    )


def get_purchase(purchase_id):
    return (
        Purchase.query.options(selectinload(Purchase.items))
        .filter_by(id=purchase_id)
        .first()
    )
