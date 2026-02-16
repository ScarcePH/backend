from flask import Blueprint, request, jsonify
from datetime import timedelta
from db.database import db
from db.models import Shipment, Order
from db.repository.order import save_order, get_order, get_order_by_status, update_order
from middleware.auth_required import auth_required
from db.repository.checkout import start_checkout, approve_checkout_session
from task.email import enqueue_email
from bot.services.messenger import send_carousel
from bot.core.constants import TRACK


orders_bp = Blueprint("orders", __name__)

@orders_bp.route("/save-order", methods=["POST"])
@auth_required(allowed_roles=["super_admin"])
def create_order():
    data = request.json
    items = [
        {
            "inventory_id": data["inventory_id"],
            "variation_id": data["variation_id"],
            "qty": 1
        }
    ]
    result = start_checkout(
            customer_id=data["customer_id"],
            items=items
    )

    if isinstance(result, tuple):
        payload, status_code = result
        return jsonify(payload), status_code

    approve_result, approve_status_code = approve_checkout_session(result["checkout_session_id"], received_amount=data['received_amount'])
    if approve_status_code != 200:
        return jsonify(approve_result), approve_status_code

    session = approve_result.get("session")
    return jsonify({
        "message": "Order created!",
        "checkout_session_id": result["checkout_session_id"],
        "order": approve_result.get("order"),
        "status": session.status if session else "approved"
    }), 200

    try:
        result = start_checkout(
            customer_id=data["customer_id"],
            items=items
        )

        if isinstance(result, tuple):
            payload, status_code = result
            return jsonify(payload), status_code

        approve_result, approve_status_code = approve_checkout_session(result["checkout_session_id"], received_amount=data['received_amount'])
        if approve_status_code != 200:
            return jsonify(approve_result), approve_status_code

        session = approve_result.get("session")
        return jsonify({
            "message": "Order created!",
            "checkout_session_id": result["checkout_session_id"],
            "order": approve_result.get("order"),
            "status": session.status if session else "approved"
        }), 200
    except Exception as exc:
        db.session.rollback()
        return jsonify({
            "message": f"Failed to create order: {exc}",
        }), 400

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

@orders_bp.route("orders/add-shipment", methods=["POST"])
@auth_required(allowed_roles=["super_admin"])
def add_shipment():
    data = request.json or {}
    order_id = data.get("order_id")

    if not order_id:
        return jsonify({"message": "order_id is required"}), 422

    order = Order.query.get(order_id)
    if not order:
        return jsonify({"message": "Order not found"}), 404

    shipment = Shipment.query.filter_by(order_id=order_id).first()
    is_new = shipment is None

    if is_new:
        shipment = Shipment(order_id=order_id)
        db.session.add(shipment)

    for field in ["carrier", "tracking", "status"]:
        if field in data:
            setattr(shipment, field, data.get(field))

    db.session.commit()

    refreshed_order = Order.query.get(order_id)
    order_payload = refreshed_order.to_dict() if refreshed_order else None
    customer = refreshed_order.customer if refreshed_order else None

    if customer and customer.email:
        normalized_status = (shipment.status or "").replace("_", "").replace(" ", "").lower()
        status_message = data.get("status_message")
        if normalized_status == "intransit":
            status_message = "Your order is currently in transit. You can track its progress using the details below."
        elif normalized_status == "delivered":
            status_message = "Your order has been successfully delivered. We hope you enjoy your purchase."

        estimated_delivery = None
        if shipment.created_at:
            estimated_delivery = (shipment.created_at + timedelta(days=10)).date().isoformat()

        email_items = []
        for item in (order_payload.get("items") if order_payload else []) or []:
            inventory = item.get("inventory") or {}
            variation = item.get("variation") or {}
            email_items.append({
                "image_url": inventory.get("image"),
                "name": inventory.get("name") or "Item",
                "category": variation.get("condition"),
                "size": f"{variation.get('size')}us" if variation.get("size") else None,
                "price": str(item.get("price"))
                if item.get("price") is not None
                else None,
            })

        email_payload = {
            "type": "shipment_update",
            "to": customer.email,
            "template_variables": {
                "shipment_status": shipment.status,
                "customer_name": customer.name if customer.name else "Customer",
                "status_message": status_message,
                "courier_name": shipment.carrier,
                "tracking_number": shipment.tracking,
                "estimated_delivery": estimated_delivery,
                "tracking_url": TRACK+shipment.tracking,
                "items": email_items,
                "year": "2024",
                "store_name": "Scarceᴾᴴ",
            },
        }
        enqueue_email(email_payload)

    if customer and customer.sender_id and order_payload:
        send_carousel(customer.sender_id, [order_payload], is_my_order=True)

    return jsonify({
        "message": "Shipment created" if is_new else "Shipment updated",
        "shipment": shipment.to_dict()
    }), 200
