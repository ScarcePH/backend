"""add messenger events

Revision ID: 6f6d7e8a9b10
Revises: 417bcc881b4b
"""
from alembic import op
import sqlalchemy as sa


revision = "6f6d7e8a9b10"
down_revision = "417bcc881b4b"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "messenger_events",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("event_key", sa.String(length=255), nullable=False),
        sa.Column("sender_id", sa.String(length=255), nullable=False),
        sa.Column("event_type", sa.String(length=50), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("meta_timestamp", sa.BigInteger(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("last_error", sa.String(length=1000), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("processed_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("event_key"),
    )
    op.create_index("ix_messenger_events_event_key", "messenger_events", ["event_key"])
    op.create_index("ix_messenger_events_sender_id", "messenger_events", ["sender_id"])
    op.create_index("ix_messenger_events_meta_timestamp", "messenger_events", ["meta_timestamp"])
    op.create_index("ix_messenger_events_status", "messenger_events", ["status"])


def downgrade():
    op.drop_index("ix_messenger_events_status", table_name="messenger_events")
    op.drop_index("ix_messenger_events_meta_timestamp", table_name="messenger_events")
    op.drop_index("ix_messenger_events_sender_id", table_name="messenger_events")
    op.drop_index("ix_messenger_events_event_key", table_name="messenger_events")
    op.drop_table("messenger_events")
