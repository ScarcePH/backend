from types import SimpleNamespace
import importlib
import io
import os
import unittest
from unittest.mock import patch

from flask import Flask
from PIL import Image
from db.models.checkout_session import CheckoutSession
from db.repository.inventory import _normalize_size, is_variation_sellable


verify_payment = importlib.import_module("bot.handlers.verify_payment")
checkout_api = importlib.import_module("api.checkout")


class FakeResponse:
    def __init__(self, body=b"image", content_type="image/jpeg", status_code=200, length=None):
        self.body = body
        self.status_code = status_code
        self.headers = {"Content-Type": content_type}
        if length is not None:
            self.headers["Content-Length"] = str(length)
        self.closed = False

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError("request failed")

    def iter_content(self, chunk_size):
        yield self.body

    def close(self):
        self.closed = True


class CheckoutReviewTestCase(unittest.TestCase):
    def test_size_normalization_preserves_integer_trailing_zero(self):
        self.assertEqual("10", _normalize_size("US 10"))
        self.assertEqual("10.5", _normalize_size("10.50"))

    def test_sellability_requires_stock_and_allowed_status(self):
        cases = [
            (1, "onhand", True),
            (1, "preorder", True),
            (0, "onhand", False),
            (1, "sold", False),
            (1, "unavailable", False),
            (1, "INACTIVE", False),
        ]
        for stock, status, expected in cases:
            with self.subTest(stock=stock, status=status):
                variation = SimpleNamespace(stock=stock, status=status)
                self.assertIs(is_variation_sellable(variation), expected)

    def test_payment_download_rejects_untrusted_host(self):
        with patch.object(verify_payment.requests, "get") as get:
            with self.assertRaisesRegex(ValueError, "Unsupported"):
                verify_payment._download_image("https://example.com/payment.jpg")
        get.assert_not_called()

    def test_payment_download_streams_supported_meta_image(self):
        buffer = io.BytesIO()
        Image.new("RGB", (1, 1), color="white").save(buffer, format="JPEG")
        image_bytes = buffer.getvalue()
        response = FakeResponse(body=image_bytes, content_type="image/jpeg")
        with patch.object(verify_payment.requests, "get", return_value=response):
            body, content_type = verify_payment._download_image(
                "https://scontent.xx.fbcdn.net/payment.jpg"
            )
        self.assertEqual(image_bytes, body)
        self.assertEqual("image/jpeg", content_type)
        self.assertTrue(response.closed)

    def test_payment_download_rejects_redirect(self):
        response = FakeResponse(status_code=302)
        with patch.object(verify_payment.requests, "get", return_value=response):
            with self.assertRaisesRegex(ValueError, "redirect"):
                verify_payment._download_image("https://lookaside.fbsbx.com/payment.jpg")

    def test_checkout_proof_submission_is_idempotent(self):
        session = CheckoutSession(
            customer_id=1,
            items_json=[{"inventory_id": 1, "variation_id": 2, "qty": 1, "price": 100}],
            total_price=100,
            status="pending",
        )
        session.submit_proof("https://storage/first.jpg", "cod", 100)
        session.submit_proof("https://storage/second.jpg", "full", 100)
        self.assertEqual("proof_submitted", session.status)
        self.assertEqual("https://storage/first.jpg", session.proof_image_url)
        self.assertEqual("cod", session.payment_method)

    def test_checkout_rejection_stores_reason(self):
        session = CheckoutSession(
            customer_id=1,
            items_json=[{"inventory_id": 1, "variation_id": 2, "qty": 1, "price": 100}],
            total_price=100,
            status="proof_submitted",
        )
        session.reject("Screenshot is unreadable")
        self.assertEqual("rejected", session.status)
        self.assertEqual("Screenshot is unreadable", session.rejection_reason)

    def test_admin_email_get_only_renders_confirmation(self):
        app = Flask(__name__)
        app.register_blueprint(checkout_api.checkout_bp)
        with patch.dict(os.environ, {"JWT_SECRET_KEY": "test-secret"}):
            token = checkout_api._get_admin_serializer().dumps({
                "session_id": "checkout-1",
                "action": "approve",
            })
            with patch.object(checkout_api, "approve_checkout_session_repo") as approve:
                response = app.test_client().get(
                    "/checkout/admin-approve", query_string={"token": token}
                )
        self.assertEqual(200, response.status_code)
        self.assertIn(b"Approve order", response.data)
        approve.assert_not_called()

    def test_admin_serializer_has_no_development_secret_fallback(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(RuntimeError, "must be configured"):
                checkout_api._get_admin_serializer()


if __name__ == "__main__":
    unittest.main()
