from flask import Blueprint, request, jsonify
from db.database import db
from db.models import Order
from db.repository.order import save_order, get_order, get_all_order, update_order, get_all_confirmed_orders
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

@orders_bp.route("orders/get-all", methods=["GET"])
@admin_required(allowed_roles=["super_admin"])
def pending_orders():
    status = request.args.get('status')
    if(not status):
       return jsonify({"message": "url param status required"}),422 
    
    date_from = request.args.get("from")
    date_to = request.args.get("to")


    pending_orders = get_all_order(status, date_from, date_to)
    return pending_orders


@orders_bp.route("orders/get-all-confirmed", methods=["GET"])
@admin_required(allowed_roles=["super_admin"])
def get_all():
    pending_orders = get_all_confirmed_orders()
    return pending_orders

@orders_bp.route("orders/update-status", methods=["POST"])
@admin_required(allowed_roles=["super_admin"])
def update():
    data = request.json
    status = data.get("status")
    order_id = data.get("order_id")
    received_payment = data.get("received_payment")
    cancel_reason = data.get("cancel_reason")
    release = data.get("release")
    if not order_id or  not status:
        return jsonify({"message": "order_id & status  is required"}),422
    
    order = update_order(order_id, status, received_payment, cancel_reason, release)
    return order


