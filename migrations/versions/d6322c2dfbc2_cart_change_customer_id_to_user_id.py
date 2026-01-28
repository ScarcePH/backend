"""cart change customer_id to user_id

Revision ID: d6322c2dfbc2
Revises: b79c9e9e66cd
Create Date: 2026-01-28 23:58:14.200760

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd6322c2dfbc2'
down_revision = 'b79c9e9e66cd'
branch_labels = None
depends_on = None


def upgrade():
    # 1. Add new column
    op.add_column("carts", sa.Column("user_id", sa.Integer(), nullable=True))

    # 2. Create FK to users
    op.create_foreign_key(
        "fk_carts_user_id_users",
        "carts",
        "users",
        ["user_id"],
        ["id"]
    )

    # 3. Drop old FK
    op.drop_constraint("carts_customer_id_fkey", "carts", type_="foreignkey")

    # 4. Drop old column
    op.drop_column("carts", "customer_id")


def downgrade():
    op.add_column("carts", sa.Column("customer_id", sa.Integer(), nullable=True))

    op.create_foreign_key(
        "fk_carts_customer_id_customers",
        "carts",
        "customers",
        ["customer_id"],
        ["id"]
    )

    op.drop_constraint("fk_carts_user_id_users", "carts", type_="foreignkey")
    op.drop_column("carts", "user_id")
