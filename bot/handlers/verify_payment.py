from bot.services.messenger import reply
from bot.state.manager import reset_state, transition_state
from bot.handlers.guided import reject_input
from decimal import Decimal
import io
import os
from urllib.parse import urlparse

import requests
from PIL import Image, UnidentifiedImageError
from db.database import db
from db.models import CheckoutSession
from services.image.upload import upload
from bot.observability import increment


MAX_IMAGE_SIZE = 9 * 1024 * 1024  
MAX_IMAGE_PIXELS = 25_000_000
ALLOWED_IMAGE_TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}
DEFAULT_ALLOWED_HOST_SUFFIXES = (".fbcdn.net", ".fbsbx.com")


def _host_is_allowed(hostname):
    hostname = (hostname or "").lower().rstrip(".")
    configured = {
        host.strip().lower()
        for host in os.environ.get("PAYMENT_PROOF_ALLOWED_HOSTS", "").split(",")
        if host.strip()
    }
    return hostname in configured or any(
        hostname.endswith(suffix) for suffix in DEFAULT_ALLOWED_HOST_SUFFIXES
    )


def _validate_image(body, content_type):
    expected_format = {
        "image/jpeg": "JPEG",
        "image/png": "PNG",
        "image/webp": "WEBP",
    }[content_type]
    try:
        with Image.open(io.BytesIO(body)) as image:
            actual_format = image.format
            if image.width * image.height > MAX_IMAGE_PIXELS:
                raise ValueError("Payment image dimensions are too large")
            image.verify()
    except Image.DecompressionBombError as exc:
        raise ValueError("Payment image dimensions are too large") from exc
    except (UnidentifiedImageError, OSError, SyntaxError) as exc:
        raise ValueError("The uploaded file is not a valid image") from exc
    if actual_format != expected_format:
        raise ValueError("The image format does not match its content type")


def _download_image(url):
    parsed = urlparse(url)
    if parsed.scheme != "https" or not _host_is_allowed(parsed.hostname):
        raise ValueError("Unsupported payment image URL")

    response = requests.get(
        url,
        stream=True,
        allow_redirects=False,
        timeout=(5, 15),
    )
    try:
        if 300 <= response.status_code < 400:
            raise ValueError("Payment image redirects are not allowed")
        response.raise_for_status()
        content_type = response.headers.get("Content-Type", "").split(";", 1)[0].lower()
        if content_type not in ALLOWED_IMAGE_TYPES:
            raise ValueError("Only JPEG, PNG, or WebP images are accepted")
        declared_size = int(response.headers.get("Content-Length", 0) or 0)
        if declared_size > MAX_IMAGE_SIZE:
            raise ValueError("Image too large (max 9MB)")

        chunks = []
        size = 0
        for chunk in response.iter_content(chunk_size=64 * 1024):
            if not chunk:
                continue
            size += len(chunk)
            if size > MAX_IMAGE_SIZE:
                raise ValueError("Image too large (max 9MB)")
            chunks.append(chunk)
        if not chunks:
            raise ValueError("Payment image is empty")
        body = b"".join(chunks)
        _validate_image(body, content_type)
        return body, content_type
    finally:
        response.close()


def handle(sender_id, screenshot, state):
    if not state.get("checkout_session_id"):
        reset_state(sender_id)
        reply(sender_id, "Your checkout session expired. Please select the pair again to restart.", None)
        return

    if not screenshot or not screenshot.startswith("https://"):
        return reject_input(
            sender_id,
            state,
            "Please send a valid JPEG, PNG, or WebP payment screenshot.",
            None,
            reason="invalid_payment_proof",
        )

    session = CheckoutSession.query.get(state["checkout_session_id"])
    if not session:
        reset_state(sender_id)
        reply(sender_id, "Your checkout session expired. Please select the pair again to restart.", None)
        return
    if session.status == "proof_submitted":
        transition_state(
            sender_id,
            state,
            "awaiting_customer_email",
            expected_input="customer_email",
            payment_ss=session.proof_image_url,
        )
        reply(sender_id, "We already saved your payment proof. Please provide your email address for order updates.", None)
        return
    if session.status != "pending" or session.is_expired():
        if session.status == "pending":
            session.status = "expired"
            db.session.commit()
        reset_state(sender_id)
        reply(sender_id, "This checkout is no longer active. Please select the pair again to restart.", None)
        return

    try:
        file_bytes, content_type = _download_image(screenshot)
        filename = f"messenger_{session.id}{ALLOWED_IMAGE_TYPES[content_type]}"
        proof_url = upload(
            file=io.BytesIO(file_bytes),
            filename=filename,
            content_type=content_type,
            subfolder="proofs",
        )
    except ValueError as exc:
        return reject_input(
            sender_id,
            state,
            str(exc),
            None,
            reason="invalid_payment_proof",
        )
    except Exception:
        reply(sender_id, "Failed to save the payment image. Please try again.", None)
        return

    payment_method = state.get("payment_method")
    try:
        requested_amount = Decimal(str(state.get("expected_payment_amount", session.total_price)))
    except Exception:
        requested_amount = session.total_price
    expected_amount = min(max(requested_amount, Decimal("0")), session.total_price)
    session.submit_proof(proof_url, payment_method, expected_amount)
    db.session.commit()
    increment("checkout_submissions")

    transition_state(
        sender_id,
        state,
        "awaiting_customer_email",
        expected_input="customer_email",
        payment_ss=proof_url,
        expected_payment_amount=str(expected_amount),
    )

    reply(sender_id, "Payment proof saved for human review. Please provide your email address so we can send order updates.", None)
    return
