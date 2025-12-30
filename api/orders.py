from flask import Blueprint, request, jsonify
from db.database import db
from db.models import Order
from db.repository.order import save_order, get_order, get_all_pending_orders, update_order
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

@orders_bp.route("orders/get-all-pending", methods=["GET"])
@admin_required(allowed_roles=["super_admin"])
def pending_orders():
    pending_orders = get_all_pending_orders()
    return pending_orders

@orders_bp.route("orders/update-status", methods=["POST"])
@admin_required(allowed_roles=["super_admin"])
def update():
    data = request.json
    status = data.get("status")
    order_id = data.get("order_id")
    received_payment = data.get("received_payment")
    cancel_reason = data.get("cancel_reason")
    if not order_id or  not status:
        return jsonify({"message": "order_id & status  is required"}),422
    
    order = update_order(order_id, status, received_payment, cancel_reason)
    return order


