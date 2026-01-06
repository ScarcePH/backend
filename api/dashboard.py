from flask import Blueprint, jsonify
from middleware.admin_required import admin_required
from db.repository.dashboard import dashboard_summary
from db.database import db
from db.models import Inventory, InventoryVariation
from sqlalchemy import func
from collections import defaultdict



dashboard_bp = Blueprint("dashboard", __name__)

@dashboard_bp.route("/dashboard/summary")
@admin_required()
def summary_cards():
    return dashboard_summary()

@dashboard_bp.route("/dashboard/bestseller")
@admin_required()
def best_selling():
    top_inventory = (
        db.session.query(
            Inventory.id.label("inventory_id"),
            Inventory.name.label("inventory_name"),
            Inventory.image.label("image"),
            InventoryVariation.size.label("size"),
            func.count(InventoryVariation.id).label("sold_count"),
            func.coalesce(
                func.sum(InventoryVariation.price), 0
            ).label("revenue"),
        )
        .join(
            InventoryVariation,
            InventoryVariation.inventory_id == Inventory.id
        )
        .filter(
            InventoryVariation.status == "sold"
        )
        .group_by(
            Inventory.id,
            Inventory.name,
            Inventory.image,
            InventoryVariation.size
        )
        .order_by(
            func.sum(InventoryVariation.price).desc()
        )
        .limit(5)
        .all()
    )


    grouped = defaultdict(lambda: {
        "inventory_id": None,
        "name": None,
        "sizes": []
    })

    for row in top_inventory:
        item = grouped[row.inventory_id]
        item["inventory_id"] = row.inventory_id
        item["name"] = row.inventory_name
        item['image'] = row.image
        item["sizes"].append({
            "size": row.size,
            "sold_count": row.sold_count,
            "revenue": row.revenue,
        })

    return jsonify(list(grouped.values()))


