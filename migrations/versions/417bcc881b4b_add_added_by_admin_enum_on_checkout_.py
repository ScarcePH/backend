"""add added_by_admin enum on checkout status

Revision ID: 417bcc881b4b
Revises: a088296b5ad7
Create Date: 2026-02-15 10:27:28.079478

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '417bcc881b4b'
down_revision = 'a088296b5ad7'
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        "ALTER TYPE checkout_status ADD VALUE IF NOT EXISTS 'added_by_admin'"
    )


def downgrade():
    # Postgres cannot remove enum values directly; recreate enum without added_by_admin.
    op.execute("ALTER TABLE checkout_sessions ALTER COLUMN status DROP DEFAULT")
    op.execute(
        "UPDATE checkout_sessions SET status = 'pending' WHERE status = 'added_by_admin'"
    )
    op.execute("ALTER TYPE checkout_status RENAME TO checkout_status_old")
    op.execute(
        "CREATE TYPE checkout_status AS ENUM ("
        "'pending', 'proof_submitted', 'approved', 'rejected', 'expired'"
        ")"
    )
    op.execute(
        "ALTER TABLE checkout_sessions "
        "ALTER COLUMN status TYPE checkout_status "
        "USING status::text::checkout_status"
    )
    op.execute("DROP TYPE checkout_status_old")
    op.execute("ALTER TABLE checkout_sessions ALTER COLUMN status SET DEFAULT 'pending'")
