"""rename admin_roles enum to user_roles

Revision ID: a04061476ed6
Revises: d96e1e36403e
Create Date: 2026-01-23 14:12:42.941992

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'a04061476ed6'
down_revision = 'd96e1e36403e'
branch_labels = None
depends_on = None


def upgrade():
    op.execute("ALTER TYPE admin_roles RENAME TO user_roles")
    


def downgrade():
    op.execute("ALTER TYPE user_roles RENAME TO admin_roles")
