"""add inventory category

Revision ID: c4d2e6f8a901
Revises: 8b9c0d1e2f3a
Create Date: 2026-08-04 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = "c4d2e6f8a901"
down_revision = "8b9c0d1e2f3a"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("inventory", schema=None) as batch_op:
        batch_op.add_column(sa.Column("category", sa.String(length=32), nullable=True))

    op.execute(sa.text("""
        UPDATE inventory
        SET category = CASE
            WHEN LOWER(name) LIKE '%janoski%' THEN 'janoski'
            ELSE 'basketball'
        END
    """))

    with op.batch_alter_table("inventory", schema=None) as batch_op:
        batch_op.alter_column("category", existing_type=sa.String(length=32), nullable=False)
        batch_op.create_check_constraint(
            "ck_inventory_category",
            "category IN ('janoski', 'basketball')",
        )


def downgrade():
    with op.batch_alter_table("inventory", schema=None) as batch_op:
        batch_op.drop_constraint("ck_inventory_category", type_="check")
        batch_op.drop_column("category")
