"""add checkout review metadata and payment integrity

Revision ID: 7a8b9c0d1e2f
Revises: 6f6d7e8a9b10
Create Date: 2026-08-01 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = "7a8b9c0d1e2f"
down_revision = "6f6d7e8a9b10"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("checkout_sessions", schema=None) as batch_op:
        batch_op.add_column(sa.Column("payment_method", sa.String(length=32), nullable=True))
        batch_op.add_column(sa.Column("expected_payment_amount", sa.Numeric(10, 2), nullable=True))
        batch_op.add_column(sa.Column("review_notified_at", sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column("rejection_reason", sa.Text(), nullable=True))

    op.execute(sa.text("""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM payments
                WHERE order_id IS NOT NULL
                GROUP BY order_id HAVING COUNT(*) > 1
            ) THEN
                RAISE EXCEPTION
                    'Cannot add uq_payments_order_id: duplicate payments.order_id values exist; merge duplicate payment rows before retrying';
            END IF;
        END $$;
    """))

    with op.batch_alter_table("payments", schema=None) as batch_op:
        batch_op.create_unique_constraint("uq_payments_order_id", ["order_id"])


def downgrade():
    with op.batch_alter_table("payments", schema=None) as batch_op:
        batch_op.drop_constraint("uq_payments_order_id", type_="unique")

    with op.batch_alter_table("checkout_sessions", schema=None) as batch_op:
        batch_op.drop_column("rejection_reason")
        batch_op.drop_column("review_notified_at")
        batch_op.drop_column("expected_payment_amount")
        batch_op.drop_column("payment_method")
