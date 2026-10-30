import base64
import hashlib
import hmac
import json
import os
import unittest
from unittest.mock import Mock, patch

from flask import Flask

from api.data_deletion import data_deletion_bp
from db.database import db
from db.models import (
    CheckoutSession,
    Customers,
    DataDeletionRequest,
    Leads,
    Order,
    Payment,
)
from db.models.users import User


def create_signed_request(sender_id, secret):
    payload = json.dumps(
        {"algorithm": "HMAC-SHA256", "user_id": sender_id}
    ).encode()
    encoded_payload = base64.urlsafe_b64encode(payload).decode().rstrip("=")
    signature = hmac.new(
        secret.encode(),
        encoded_payload.encode(),
        hashlib.sha256,
    ).digest()
    encoded_signature = base64.urlsafe_b64encode(signature).decode().rstrip("=")
    return f"{encoded_signature}.{encoded_payload}"


class DataDeletionTestCase(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.config.update(
            SQLALCHEMY_DATABASE_URI="sqlite://",
            SQLALCHEMY_TRACK_MODIFICATIONS=False,
            TESTING=True,
        )
        self.app.register_blueprint(data_deletion_bp)
        db.init_app(self.app)
        self.context = self.app.app_context()
        self.context.push()
        db.create_all()
        self.client = self.app.test_client()
        self.secret = "data-deletion-test-secret"
        self.environment = patch.dict(os.environ, {"APP_SECRET": self.secret})
        self.environment.start()
        self.redis_delete = patch("api.data_deletion.redis_client.delete")
        self.delete_proofs = patch("api.data_deletion._delete_stored_proofs")
        self.sender_lock = patch("api.data_deletion.redis_client.lock")
        self.redis_mock = self.redis_delete.start()
        self.proofs_mock = self.delete_proofs.start()
        self.sender_lock_mock = self.sender_lock.start()
        self.lock_mock = Mock()
        self.lock_mock.acquire.return_value = True
        self.sender_lock_mock.return_value = self.lock_mock

    def tearDown(self):
        self.delete_proofs.stop()
        self.redis_delete.stop()
        self.sender_lock.stop()
        self.environment.stop()
        db.session.remove()
        db.drop_all()
        self.context.pop()

    def test_valid_request_removes_personal_data_but_keeps_transaction_history(self):
        customer = Customers(
            sender_id="facebook-user-123",
            name="Customer Name",
            phone="555-1234",
            address="1 Main St",
            email="customer@example.com",
        )
        db.session.add(customer)
        db.session.flush()
        checkout = CheckoutSession(
            customer_id=customer.id,
            items_json=[],
            total_price=100,
            proof_image_url="https://images.example.com/proofs/proof.jpg",
        )
        db.session.add(checkout)
        db.session.flush()
        order = Order(
            customer_id=customer.id,
            checkout_session_id=checkout.id,
            total_price=100,
        )
        db.session.add(order)
        db.session.flush()
        payment = Payment(
            order_id=order.id,
            received_amount=100,
            total_amount=100,
            payment_ss=checkout.proof_image_url,
        )
        db.session.add_all(
            [
                payment,
                Leads(sender_id="facebook-user-123", name="Shoe", size="9"),
            ]
        )
        db.session.commit()

        signed_request = create_signed_request("facebook-user-123", self.secret)
        response = self.client.post(
            "/data-deletion",
            data={"signed_request": signed_request},
            base_url="https://api.example.com",
        )

        self.assertEqual(200, response.status_code)
        body = response.get_json()
        self.assertRegex(body["confirmation_code"], r"^[0-9a-f]{32}$")
        self.assertEqual(
            "https://api.example.com/data-deletion-status/"
            + body["confirmation_code"],
            body["url"],
        )
        self.redis_mock.assert_called_once_with(
            "user_state:facebook-user-123",
            "handover:facebook-user-123",
            "chat_history:facebook-user-123",
            "bot_confusion:facebook-user-123",
        )
        self.sender_lock_mock.assert_called_once_with(
            "messenger:sender:facebook-user-123",
            timeout=300,
            blocking_timeout=15,
        )
        self.lock_mock.acquire.assert_called_once_with(
            blocking=True,
            blocking_timeout=15,
        )
        self.lock_mock.release.assert_called_once_with()
        self.proofs_mock.assert_called_once_with(
            [
                "https://images.example.com/proofs/proof.jpg",
                "https://images.example.com/proofs/proof.jpg",
            ]
        )

        db.session.expire_all()
        retained_customer = Customers.query.one()
        self.assertIsNone(retained_customer.sender_id)
        self.assertIsNone(retained_customer.name)
        self.assertIsNone(retained_customer.phone)
        self.assertIsNone(retained_customer.address)
        self.assertIsNone(retained_customer.email)
        self.assertEqual(1, Order.query.count())
        self.assertEqual(1, Payment.query.count())
        self.assertEqual(100, Payment.query.one().total_amount)
        self.assertIsNone(CheckoutSession.query.one().proof_image_url)
        self.assertIsNone(Payment.query.one().payment_ss)
        self.assertEqual(0, Leads.query.count())
        self.assertEqual(1, DataDeletionRequest.query.count())

        status_response = self.client.get(body["url"])
        self.assertEqual(200, status_response.status_code)
        self.assertIn(b"Data deletion request completed", status_response.data)
        self.assertIn(body["confirmation_code"].encode(), status_response.data)

    def test_invalid_signature_is_rejected_without_processing(self):
        signed_request = create_signed_request("facebook-user-123", "wrong-secret")

        response = self.client.post(
            "/data-deletion",
            data={"signed_request": signed_request},
        )

        self.assertEqual(400, response.status_code)
        self.assertEqual(0, DataDeletionRequest.query.count())
        self.redis_mock.assert_not_called()
        self.proofs_mock.assert_not_called()
        self.sender_lock_mock.assert_not_called()

    def test_malformed_signed_request_is_rejected(self):
        response = self.client.post(
            "/data-deletion",
            data={"signed_request": "é.invalid"},
        )

        self.assertEqual(400, response.status_code)
        self.assertEqual(0, DataDeletionRequest.query.count())
        self.sender_lock_mock.assert_not_called()

    def test_request_is_not_processed_when_sender_lock_is_unavailable(self):
        self.lock_mock.acquire.return_value = False

        response = self.client.post(
            "/data-deletion",
            data={
                "signed_request": create_signed_request(
                    "facebook-user-123",
                    self.secret,
                )
            },
        )

        self.assertEqual(503, response.status_code)
        self.assertEqual(0, DataDeletionRequest.query.count())
        self.redis_mock.assert_not_called()
        self.proofs_mock.assert_not_called()
        self.lock_mock.release.assert_not_called()

    def test_unknown_status_confirmation_is_not_exposed(self):
        response = self.client.get("/data-deletion-status/" + "a" * 32)

        self.assertEqual(404, response.status_code)


if __name__ == "__main__":
    unittest.main()
