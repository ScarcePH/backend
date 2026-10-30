"""add data deletion request status records

Revision ID: 4f2a9c7d1b60
Revises: 547c3620d556
"""
from alembic import op
import sqlalchemy as sa


revision = "4f2a9c7d1b60"
down_revision = "547c3620d556"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "data_deletion_requests",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("confirmation_code", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column(
            "requested_at",
            sa.DateTime(),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "completed_at",
            sa.DateTime(),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("confirmation_code"),
    )


def downgrade():
    op.drop_table("data_deletion_requests")
