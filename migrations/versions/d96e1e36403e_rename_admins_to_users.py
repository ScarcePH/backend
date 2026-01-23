"""rename admins to users

Revision ID: d96e1e36403e
Revises: 2ba92c76a2ba
Create Date: 2026-01-23 14:01:04.543072

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'd96e1e36403e'
down_revision = '2ba92c76a2ba'
branch_labels = None
depends_on = None


def upgrade():
    op.rename_table("admins", "users")




def downgrade():
    op.rename_table("users", "admins")

