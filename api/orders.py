from flask import Blueprint, request, jsonify
from db.database import db
from db.models import Order
from db.repository.order import save_order, get_order, get_order_by_status, update_order
from middleware.auth_required import auth_required
from services.ocr.ocr_service import ocr_is_valid_payment_today


orders_bp = Blueprint("orders", __name__)

@orders_bp.route("/save-order", methods=["POST"])
@auth_required(allowed_roles=["super_admin"])
def create_order():
    data = request.json
    order = save_order(data)
    return jsonify({"status": "ok", "order": order})

@orders_bp.route("get-order", methods=["GET"])
@auth_required(allowed_roles=["super_admin"])
def get_order_by_senderid():
    sender_id= request.args.get('sender_id')
    order = get_order(sender_id)
    return order

@orders_bp.route("orders/get-all", methods=["GET"])
@auth_required(allowed_roles=["super_admin"])
def get_order_status():
    status = request.args.get('status')
    if(not status):
       return jsonify({"message": "url param status required"}),422 
    
    date_from = request.args.get("from")
    date_to = request.args.get("to")


    pending_orders = get_order_by_status(status, date_from, date_to)
    return pending_orders


@orders_bp.route("orders/update-status", methods=["POST"])
@auth_required(allowed_roles=["super_admin"])
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



@orders_bp.route("/upload-proof", methods=["POST"])
def upload_proof():
    file = request.files["image"]
    result = ocr_is_valid_payment_today(file.read())
    return jsonify(result)


@orders_bp.route("/test-only", methods=["GET"])
def testonly():
    return "WORKING"