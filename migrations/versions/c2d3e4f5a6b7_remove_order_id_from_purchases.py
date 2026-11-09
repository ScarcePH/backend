"""remove order_id from purchases

Revision ID: c2d3e4f5a6b7
Revises: a1b2c3d4e5f6
Create Date: 2026-11-08 18:16:32.283000

"""
from alembic import op
import sqlalchemy as sa


revision = "c2d3e4f5a6b7"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None


FK_NAMING_CONVENTION = {
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
}


def upgrade():
    foreign_keys = sa.inspect(op.get_bind()).get_foreign_keys("purchases")
    order_foreign_key = next(
        (
            foreign_key
            for foreign_key in foreign_keys
            if foreign_key["constrained_columns"] == ["order_id"]
        ),
        None,
    )
    op.drop_index("ix_purchases_order_id", table_name="purchases")
    with op.batch_alter_table(
        "purchases",
        naming_convention=FK_NAMING_CONVENTION,
    ) as batch_op:
        if order_foreign_key:
            batch_op.drop_constraint(
                order_foreign_key["name"] or "fk_purchases_order_id_orders",
                type_="foreignkey",
            )
        batch_op.drop_column("order_id")


def downgrade():
    with op.batch_alter_table(
        "purchases",
        naming_convention=FK_NAMING_CONVENTION,
    ) as batch_op:
        batch_op.add_column(sa.Column("order_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            None,
            "orders",
            ["order_id"],
            ["id"],
            ondelete="SET NULL",
        )
    op.create_index("ix_purchases_order_id", "purchases", ["order_id"])
