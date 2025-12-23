from flask import Blueprint, request, jsonify
from db.database import db
from db.models import Order
from db.repository.order import save_order, get_order
from middleware.admin_required import admin_required

orders_bp = Blueprint("orders", __name__)

@orders_bp.route("/save-order", methods=["POST"])
@admin_required(allowed_roles=["super_admin"])
def create_order():
    data = request.json
    save_order(data)
    return jsonify({"status": "ok", "order": data})

@orders_bp.route("get-order", methods=["GET"])
@admin_required(allowed_roles=["super_admin"])
def get_order_by_senderid():
    sender_id= request.args.get('sender_id')
    order = get_order(sender_id)
    return order

@orders_bp.route("/orders/<int:order_id>", methods=["PUT"])
@admin_required(allowed_roles=["super_admin"])
def update_order(order_id):
    order = Order.query.get_or_404(order_id)
    data = request.json or {}

    # Allowed fields
    editable_fields = {
        "status"
    }

    for field, value in data.items():
        if field in editable_fields:
            setattr(order, field, value)

    db.session.commit()

    return jsonify({"message": "Order updated", "order_id": order.id})


@orders_bp.route("/orders/<int:order_id>", methods=["DELETE"])
@admin_required(allowed_roles=["super_admin"])
def delete_order(order_id):
    order = Order.query.get_or_404(order_id)

    # Free up inventory if needed
    inv = order.inventory_item
    if inv.status in ["reserved", "sold"]:
        inv.status = "available"

    db.session.delete(order)
    db.session.commit()

    return jsonify({"message": "Order deleted"})
