import uuid
from datetime import datetime, timedelta
from sqlalchemy.dialects.postgresql import UUID
from db.database import db


class CheckoutSession(db.Model):
    __tablename__ = "checkout_sessions"

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    customer_id = db.Column(
        db.Integer,
        db.ForeignKey("customers.id"),
        nullable=False,
        index=True
    )


    items_json = db.Column(db.JSON, nullable=False)

    total_price = db.Column(db.Numeric(10, 2), nullable=False)

    status = db.Column(
        db.Enum(
            "pending",          # checkout created, waiting for screenshot
            "proof_submitted",  # user uploaded screenshot
            "approved",         # admin approved payment
            "rejected",         # admin rejected screenshot
            "expired",          # session expired
            name="checkout_status"
        ),
        nullable=False,
        default="pending"
    )

    proof_image_url = db.Column(db.String, nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    expires_at = db.Column(db.DateTime, nullable=False)

    customer = db.relationship("Customers", backref="checkout_sessions")
    orders = db.relationship("Order", backref="checkout_session", uselist=False)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if not self.expires_at:
            self.expires_at = datetime.utcnow() + timedelta(minutes=30)

    def is_expired(self):
        return datetime.utcnow() > self.expires_at

    def submit_proof(self, image_url: str):
        if self.status != "pending":
            raise ValueError("Cannot submit proof in current state")
        self.proof_image_url = image_url
        self.status = "proof_submitted"

    def approve(self):
        if self.status != "proof_submitted":
            raise ValueError("Only proof_submitted sessions can be approved")
        self.status = "approved"

    def reject(self):
        if self.status != "proof_submitted":
            raise ValueError("Only proof_submitted sessions can be rejected")
        self.status = "rejected"

    def __repr__(self):
        return f"<CheckoutSession {self.id} customer={self.customer_id} status={self.status}>"
