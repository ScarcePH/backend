from flask import request, jsonify, Blueprint, url_for, make_response
from db.models import CheckoutSession, Inventory, Customers, InventoryVariation, Cart, User
from db.database import db
from api.helpers.cart import get_active_cart, get_current_customer_context
from middleware.auth_required import auth_required
from db.repository.checkout import (
    start_checkout as start_checkout_repo,
    approve_checkout_session as approve_checkout_session_repo,
    reject_checkout_session as reject_checkout_session_repo,
)
from services.image.upload import upload
from db.repository.customer_service import get_or_create_customer
import io
import time
import random
import os
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from datetime import datetime
from db.repository.ocr_job import ocr_job
from db.models.ocrjob import OCRJob
from task.email import enqueue_email





checkout_bp = Blueprint("checkout", __name__)


def _get_admin_serializer():
    secret = os.environ.get("JWT_SECRET_KEY") or "dev-secret"
    return URLSafeTimedSerializer(secret, salt="admin-order-approval")


def _build_admin_action_urls(session_id: str):
    serializer = _get_admin_serializer()
    approve_token = serializer.dumps({
        "session_id": session_id,
        "action": "approve"
    })
    decline_token = serializer.dumps({
        "session_id": session_id,
        "action": "decline"
    })
    approve_url = url_for(
        "checkout.admin_approve_via_email",
        token=approve_token,
        _external=True
    )
    decline_url = url_for(
        "checkout.admin_decline_via_email",
        token=decline_token,
        _external=True
    )
    return approve_url, decline_url


def _html_response(title: str, message: str, status_code: int = 200):
    html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title}</title>
  <style>
    body {{
      font-family: Arial, sans-serif;
      background: #f7f7f7;
      color: #111;
      margin: 0;
      padding: 40px 16px;
    }}
    .card {{
      max-width: 520px;
      margin: 0 auto;
      background: #fff;
      border-radius: 12px;
      padding: 24px;
      box-shadow: 0 6px 20px rgba(0,0,0,0.08);
    }}
    h1 {{
      margin: 0 0 8px;
      font-size: 20px;
    }}
    p {{
      margin: 0;
      font-size: 14px;
      line-height: 1.5;
    }}
  </style>
</head>
<body>
  <div class="card">
    <h1>{title}</h1>
    <p>{message}</p>
  </div>
</body>
</html>"""
    response = make_response(html, status_code)
    response.headers["Content-Type"] = "text/html; charset=utf-8"
    return response


@checkout_bp.route("/checkout/start", methods=["POST"])
def start_checkout():
    data = request.json
    ctx = get_current_customer_context()


    source = data.get("source")  

    if source == "cart":
        cart =  get_active_cart(user_id=ctx["user_id"], guest_id=ctx["guest_id"])
        items = [
            {
                "inventory_id": item.inventory_id,
                "variation_id": item.variation_id,
                "qty": item.quantity
            }
            for item in cart.items
        ]

    else:
        items = data.get("items")

    if not items:
        return jsonify({"error": "No items"}), 400
    
     
    result = start_checkout_repo(
        items=items,
        user_id=ctx["user_id"],
        guest_id=ctx["guest_id"]
    )

    if isinstance(result, tuple):
        return result
    
   

    response =  jsonify(result)


    response.set_cookie("guest_id", ctx["guest_id"], max_age=60*60*24*30)
    return response




@checkout_bp.route("/checkout/submit-proof", methods=["POST"])
def submit_checkout_proof():
    session_id = (
        request.form.get("checkout_session_id")
        or request.form.get("id")
        or request.args.get("checkout_session_id")
        or request.args.get("id")
    )
    file = request.files.get("file") or request.files.get("image")

    if not session_id:
        return jsonify({"message": "checkout_session_id is required"}), 422

    if not file:
        return jsonify({"message": "file is required"}), 422

    ctx = get_current_customer_context()
    customer = None

    if ctx.get("user_id"):
        customer = Customers.query.filter_by(user_id=ctx["user_id"]).first()
    elif ctx.get("guest_id"):
        customer = Customers.query.filter_by(guest_id=ctx["guest_id"]).first()

    if not customer:
        return jsonify({"message": "Customer not found"}), 404

    session = CheckoutSession.query.get_or_404(session_id)

    if session.customer_id != customer.id:
        return jsonify({"message": "Unauthorized checkout session"}), 403

    if session.is_expired():
        session.status = "expired"
        db.session.commit()
        return jsonify({
            "message": "Checkout session expired",
            "id": str(session.id),
            "status": session.status
        }), 400

    raw = file.stream.read()
    upload_buf = io.BytesIO(raw)

    ext = os.path.splitext(file.filename)[1]
    new_filename = f"{int(time.time())}_{random.randint(1000,9999)}{ext}"

    proof_url = upload(
        file=upload_buf,
        filename=new_filename,
        content_type=file.content_type,
        subfolder="proofs"
    )
    job_info = ocr_job(raw, new_filename, file.content_type)
  

    try:
        session.submit_proof(proof_url)
    except ValueError as exc:
        return jsonify({
            "message": str(exc),
            "id": str(session.id),
            "status": session.status
        }), 400

    db.session.commit()

    return jsonify({
        "message": "Payment proof submitted",
        "id": str(session.id),
        "status": session.status,
        "proof_image_url": session.proof_image_url,
        "payment_queue": job_info["job_id"]

    })

@checkout_bp.route("/payment/status/<job_id>/<checkout_session_id>", methods=["GET"])
def ocr_status(job_id,checkout_session_id):

    job = OCRJob.query.get_or_404(job_id)
    session = CheckoutSession.query.get_or_404(checkout_session_id)
    if job.status == "DONE" and job.result:
        customer = session.customer
        customer_email = customer.email if customer else None

        if customer_email:
            items = []
            for item in session.items_json or []:
                inventory = Inventory.query.get(item.get("inventory_id"))
                variation = InventoryVariation.query.get(item["variation_id"])
                items.append({
                    "name": inventory.name if inventory else "Item",
                    "qty": item.get("qty", 1),
                    "price": str(variation.price),
                    "image_url": inventory.image,
                    "condition":variation.condition,
                    "size": variation.size+"us"
                })

            payload = {
                "type": "validate_payment",
                "to": customer_email,
                "template_variables": {
                    "customer_name": (customer.name if customer and customer.name else "Customer"),
                    "order_id": str(session.orders.id) if session.orders else str(session.id),
                    "total": float(session.total_price) if session.total_price is not None else None,
                    "validation_eta": "10-30 mins",
                    "store_name": "Scarceᴾᴴ",
                    "support_email": "Facebook.com/scarceph",
                    "year": "enqueue_email",
                    "items": items
                }
            }

            enqueue_email(payload)

        admin_email = User.query.filter_by(role="super_admin").first().email
        if admin_email:
            admin_items = []
            for item in session.items_json or []:
                inventory = Inventory.query.get(item.get("inventory_id"))
                variation = InventoryVariation.query.get(item["variation_id"])
                admin_items.append({
                    "name": inventory.name if inventory else "Item",
                    "size": f"{variation.size}us" if variation and variation.size else None,
                    "price": str(variation.price) if variation and variation.price is not None else None
                })

            approve_url, decline_url = _build_admin_action_urls(str(session.id))
            admin_payload = {
                "type": "admin_order_notification",
                "to": admin_email,
                "template_variables": {
                    "order_id": str(session.orders.id) if session.orders else str(session.id),
                    "customer_name": customer.name if customer and customer.name else "Customer",
                    "customer_phone": customer.phone if customer else None,
                    "customer_address": customer.address if customer else None,
                    "items": admin_items,
                    "total": str(session.total_price) if session.total_price is not None else None,
                    "payment_ss": session.proof_image_url,
                    "approve_url": approve_url,
                    "decline_url": decline_url
                }
            }
            enqueue_email(admin_payload)

        owner_cart = None
        if customer:
            if customer.user_id:
                owner_cart = Cart.query.filter_by(user_id=customer.user_id, is_active=True).first()
            elif customer.guest_id:
                owner_cart = Cart.query.filter_by(guest_id=customer.guest_id, is_active=True).first()

        if owner_cart:
            db.session.delete(owner_cart)
            db.session.commit()

    

    return jsonify({
        "status": job.status,
        "result": job.result
    })



@checkout_bp.route("/checkout/pending-approval", methods=["GET"])
@auth_required(allowed_roles=["super_admin"])
def get_pending_checkout_approvals():
    sessions = (
        CheckoutSession.query
        .filter(CheckoutSession.status == "proof_submitted")
        .order_by(CheckoutSession.created_at.asc())
        .all()
    )

    return jsonify([
        {
            "id": str(session.id),
            "customer_id": session.customer_id,
            "items": hydrate_checkout_items(session.items_json),
            "total_price": float(session.total_price),
            "proof_image_url": session.proof_image_url,
            "created_at": session.created_at.isoformat(),
            "expires_at": session.expires_at.isoformat()
        }
        for session in sessions
    ])


@checkout_bp.route("/checkout/session", methods=["GET"])
def get_checkout_session_by_id():
    session_id = (
        request.args.get("checkout_session_id")
        or request.args.get("id")
        or request.args.get("session_id")
    )

    if not session_id:
        return jsonify({"message": "checkout_session_id is required"}), 422

    ctx = get_current_customer_context()
    customer = get_or_create_customer(user_id=ctx["user_id"], guest_id=ctx["guest_id"])


    print('customer',customer)
    if not customer:
        return jsonify({"message": "Customer not found"}), 404

    session = CheckoutSession.query.get_or_404(session_id)

    if session.customer_id != customer.id:
        return jsonify({"message": "Unauthorized checkout session"}), 403

    if session.is_expired() :
        session.status = "expired"
        db.session.commit()
        return jsonify({"message":"Session Expired."}), 404

    return jsonify({
        "id": str(session.id),
        "customer_id": session.customer_id,
        "items": hydrate_checkout_items(session.items_json),
        "total_price": float(session.total_price),
        "status": session.status,
        "proof_image_url": session.proof_image_url,
        "created_at": session.created_at.isoformat(),
        "expires_at": session.expires_at.isoformat()
    })



def hydrate_checkout_items(items_json):
    hydrated = []

    for item in items_json:
        inventory = Inventory.query.get(item["inventory_id"])

        hydrated.append({
            "inventory_id": item["inventory_id"],
            "variation_id": item["variation_id"],
            "qty": item["qty"],
            "price": item["price"], 
            "inventory": inventory.to_dict() if inventory else None,
        })

    return hydrated


@checkout_bp.route("/checkout/approve", methods=["POST"])
@auth_required(allowed_roles=["super_admin"])
def approve_checkout_session():
    data = request.json or {}
    session_id = data.get("checkout_session_id") or data.get("id")

    if not session_id:
        return jsonify({"message": "checkout_session_id is required"}), 422

    result, status_code = approve_checkout_session_repo(session_id)
    if status_code != 200:
        return jsonify(result), status_code

    session = result["session"]
    order = result["order"]

    return jsonify({
        "message": "Checkout session approved",
        "id": str(session.id),
        "status": session.status,
        "order": order
    })


@checkout_bp.route("/checkout/reject", methods=["POST"])
@auth_required(allowed_roles=["super_admin"])
def reject_checkout_session():
    data = request.json or {}
    session_id = data.get("checkout_session_id") or data.get("id")
    reject_reason = data.get("reason")

    if not session_id:
        return jsonify({"message": "checkout_session_id is required"}), 422

    result, status_code = reject_checkout_session_repo(session_id, reject_reason=reject_reason)
    if status_code != 200:
        return jsonify(result), status_code

    session = result["session"]

    return jsonify({
        "message": "Checkout session rejected",
        "id": str(session.id),
        "status": session.status
    })


@checkout_bp.route("/checkout/admin-approve", methods=["GET"])
def admin_approve_via_email():
    token = request.args.get("token")
    if not token:
        return _html_response("Missing token", "The approval link is missing a token.", 422)

    serializer = _get_admin_serializer()
    try:
        payload = serializer.loads(token, max_age=604800)
    except SignatureExpired:
        return _html_response("Link expired", "This approval link has expired.", 400)
    except BadSignature:
        return _html_response("Invalid link", "This approval link is invalid.", 400)

    if payload.get("action") != "approve":
        return _html_response("Invalid link", "This approval link is invalid.", 400)

    session_id = payload.get("session_id")
    if not session_id:
        return _html_response("Invalid link", "This approval link is invalid.", 400)

    result, status_code = approve_checkout_session_repo(session_id)
    if status_code != 200:
        message = result.get("message") if isinstance(result, dict) else "Unable to approve this order."
        return _html_response("Approval failed", message, status_code)

    session = result["session"]
    return _html_response(
        "Order approved",
        f"Checkout session {session.id} has been approved."
    )


@checkout_bp.route("/checkout/admin-decline", methods=["GET"])
def admin_decline_via_email():
    token = request.args.get("token")
    if not token:
        return _html_response("Missing token", "The decline link is missing a token.", 422)

    serializer = _get_admin_serializer()
    try:
        payload = serializer.loads(token, max_age=604800)
    except SignatureExpired:
        return _html_response("Link expired", "This decline link has expired.", 400)
    except BadSignature:
        return _html_response("Invalid link", "This decline link is invalid.", 400)

    if payload.get("action") != "decline":
        return _html_response("Invalid link", "This decline link is invalid.", 400)

    session_id = payload.get("session_id")
    if not session_id:
        return _html_response("Invalid link", "This decline link is invalid.", 400)

    result, status_code = reject_checkout_session_repo(session_id, reject_reason="Declined by admin")
    if status_code != 200:
        message = result.get("message") if isinstance(result, dict) else "Unable to decline this order."
        return _html_response("Decline failed", message, status_code)

    session = result["session"]
    return _html_response(
        "Order declined",
        f"Checkout session {session.id} has been declined."
    )


@checkout_bp.route("/checkout/save-customer", methods=["POST"])
def save_checkout_customer():
    data = request.json or {}
    session_id = data.get("checkout_session_id") or data.get("id")

    if not session_id:
        return jsonify({"message": "checkout_session_id is required"}), 422

    ctx = get_current_customer_context()
    customer = None

    if ctx.get("user_id"):
        customer = Customers.query.filter_by(user_id=ctx["user_id"]).first()
    elif ctx.get("guest_id"):
        customer = Customers.query.filter_by(guest_id=ctx["guest_id"]).first()

    if not customer:
        return jsonify({"message": "Customer not found"}), 404

    session = CheckoutSession.query.get_or_404(session_id)

    if session.customer_id != customer.id:
        return jsonify({"message": "Unauthorized checkout session"}), 403

    name = data.get("name")
    phone = data.get("phone")
    address = data.get("address")
    email = data.get("email")

    if name is not None:
        customer.name = name
    if phone is not None:
        customer.phone = phone
    if address is not None:
        customer.address = address
    if email is not None:
        customer.email = email

    db.session.commit()

    return jsonify({
        "message": "Customer details saved",
        "checkout_session_id": str(session.id),
        "customer": customer.to_dict()
    })
