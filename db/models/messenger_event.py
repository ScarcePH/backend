from datetime import datetime

from db.database import db


class MessengerEvent(db.Model):
    __tablename__ = "messenger_events"

    id = db.Column(
        db.BigInteger().with_variant(db.Integer, "sqlite"),
        primary_key=True,
        autoincrement=True,
    )
    event_key = db.Column(db.String(255), nullable=False, unique=True, index=True)
    sender_id = db.Column(db.String(255), nullable=False, index=True)
    event_type = db.Column(db.String(50), nullable=False)
    payload = db.Column(db.JSON, nullable=False)
    meta_timestamp = db.Column(db.BigInteger, nullable=True, index=True)
    status = db.Column(db.String(20), nullable=False, default="pending", index=True)
    attempts = db.Column(db.Integer, nullable=False, default=0)
    last_error = db.Column(db.String(1000), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )
    processed_at = db.Column(db.DateTime, nullable=True)
