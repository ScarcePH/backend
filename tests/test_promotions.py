from datetime import date, datetime
from decimal import Decimal
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from zoneinfo import ZoneInfo
from uuid import UUID

from flask import Flask

from api import promotions as promotions_api
from db.database import db
from db.models import Cart, CartItem, CheckoutSession, Inventory, InventoryVariation, Promotion, PromotionItem
from db.models.users import User
from db.repository.checkout import _authoritative_items
from db.repository.checkout import start_checkout
from db.repository.inventory import get_public_catalog_inventory
from db.repository.promotion import get_active_promotion, promotion_status


class PromotionTestCase(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.config.update(
            SQLALCHEMY_DATABASE_URI="sqlite://",
            SQLALCHEMY_TRACK_MODIFICATIONS=False,
            TESTING=True,
        )
        db.init_app(self.app)
        self.context = self.app.app_context()
        self.context.push()
        db.create_all()

        self.inventory = Inventory(
            name="Promo pair",
            description="Test pair",
            category="janoski",
            image="pair.png",
        )
        self.variation = InventoryVariation(
            condition="New",
            price=Decimal("5000.00"),
            size="9",
            status="onhand",
            stock=2,
        )
        self.inventory.variations.append(self.variation)
        db.session.add(self.inventory)
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.context.pop()

    def add_promotion(self, start=date(2026, 8, 4), end=date(2026, 8, 6), price="4000.00"):
        promotion = Promotion(
            name="August sale",
            description="Three day sale",
            start_date=start,
            end_date=end,
        )
        promotion.items.append(PromotionItem(
            variation_id=self.variation.id,
            promo_price=Decimal(price),
        ))
        db.session.add(promotion)
        db.session.commit()
        return promotion

    def payload(self, **changes):
        data = {
            "name": "August sale",
            "description": "Three day sale",
            "start_date": "2026-08-04",
            "end_date": "2026-08-06",
            "items": [{"variation_id": self.variation.id, "promo_price": 4000}],
        }
        data.update(changes)
        return data

    def test_activation_dates_are_inclusive(self):
        promotion = self.add_promotion()
        self.assertEqual("scheduled", promotion_status(promotion, date(2026, 8, 3)))
        self.assertEqual("active", promotion_status(promotion, date(2026, 8, 4)))
        self.assertEqual("active", promotion_status(promotion, date(2026, 8, 6)))
        self.assertEqual("ended", promotion_status(promotion, date(2026, 8, 7)))
        self.assertEqual(promotion.id, get_active_promotion(date(2026, 8, 4)).id)
        self.assertEqual(promotion.id, get_active_promotion(date(2026, 8, 6)).id)

    def test_catalog_exposes_regular_and_effective_prices(self):
        promotion = self.add_promotion()
        with patch("db.repository.promotion.manila_today", return_value=date(2026, 8, 5)):
            variation = get_public_catalog_inventory()[0]["variations"][0]
        self.assertEqual(5000.0, variation["price"])
        self.assertEqual(4000.0, variation["effective_price"])
        self.assertEqual(4000.0, variation["promo_price"])
        self.assertEqual(promotion.id, variation["promotion_id"])
        self.assertTrue(variation["is_on_promotion"])

    def test_create_rejects_empty_duplicate_and_non_discount_items(self):
        invalid_items = [
            [],
            [
                {"variation_id": self.variation.id, "promo_price": 4000},
                {"variation_id": self.variation.id, "promo_price": 3900},
            ],
            [{"variation_id": self.variation.id, "promo_price": 5000}],
            [{"variation_id": self.variation.id, "promo_price": 0}],
        ]
        for items in invalid_items:
            with self.subTest(items=items), self.app.test_request_context(
                method="POST", json=self.payload(items=items)
            ):
                response, status = promotions_api.create_promotion.__wrapped__()
            self.assertEqual(400, status)
            self.assertIn("message", response.get_json())

    def test_overlapping_schedules_are_rejected_but_early_ended_do_not_block(self):
        promotion = self.add_promotion()
        with self.app.test_request_context(method="POST", json=self.payload(
            start_date="2026-08-06", end_date="2026-08-08"
        )):
            response, status = promotions_api.create_promotion.__wrapped__()
        self.assertEqual(409, status)
        self.assertEqual("promotion_overlap", response.get_json()["code"])

        promotion.early_ended_at = datetime(2026, 8, 5, tzinfo=ZoneInfo("Asia/Manila"))
        db.session.commit()
        with self.app.test_request_context(method="POST", json=self.payload(
            name="Replacement", start_date="2026-08-06", end_date="2026-08-08"
        )):
            response, status = promotions_api.create_promotion.__wrapped__()
        self.assertEqual(201, status)

    def test_lifecycle_edit_end_and_delete_rules(self):
        promotion = self.add_promotion()
        with patch("api.promotions.manila_today", return_value=date(2026, 8, 5)), patch(
            "db.repository.promotion.manila_today", return_value=date(2026, 8, 5)
        ), self.app.test_request_context(method="PUT", json=self.payload(start_date="2026-08-03")):
            response, status = promotions_api.update_promotion.__wrapped__(promotion.id)
        self.assertEqual(409, status)
        self.assertIn("start date", response.get_json()["message"])

        with patch("db.repository.promotion.manila_today", return_value=date(2026, 8, 5)), patch(
            "api.promotions.manila_now",
            return_value=datetime(2026, 8, 5, 12, tzinfo=ZoneInfo("Asia/Manila")),
        ), self.app.test_request_context(method="POST"):
            response = promotions_api.end_promotion.__wrapped__(promotion.id)
        self.assertEqual("ended", response.get_json()["status"])

        with self.app.test_request_context(method="PUT", json=self.payload()):
            response, status = promotions_api.update_promotion.__wrapped__(promotion.id)
        self.assertEqual(409, status)

        future = self.add_promotion(start=date(2026, 9, 1), end=date(2026, 9, 2))
        with patch("db.repository.promotion.manila_today", return_value=date(2026, 8, 5)), self.app.test_request_context(method="DELETE"):
            response = promotions_api.delete_promotion.__wrapped__(future.id)
        self.assertEqual(204, response[1])
        self.assertIsNone(db.session.get(Promotion, future.id))

    def test_checkout_revalidation_keeps_locked_price(self):
        session = SimpleNamespace(items_json=[{
            "inventory_id": self.inventory.id,
            "variation_id": self.variation.id,
            "qty": 1,
            "price": 4000.0,
        }])
        self.variation.price = Decimal("5500.00")
        db.session.commit()
        items, total, _ = _authoritative_items(session)
        self.assertEqual(4000.0, items[0]["price"])
        self.assertEqual(Decimal("4000.0"), total)

    def test_checkout_start_locks_active_price_across_promotion_edit(self):
        promotion = self.add_promotion()
        with patch("db.repository.promotion.manila_today", return_value=date(2026, 8, 5)):
            result = start_checkout([
                {"inventory_id": self.inventory.id, "variation_id": self.variation.id, "qty": 1}
            ], guest_id="checkout-guest")
        session = db.session.get(CheckoutSession, UUID(result["checkout_session_id"]))
        self.assertEqual(4000.0, session.items_json[0]["price"])

        promotion.items[0].promo_price = Decimal("3500.00")
        db.session.commit()
        items, total, _ = _authoritative_items(session)
        self.assertEqual(4000.0, items[0]["price"])
        self.assertEqual(Decimal("4000.0"), total)

    def test_cart_display_reprices_when_promotion_starts_and_ends(self):
        import api.cart as cart_api

        promotion = self.add_promotion()
        cart = Cart(guest_id="cart-guest")
        cart.items.append(CartItem(
            inventory_id=self.inventory.id,
            variation_id=self.variation.id,
            quantity=1,
            price_at_add=Decimal("5000.00"),
        ))
        db.session.add(cart)
        db.session.commit()

        context = {"user_id": None, "guest_id": "cart-guest", "new_guest_created": False}
        with patch.object(cart_api, "get_current_customer_context", return_value=context), patch(
            "db.repository.promotion.manila_today", return_value=date(2026, 8, 5)
        ), self.app.test_request_context(method="GET"):
            active_response = cart_api.get_cart()
        self.assertEqual(4000.0, active_response[0].get_json()["total"])

        promotion.early_ended_at = datetime(2026, 8, 5, tzinfo=ZoneInfo("Asia/Manila"))
        db.session.commit()
        with patch.object(cart_api, "get_current_customer_context", return_value=context), self.app.test_request_context(method="GET"):
            ended_response = cart_api.get_cart()
        self.assertEqual(5000.0, ended_response[0].get_json()["total"])


if __name__ == "__main__":
    unittest.main()
