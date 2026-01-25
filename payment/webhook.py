import hmac
import hashlib
import base64
from flask import Blueprint, request, abort
import os


payments_bp = Blueprint("event_payments", __name__)

PAYMENT_EVENT_SECRET = str(os.environ.get("PAYMENT_EVENT_SECRET"))



def verify_signature(payload, signature_header):
    computed = hmac.new(
        PAYMENT_EVENT_SECRET.encode(),
        payload,
        hashlib.sha256
    ).digest()

    computed_signature = base64.b64encode(computed).decode()
    return hmac.compare_digest(computed_signature, signature_header)


@payments_bp.route("/webhook/payments", methods=["POST"])
def webhook():
    signature = request.headers.get("Paymongo-Signature")
    payload = request.get_data()  # RAW body


    # signature = base64.b64encode(
    #     hmac.new(PAYMENT_EVENT_SECRET.encode(), payload, hashlib.sha256).digest()
    # ).decode()

    # return signature

   


    if not signature or not verify_signature(payload, signature):
        abort(400, "Invalid signature")

    data = request.json
    print("EVENT RECEIVED:", data)

    return {"status": "ok" ,"data":data}
