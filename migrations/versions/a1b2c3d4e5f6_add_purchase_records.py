"""add purchase records

Revision ID: a1b2c3d4e5f6
Revises: 4f2a9c7d1b60
Create Date: 2026-11-07 21:40:00.000000

"""
from alembic import op
import sqlalchemy as sa
from datetime import date


revision = "a1b2c3d4e5f6"
down_revision = "4f2a9c7d1b60"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "purchases",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("supplier", sa.String(length=255), nullable=True),
        sa.Column("order_id", sa.Integer(), nullable=True),
        sa.Column("purchase_date", sa.Date(), server_default=sa.func.current_date(), nullable=False),
        sa.Column("shipping_fees", sa.Numeric(precision=12, scale=2), nullable=False, server_default="0"),
        sa.Column("other_fees", sa.Numeric(precision=12, scale=2), nullable=False, server_default="0"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.CheckConstraint("shipping_fees >= 0", name="ck_purchases_shipping_fees_nonnegative"),
        sa.CheckConstraint("other_fees >= 0", name="ck_purchases_other_fees_nonnegative"),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_purchases_order_id", "purchases", ["order_id"])
    op.create_index("ix_purchases_purchase_date", "purchases", ["purchase_date"])

    op.create_table(
        "purchase_items",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("purchase_id", sa.Integer(), nullable=False),
        sa.Column("variation_id", sa.Integer(), nullable=True),
        sa.Column("inventory_name", sa.String(), nullable=False),
        sa.Column("condition", sa.String(), nullable=True),
        sa.Column("size", sa.String(length=50), nullable=True),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("unit_cost", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("listed_price", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.CheckConstraint("quantity > 0", name="ck_purchase_items_quantity_positive"),
        sa.CheckConstraint("unit_cost >= 0", name="ck_purchase_items_unit_cost_nonnegative"),
        sa.CheckConstraint("listed_price >= 0", name="ck_purchase_items_listed_price_nonnegative"),
        sa.ForeignKeyConstraint(["purchase_id"], ["purchases.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["variation_id"],
            ["inventory_variations.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_purchase_items_purchase_id", "purchase_items", ["purchase_id"])
    op.create_index("ix_purchase_items_variation_id", "purchase_items", ["variation_id"])

    connection = op.get_bind()
    inventory_variations = sa.table(
        "inventory_variations",
        sa.column("id", sa.Integer),
        sa.column("inventory_id", sa.Integer),
        sa.column("condition", sa.String),
        sa.column("size", sa.String),
        sa.column("price", sa.Numeric(10, 2)),
        sa.column("spent", sa.Numeric(10, 2)),
        sa.column("quantity_purchased", sa.Integer),
        sa.column("created_at", sa.DateTime),
    )
    inventory = sa.table(
        "inventory",
        sa.column("id", sa.Integer),
        sa.column("name", sa.String),
    )
    purchases = sa.table(
        "purchases",
        sa.column("id", sa.Integer),
        sa.column("supplier", sa.String),
        sa.column("purchase_date", sa.Date),
        sa.column("shipping_fees", sa.Numeric(12, 2)),
        sa.column("other_fees", sa.Numeric(12, 2)),
        sa.column("notes", sa.Text),
    )
    purchase_items = sa.table(
        "purchase_items",
        sa.column("purchase_id", sa.Integer),
        sa.column("variation_id", sa.Integer),
        sa.column("inventory_name", sa.String),
        sa.column("condition", sa.String),
        sa.column("size", sa.String),
        sa.column("quantity", sa.Integer),
        sa.column("unit_cost", sa.Numeric(12, 2)),
        sa.column("listed_price", sa.Numeric(12, 2)),
    )

    legacy_costs = connection.execute(
        sa.select(
            inventory_variations.c.id,
            inventory_variations.c.condition,
            inventory_variations.c.size,
            inventory_variations.c.price,
            inventory_variations.c.spent,
            inventory_variations.c.quantity_purchased,
            inventory_variations.c.created_at,
            inventory.c.name,
        )
        .select_from(
            inventory_variations.join(
                inventory,
                inventory_variations.c.inventory_id == inventory.c.id,
            )
        )
        .where(inventory_variations.c.spent.is_not(None))
    ).mappings()

    for row in legacy_costs:
        quantity = row["quantity_purchased"]
        if quantity is None:
            quantity = 1
        elif quantity <= 0:
            raise ValueError(
                f"Cannot migrate inventory variation {row['id']}: "
                "quantity_purchased must be positive"
            )
        if row["spent"] < 0:
            raise ValueError(
                f"Cannot migrate inventory variation {row['id']}: "
                "spent cannot be negative"
            )
        if row["price"] < 0:
            raise ValueError(
                f"Cannot migrate inventory variation {row['id']}: "
                "price cannot be negative"
            )
        purchase_date = row["created_at"]
        if purchase_date is not None:
            purchase_date = (
                purchase_date.date()
                if hasattr(purchase_date, "date")
                else purchase_date
            )
        else:
            purchase_date = date(1900, 1, 1)

        purchase_id = connection.execute(
            purchases.insert()
            .values(
                supplier="Legacy inventory cost",
                purchase_date=purchase_date,
                shipping_fees=0,
                other_fees=0,
                notes="Migrated from inventory_variations.spent",
            )
            .returning(purchases.c.id)
        ).scalar_one()
        connection.execute(
            purchase_items.insert().values(
                purchase_id=purchase_id,
                variation_id=row["id"],
                inventory_name=row["name"],
                condition=row["condition"],
                size=row["size"],
                quantity=quantity,
                unit_cost=row["spent"],
                listed_price=row["price"],
            )
        )


def downgrade():
    op.drop_index("ix_purchase_items_variation_id", table_name="purchase_items")
    op.drop_index("ix_purchase_items_purchase_id", table_name="purchase_items")
    op.drop_table("purchase_items")
    op.drop_index("ix_purchases_purchase_date", table_name="purchases")
    op.drop_index("ix_purchases_order_id", table_name="purchases")
    op.drop_table("purchases")
