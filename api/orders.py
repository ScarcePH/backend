from flask import Blueprint, request, jsonify
from db.database import db
from db.models import Order

orders_bp = Blueprint("orders", __name__)

@orders_bp.route("/orders", methods=["POST"])
def create_order():
    data = request.json
    order = Order(**data)
    db.session.add(order)
    db.session.commit()
    return jsonify({"status": "ok", "order": data})

@orders_bp.route("/orders/<int:order_id>", methods=["PUT"])
def update_order(order_id):
    order = Order.query.get_or_404(order_id)
    data = request.json or {}

    # Allowed fields
    editable_fields = {
        "payment_method",
        "payment_reference",
        "payment_verified",
        "status"
    }

    for field, value in data.items():
        if field in editable_fields:
            setattr(order, field, value)

    # BUSINESS LOGIC: inventory status must follow order status
    if "status" in data:
        inv = order.inventory_item

        if data["status"] == "pending":
            inv.status = "reserved"

        elif data["status"] == "confirmed":
            inv.status = "sold"

        elif data["status"] == "cancelled":
            inv.status = "available"

    db.session.commit()

    return jsonify({"message": "Order updated", "order_id": order.id})


@orders_bp.route("/orders/<int:order_id>", methods=["DELETE"])
def delete_order(order_id):
    order = Order.query.get_or_404(order_id)

    # Free up inventory if needed
    inv = order.inventory_item
    if inv.status in ["reserved", "sold"]:
        inv.status = "available"

    db.session.delete(order)
    db.session.commit()

    return jsonify({"message": "Order deleted"})
