import importlib
import unittest
from datetime import date, datetime
from unittest.mock import patch

from flask import Flask
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations

import api.purchases as purchases_api
from db.database import db
from db.models import (
    Customers,
    Inventory,
    InventoryVariation,
    Order,
    OrderItem,
    Payment,
)
from db.repository.dashboard import income_statement, purchase_statement
from db.repository.purchase import create_purchase, fifo_costs_by_order_item


class PurchaseRecordTestCase(unittest.TestCase):
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
            name="Janoski",
            category="janoski",
            variations=[
                InventoryVariation(
                    condition="New",
                    price=6000,
                    size="9",
                    status="preorder",
                    stock=0,
                    spent=1000,
                ),
                InventoryVariation(
                    condition="New",
                    price=7000,
                    size="10",
                    status="preorder",
                    stock=0,
                ),
            ],
        )
        db.session.add(self.inventory)
        db.session.commit()
        self.variation, self.other_variation = self.inventory.variations

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.context.pop()

    def test_purchase_saves_actual_cost_and_allocates_fees_without_changing_listed_price(self):
        purchase = create_purchase({
            "supplier": "Supplier",
            "purchase_date": "2026-11-07",
            "shipping_fees": "30.00",
            "items": [
                {"variation_id": self.variation.id, "quantity": 1, "unit_cost": "100.00"},
                {"variation_id": self.other_variation.id, "quantity": 1, "unit_cost": "200.00"},
            ],
        })

        result = purchase.to_dict()
        self.assertEqual(330.0, result["total_cost"])
        self.assertEqual([10.0, 20.0], [
            item["allocated_fees"] for item in result["items"]
        ])
        self.assertEqual([110.0, 220.0], [
            item["actual_total_cost"] for item in result["items"]
        ])
        self.assertEqual([6000.0, 7000.0], [
            item["listed_price"] for item in result["items"]
        ])
        self.assertEqual(6000, float(self.variation.price))
        self.assertNotIn("spent", self.variation.to_dict())

    def test_purchase_is_not_linked_to_an_order(self):
        customer = Customers(name="Customer")
        db.session.add(customer)
        db.session.flush()
        order = Order(customer_id=customer.id, total_price=6000)
        db.session.add(order)
        db.session.flush()
        db.session.add(OrderItem(
            order_id=order.id,
            inventory_id=self.inventory.id,
            variation_id=self.variation.id,
            quantity=1,
            price_at_purchase=6000,
        ))
        db.session.commit()

        with self.app.test_request_context(
            method="POST",
            json={
                "order_id": order.id,
                "items": [{
                    "variation_id": self.other_variation.id,
                    "quantity": 1,
                    "unit_cost": "3500.00",
                }],
            },
        ):
            response, status = purchases_api.create_purchase_record.__wrapped__()

        self.assertEqual(201, status)
        self.assertNotIn("order_id", response.get_json()["purchase"])
        self.assertEqual(3500.0, response.get_json()["purchase"]["items"][0]["unit_cost"])

    def test_invalid_cost_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "unit_cost"):
            create_purchase({
                "items": [{
                    "variation_id": self.variation.id,
                    "quantity": 1,
                    "unit_cost": "-1.00",
                }],
            })

    def test_fee_rounding_never_creates_negative_allocations(self):
        purchase = create_purchase({
            "shipping_fees": "0.01",
            "items": [
                {"variation_id": self.variation.id, "quantity": 1, "unit_cost": "1.00"},
                {"variation_id": self.variation.id, "quantity": 1, "unit_cost": "1.00"},
                {"variation_id": self.variation.id, "quantity": 1, "unit_cost": "0.00"},
            ],
        })

        allocations = [
            item["allocated_fees"] for item in purchase.to_dict()["items"]
        ]
        self.assertEqual(0.01, sum(allocations))
        self.assertTrue(all(amount >= 0 for amount in allocations))

    def test_list_endpoint_filters_and_serializes_purchase_records(self):
        create_purchase({
            "purchase_date": "2026-11-06",
            "items": [{
                "variation_id": self.variation.id,
                "quantity": 2,
                "unit_cost": "3000.00",
            }],
        })
        with self.app.test_request_context(
            method="GET",
            query_string={"start_date": "2026-11-07"},
        ):
            response, status = purchases_api.get_purchase_records.__wrapped__()

        self.assertEqual(200, status)
        self.assertEqual([], response.get_json()["purchases"])

    def test_purchase_statement_reports_actual_cost_including_allocated_fees(self):
        create_purchase({
            "purchase_date": "2026-11-07",
            "shipping_fees": "20.00",
            "items": [{
                "variation_id": self.variation.id,
                "quantity": 2,
                "unit_cost": "3000.00",
            }],
        })

        statement = purchase_statement(date(2026, 11, 7), date(2026, 11, 8))
        result = statement.get_json()

        self.assertEqual(6020.0, result["total_spent"])
        self.assertEqual(12000.0, result["total_price"])
        self.assertEqual(20.0, result["data"][0]["allocated_fees"])
        self.assertNotIn("order_id", result["data"][0])

    def test_fifo_costs_are_allocated_to_sale_items_by_purchase_date(self):
        create_purchase({
            "purchase_date": "2026-11-01",
            "shipping_fees": "20.00",
            "items": [{
                "variation_id": self.variation.id,
                "quantity": 2,
                "unit_cost": "100.00",
            }],
        })
        create_purchase({
            "purchase_date": "2026-11-05",
            "items": [{
                "variation_id": self.variation.id,
                "quantity": 2,
                "unit_cost": "200.00",
            }],
        })
        customer = Customers(name="Customer")
        db.session.add(customer)
        db.session.flush()
        order = Order(
            customer_id=customer.id,
            total_price=600,
            status="completed",
        )
        db.session.add(order)
        db.session.flush()
        order_item = OrderItem(
            order_id=order.id,
            inventory_id=self.inventory.id,
            variation_id=self.variation.id,
            quantity=3,
            price_at_purchase=200,
        )
        db.session.add(order_item)
        db.session.commit()

        costs = fifo_costs_by_order_item()

        self.assertEqual(420.0, float(costs[order_item.id]["cost"]))
        self.assertTrue(costs[order_item.id]["complete"])

    def test_income_statement_uses_fifo_cost_for_sale_profit(self):
        create_purchase({
            "purchase_date": "2026-11-01",
            "items": [{
                "variation_id": self.variation.id,
                "quantity": 3,
                "unit_cost": "100.00",
            }],
        })
        customer = Customers(name="Customer")
        db.session.add(customer)
        db.session.flush()
        order = Order(
            customer_id=customer.id,
            total_price=600,
            status="completed",
        )
        db.session.add(order)
        db.session.flush()
        order_item = OrderItem(
            order_id=order.id,
            inventory_id=self.inventory.id,
            variation_id=self.variation.id,
            quantity=3,
            price_at_purchase=200,
        )
        db.session.add(order_item)
        db.session.add(Payment(
            order_id=order.id,
            total_amount=600,
            received_amount=500,
            created_at=datetime(2026, 11, 7),
        ))
        db.session.commit()

        statement = income_statement("2026-11-07", "2026-11-08").get_json()

        self.assertEqual(500.0, statement["total_received"])
        self.assertEqual(600.0, statement["total_revenue"])
        self.assertEqual(300.0, statement["total_spent"])
        self.assertEqual(300.0, statement["total_net_profit"])
        self.assertEqual(300.0, statement["data"][0]["net_profit"])
        self.assertTrue(statement["data"][0]["cost_data_complete"])

    def test_income_statement_does_not_report_profit_without_complete_cost_data(self):
        customer = Customers(name="Customer")
        db.session.add(customer)
        db.session.flush()
        order = Order(
            customer_id=customer.id,
            total_price=600,
            status="completed",
        )
        db.session.add(order)
        db.session.flush()
        db.session.add(OrderItem(
            order_id=order.id,
            inventory_id=self.inventory.id,
            variation_id=self.other_variation.id,
            quantity=1,
            price_at_purchase=600,
        ))
        db.session.add(Payment(
            order_id=order.id,
            total_amount=600,
            received_amount=600,
            created_at=datetime(2026, 11, 7),
        ))
        db.session.commit()

        statement = income_statement("2026-11-07", "2026-11-08").get_json()

        self.assertFalse(statement["cost_data_complete"])
        self.assertIsNone(statement["total_net_profit"])
        self.assertIsNone(statement["data"][0]["net_profit"])


class PurchaseRecordMigrationTestCase(unittest.TestCase):
    def test_migration_creates_tables_and_backfills_legacy_variation_costs(self):
        engine = sa.create_engine("sqlite://")
        metadata = sa.MetaData()
        sa.Table("orders", metadata, sa.Column("id", sa.Integer, primary_key=True))
        sa.Table(
            "inventory",
            metadata,
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("name", sa.String),
        )
        sa.Table(
            "inventory_variations",
            metadata,
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("inventory_id", sa.Integer),
            sa.Column("condition", sa.String),
            sa.Column("size", sa.String),
            sa.Column("price", sa.Numeric(10, 2)),
            sa.Column("spent", sa.Numeric(10, 2)),
            sa.Column("quantity_purchased", sa.Integer),
            sa.Column("created_at", sa.DateTime),
        )
        metadata.create_all(engine)

        migration = importlib.import_module(
            "migrations.versions.a1b2c3d4e5f6_add_purchase_records"
        )
        with engine.begin() as connection:
            operations = Operations(MigrationContext.configure(connection))
            with patch.object(migration, "op", operations):
                connection.execute(sa.text(
                    "INSERT INTO inventory (id, name) VALUES (1, 'Janoski')"
                ))
                connection.execute(sa.text(
                    """
                    INSERT INTO inventory_variations
                        (id, inventory_id, condition, size, price, spent,
                         quantity_purchased, created_at)
                    VALUES
                        (1, 1, 'New', '9', 6000, 1000, 2, '2026-11-01 10:00:00'),
                        (2, 1, 'New', '10', 7000, 800, 1, NULL),
                        (3, 1, 'New', '11', 7500, NULL, 1, '2026-11-02 10:00:00')
                    """
                ))
                migration.upgrade()
                remove_order_id_migration = importlib.import_module(
                    "migrations.versions.c2d3e4f5a6b7_remove_order_id_from_purchases"
                )
                with patch.object(remove_order_id_migration, "op", operations):
                    remove_order_id_migration.upgrade()
            tables = sa.inspect(connection).get_table_names()
            purchase_columns = {
                column["name"]
                for column in sa.inspect(connection).get_columns("purchases")
            }
            purchases = connection.execute(
                sa.text("SELECT id, purchase_date FROM purchases ORDER BY id")
            ).all()
            purchase_items = connection.execute(
                sa.text(
                    "SELECT variation_id, inventory_name, quantity, unit_cost "
                    "FROM purchase_items ORDER BY variation_id"
                )
            ).all()

        self.assertIn("purchases", tables)
        self.assertIn("purchase_items", tables)
        self.assertNotIn("order_id", purchase_columns)
        self.assertEqual(
            ["2026-11-01", "1900-01-01"],
            [str(purchase.purchase_date) for purchase in purchases],
        )
        self.assertEqual(
            [(1, "Janoski", 2, 1000), (2, "Janoski", 1, 800)],
            [
                (row.variation_id, row.inventory_name, row.quantity, float(row.unit_cost))
                for row in purchase_items
            ],
        )


if __name__ == "__main__":
    unittest.main()
