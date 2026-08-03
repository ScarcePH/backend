import importlib
import io
import unittest
from unittest.mock import patch

import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from flask import Flask
from PIL import Image

import api.inventory as inventory_api
from db.database import db
from db.models.inventory import Inventory
from db.models.inventory_variation import InventoryVariation


class InventoryCategoryTestCase(unittest.TestCase):
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

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.context.pop()

    @staticmethod
    def _image_file():
        image = io.BytesIO()
        Image.new("RGB", (2, 2), color="white").save(image, format="PNG")
        image.seek(0)
        return image

    def test_category_is_serialized_and_returned_by_public_catalog(self):
        pair = Inventory(name="Nike SB Janoski", category="janoski", image="pair.png")
        pair.variations.append(InventoryVariation(
            condition="New",
            price=5000,
            size="9",
            status="onhand",
            stock=1,
        ))
        db.session.add(pair)
        db.session.commit()

        self.assertEqual("janoski", pair.to_dict()["category"])
        with self.app.test_request_context():
            response = inventory_api.get_catalog_items()
        self.assertEqual("janoski", response[0]["category"])
        self.assertEqual("available", response[0]["availability_status"])

    def test_create_requires_a_supported_category(self):
        for category in (None, "running"):
            with self.subTest(category=category):
                data = {
                    "name": "Test pair",
                    "file": (self._image_file(), "pair.png"),
                }
                if category is not None:
                    data["category"] = category
                with self.app.test_request_context(
                    method="POST",
                    data=data,
                    content_type="multipart/form-data",
                ):
                    response, status = inventory_api.create_inventory.__wrapped__()
                self.assertEqual(400, status)
                self.assertIn("category", response.get_json()["message"])

    def test_create_persists_category(self):
        with self.app.test_request_context(
            method="POST",
            data={
                "name": "Dunk pair",
                "description": "Court shoe",
                "category": "basketball",
                "file": (self._image_file(), "pair.png"),
            },
            content_type="multipart/form-data",
        ), patch.object(inventory_api, "upload", side_effect=["image-url", "carousel-url"]), patch.object(
            inventory_api, "fit_subject_center", side_effect=lambda image, _: image
        ):
            response, status = inventory_api.create_inventory.__wrapped__()

        self.assertEqual(201, status)
        self.assertEqual("basketball", response.get_json()["data"]["category"])
        self.assertEqual("basketball", Inventory.query.one().category)

    def test_edit_changes_category_and_rejects_invalid_values(self):
        pair = Inventory(name="Pair", category="basketball")
        db.session.add(pair)
        db.session.commit()

        with self.app.test_request_context(
            method="POST",
            json={"inventory_id": pair.id, "category": "janoski"},
        ):
            response, status = inventory_api.edit.__wrapped__()
        self.assertEqual(200, status)
        self.assertEqual("janoski", response.get_json()["inventory"]["category"])

        with self.app.test_request_context(
            method="POST",
            json={"inventory_id": pair.id, "category": "running"},
        ):
            response, status = inventory_api.edit.__wrapped__()
        self.assertEqual(400, status)
        self.assertIn("category", response.get_json()["message"])
        self.assertEqual("janoski", db.session.get(Inventory, pair.id).category)


class InventoryCategoryMigrationTestCase(unittest.TestCase):
    def test_migration_backfills_names_and_defaults_everything_else(self):
        engine = sa.create_engine("sqlite://")
        metadata = sa.MetaData()
        inventory = sa.Table(
            "inventory",
            metadata,
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("name", sa.String, nullable=False),
        )
        metadata.create_all(engine)

        migration = importlib.import_module(
            "migrations.versions.c4d2e6f8a901_add_inventory_category"
        )
        with engine.begin() as connection:
            connection.execute(inventory.insert(), [
                {"name": "Nike SB Janoski OG+"},
                {"name": "janoski Max"},
                {"name": "Kobe 6"},
            ])
            operations = Operations(MigrationContext.configure(connection))
            with patch.object(migration, "op", operations):
                migration.upgrade()
            rows = connection.execute(sa.text(
                "SELECT name, category FROM inventory ORDER BY id"
            )).all()

        self.assertEqual([
            ("Nike SB Janoski OG+", "janoski"),
            ("janoski Max", "janoski"),
            ("Kobe 6", "basketball"),
        ], rows)


if __name__ == "__main__":
    unittest.main()
