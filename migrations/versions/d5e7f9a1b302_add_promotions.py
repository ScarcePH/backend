"""add scheduled promotions

Revision ID: d5e7f9a1b302
Revises: c4d2e6f8a901
Create Date: 2026-08-04 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa


revision = "d5e7f9a1b302"
down_revision = "c4d2e6f8a901"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "promotions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("early_ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("end_date >= start_date", name="ck_promotions_date_range"),
    )
    op.create_index("ix_promotions_start_date", "promotions", ["start_date"])
    op.create_index("ix_promotions_end_date", "promotions", ["end_date"])
    op.create_table(
        "promotion_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("promotion_id", sa.Integer(), sa.ForeignKey("promotions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("variation_id", sa.Integer(), sa.ForeignKey("inventory_variations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("promo_price", sa.Numeric(10, 2), nullable=False),
        sa.CheckConstraint("promo_price > 0", name="ck_promotion_items_positive_price"),
        sa.UniqueConstraint("promotion_id", "variation_id", name="uq_promotion_variation"),
    )
    op.create_index("ix_promotion_items_promotion_id", "promotion_items", ["promotion_id"])
    op.create_index("ix_promotion_items_variation_id", "promotion_items", ["variation_id"])

    if op.get_bind().dialect.name == "postgresql":
        op.execute(sa.text(
            "ALTER TABLE promotions ADD CONSTRAINT ex_promotions_no_overlap "
            "EXCLUDE USING gist (daterange(start_date, end_date, '[]') WITH &&) "
            "WHERE (early_ended_at IS NULL)"
        ))


def downgrade():
    op.drop_table("promotion_items")
    op.drop_table("promotions")
