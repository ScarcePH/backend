import base64
import binascii
import hashlib
import hmac
import html
import json
import os
import re
import secrets
from urllib.parse import unquote, urlparse

from flask import Blueprint, abort, jsonify, make_response, request, url_for

from bot.utils.redis_client import redis_client
from db.database import db
from db.models import CheckoutSession, Customers, DataDeletionRequest, Leads, Order, Payment


data_deletion_bp = Blueprint("data_deletion", __name__)
CONFIRMATION_CODE_PATTERN = re.compile(r"^[0-9a-f]{32}$")
SENDER_LOCK_TIMEOUT_SECONDS = 300
SENDER_LOCK_WAIT_SECONDS = 15


def _decode_signed_request(signed_request):
    print('signed_request', signed_request )

    if not isinstance(signed_request, str):
        return None

    parts = signed_request.split(".")
    if len(parts) != 2:
        return None

    encoded_signature, encoded_payload = parts
 
    try:
        signature = base64.b64decode(
            encoded_signature + "=" * (-len(encoded_signature) % 4),
            altchars=b"-_",
            validate=True,
        )
        payload_bytes = base64.b64decode(
            encoded_payload + "=" * (-len(encoded_payload) % 4),
            altchars=b"-_",
            validate=True,
        )
        payload = json.loads(payload_bytes)
    except (binascii.Error, UnicodeError, ValueError):
        print(binascii.Error, UnicodeError, ValueError)
        return None
       

    app_secret = os.environ.get("APP_SECRET")

    print("app_secret", app_secret)

    if not app_secret or not isinstance(payload, dict):
        return None

    expected_signature = hmac.new(
        app_secret.encode("utf-8"),
        encoded_payload.encode("ascii"),
        hashlib.sha256,
    ).digest()
    if not hmac.compare_digest(signature, expected_signature):
        return None

    print('signature',signature)
    print('expected_signature', expected_signature)
    print("payload", payload)

    algorithm = payload.get("algorithm")
    if not isinstance(algorithm, str) or algorithm.upper() != "HMAC-SHA256":
        return None

    sender_id = payload.get("user_id")
    if isinstance(sender_id, int) and not isinstance(sender_id, bool):
        sender_id = str(sender_id)
    if not isinstance(sender_id, str) or not sender_id or len(sender_id) > 255:
        return None

    return sender_id


def _stored_object_key(image_url):
    image_base_url = os.environ.get("IMAGE_BASE_URL")
    if not image_base_url:
        raise RuntimeError("IMAGE_BASE_URL is required to remove stored payment proofs")

    base = urlparse(image_base_url.rstrip("/"))
    image = urlparse(image_url)
    base_path = base.path.rstrip("/")
    expected_prefix = f"{base_path}/"
    if (
        not base.scheme
        or not base.netloc
        or (image.scheme, image.netloc) != (base.scheme, base.netloc)
        or not image.path.startswith(expected_prefix)
    ):
        raise RuntimeError("Payment proof URL is outside the configured image storage")

    key = unquote(image.path[len(expected_prefix):])
    if not key or any(part in {"", ".", ".."} for part in key.split("/")):
        raise RuntimeError("Payment proof URL has an invalid storage key")
    return key


def _delete_stored_proofs(image_urls):
    unique_urls = {image_url for image_url in image_urls if image_url}
    if not unique_urls:
        return

    from services.image.upload import s3

    for image_url in unique_urls:
        s3.delete_object(
            Bucket="scarce-images",
            Key=_stored_object_key(image_url),
        )


def _delete_sender_data(sender_id):
    customer = Customers.query.filter_by(sender_id=sender_id).first()
    checkout_sessions = []
    orders = []
    if customer:
        checkout_sessions = CheckoutSession.query.filter_by(
            customer_id=customer.id
        ).all()
        orders = Order.query.filter_by(customer_id=customer.id).all()

    payment_ids = [order.id for order in orders]
    payments = (
        Payment.query.filter(Payment.order_id.in_(payment_ids)).all()
        if payment_ids
        else []
    )
    proof_urls = [session.proof_image_url for session in checkout_sessions]
    proof_urls.extend(payment.payment_ss for payment in payments)

    _delete_stored_proofs(proof_urls)
    redis_client.delete(
        f"user_state:{sender_id}",
        f"handover:{sender_id}",
        f"chat_history:{sender_id}",
        f"bot_confusion:{sender_id}",
    )

    Leads.query.filter_by(sender_id=sender_id).delete(synchronize_session=False)
    if customer:
        customer.sender_id = None
        customer.name = None
        customer.phone = None
        customer.address = None
        customer.email = None
        for session in checkout_sessions:
            session.proof_image_url = None
        for payment in payments:
            payment.payment_ss = None

    confirmation_code = secrets.token_hex(16)
    db.session.add(
        DataDeletionRequest(
            confirmation_code=confirmation_code,
            status="completed",
        )
    )
    db.session.commit()
    return confirmation_code


@data_deletion_bp.post("/data-deletion")
def data_deletion_callback():
    sender_id = _decode_signed_request(request.form.get("signed_request"))
    print("sender_id", sender_id)
    if sender_id is None:
        return jsonify({"error": "Invalid signed_request"}), 400

    lock = redis_client.lock(
        f"messenger:sender:{sender_id}",
        timeout=SENDER_LOCK_TIMEOUT_SECONDS,
        blocking_timeout=SENDER_LOCK_WAIT_SECONDS,
    )
    if not lock.acquire(blocking=True, blocking_timeout=SENDER_LOCK_WAIT_SECONDS):
        return jsonify({"error": "Could not safely process the deletion request"}), 503
    try:
        confirmation_code = _delete_sender_data(sender_id)
    finally:
        lock.release()

    status_url = url_for(
        "data_deletion.deletion_status",
        confirmation_code=confirmation_code,
        _external=True,
        _scheme="https",
    )
    response = jsonify(
        {
            "url": status_url,
            "confirmation_code": confirmation_code,
        }
    )
    response.headers["Cache-Control"] = "no-store"
    return response


@data_deletion_bp.get("/data-deletion-status/<confirmation_code>")
def deletion_status(confirmation_code):
    if not CONFIRMATION_CODE_PATTERN.fullmatch(confirmation_code):
        abort(404)

    deletion_request = DataDeletionRequest.query.filter_by(
        confirmation_code=confirmation_code
    ).first()
    if deletion_request is None:
        abort(404)

    completed_at = html.escape(deletion_request.completed_at.isoformat())
    safe_code = html.escape(deletion_request.confirmation_code)
    response = make_response(
        f"""<!doctype html>
<html lang="en">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Data deletion request status - ScarcePH</title></head>
<body>
<main>
<h1>Data deletion request completed</h1>
<p>Your Messenger identifier, contact details, inquiry records, conversation state,
and stored payment-proof images have been removed from our systems.</p>
<p>Order and transaction records are retained where needed for fulfillment,
accounting, or legal obligations; direct customer contact details have been removed.</p>
<p>Confirmation code: <strong>{safe_code}</strong></p>
<p>Completed at: <time>{completed_at}</time></p>
</main>
</body>
</html>"""
    )
    response.headers["Cache-Control"] = "no-store"
    return response
