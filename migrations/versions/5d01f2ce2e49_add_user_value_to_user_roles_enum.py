"""add user value to user_roles enum

Revision ID: 5d01f2ce2e49
Revises: a04061476ed6
Create Date: 2026-01-23 14:44:23.942624

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '5d01f2ce2e49'
down_revision = 'a04061476ed6'
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        "ALTER TYPE user_roles ADD VALUE IF NOT EXISTS 'user'"
    )


def downgrade():
    pass
