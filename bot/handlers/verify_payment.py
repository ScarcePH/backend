from bot.services.messenger import reply
from bot.state.manager import set_state
from db.repository.customer import get_customer
from bot.core.constants import USE_OR_CHANGE_ADDRESS
import requests
from db.repository.ocr_job import ocr_job, wait_for_ocr
from db.database import db
from db.models import CheckoutSession
import mimetypes


MAX_IMAGE_SIZE = 9 * 1024 * 1024  


def handle(sender_id, screenshot, state):

    if not screenshot or not screenshot.startswith("https://"):
        reply(sender_id, "Payment Invalid. Please send a valid screenshot.", None)
        return

    try:
        response = requests.get(screenshot, timeout=10)
        response.raise_for_status()

        size = int(response.headers.get("Content-Length", 0))
        if size > MAX_IMAGE_SIZE:
            reply(sender_id, "Image too large (max 9MB).", None)
            return

        file_bytes = response.content

        filename = screenshot.split("/")[-1] or "image.jpg"
        content_type = (
            response.headers.get("Content-Type")
            or mimetypes.guess_type(filename)[0]
            or "image/jpeg"
        )

    except Exception:
        reply(sender_id, "Failed to process image.", None)
        return

    job_info = ocr_job(file_bytes, filename, content_type)

    result = wait_for_ocr(job_info["job_id"])

    if result.get("status") == "TIMEOUT":
        reply(sender_id, "Processing payment... please wait.", None)
        return

    if not result.get("is_valid"):
        reply(sender_id, "Payment Invalid. Please send again.", None)
        return

    
    session = CheckoutSession.query.get(state["checkout_session_id"])

    session.submit_proof(screenshot)
    db.session.commit()

    customer = get_customer(sender_id)

    name = customer.name if customer else None
    address = customer.address if customer else None
    phone = customer.phone if customer else None

    if name and address and phone:
        msg = (
            "We have your most recent Shipment info.\n"
            f"Name: {name}\n"
            f"Address: {address}\n"
            f"Phone: {phone}\n\n"
            "Would you like to use this address for your order?"
        )

        set_state(sender_id, {
            **state,
            "state": "repeat_customer_confirm",
            "customer_name": name,
            "customer_address": address,
            "customer_phone": phone,
            "customer_id": customer.id,
            "payment_ss": screenshot
        })

        reply(sender_id, msg, USE_OR_CHANGE_ADDRESS)
        return

    set_state(sender_id, {
        **state,
        "state": "awaiting_customer_name",
        "payment_ss": screenshot
    })

    reply(sender_id, "Great! To proceed with shipping, please provide your full name.", None)
    return
