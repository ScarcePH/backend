from flask import Blueprint, jsonify, request
from middleware.auth_required import auth_required
from db.repository.dashboard import dashboard_summary, income_statement, last_3_months_cc_statement, purchase_statement
from db.database import db
from db.models import Inventory, InventoryVariation
from sqlalchemy import func
from collections import defaultdict
from db.repository.dashboard import last_6_months_sale_bar_chart




dashboard_bp = Blueprint("dashboard", __name__)

@dashboard_bp.route("/dashboard/summary", methods=["GET"])
@auth_required(allowed_roles=["super_admin"])
def summary_cards():
    return dashboard_summary()

@dashboard_bp.route("/dashboard/sales-bar-chart", methods=["GET"])
@auth_required(allowed_roles=["super_admin"])
def bar_chart():
    return last_6_months_sale_bar_chart()

@dashboard_bp.route("/dashboard/cc-statement", methods=["GET"])
@auth_required(allowed_roles=["super_admin"])
def cc_statement():
    return last_3_months_cc_statement()

@dashboard_bp.route("/dashboard/purchase-statement", methods=["GET"])
@auth_required(allowed_roles=["super_admin"])
def purchase_statement_route():
    start_date = request.args.get("start_date")
    end_date = request.args.get("end_date")
    return purchase_statement(start_date, end_date)

@dashboard_bp.route("/dashboard/income-statement", methods=["GET"])
@auth_required(allowed_roles=["super_admin"])
def income_statement_route():
    start_date = request.args.get("start_date")
    end_date = request.args.get("end_date")
    return income_statement(start_date, end_date)

@dashboard_bp.route("/dashboard/bestseller", methods=["GET"])
@auth_required(allowed_roles=["super_admin"])
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
        .all()
    )


    grouped = defaultdict(lambda: {
        "inventory_id": None,
        "inventory_name": None,
        "total_sold": 0,
        "total_revenue": 0,
        "sizes": [],
    })

    for row in top_inventory:
        item = grouped[row.inventory_id]

        item["inventory_id"] = row.inventory_id
        item["inventory_name"] = row.inventory_name
        item['image'] = row.image

        item["sizes"].append({
            "size": row.size,
            "sold_count": row.sold_count,
            "revenue": row.revenue,
        })

        item["total_sold"] += row.sold_count
        item["total_revenue"] += row.revenue

        
    result = sorted(
        grouped.values(),
        key=lambda x: x["total_revenue"],
        reverse=True
    )[:6]

    return jsonify(result)
