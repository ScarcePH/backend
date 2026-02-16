from db.database import db
from sqlalchemy.dialects.postgresql import UUID


class Order(db.Model):
    __tablename__ = "orders"

    id = db.Column(db.Integer, primary_key=True)

    customer_id = db.Column(db.Integer, db.ForeignKey("customers.id"), nullable=False)

    # inventory_id = db.Column(
    #     db.Integer, db.ForeignKey("inventory.id"), nullable=False
    # )

    # variation_id = db.Column(
    #     db.Integer, db.ForeignKey("inventory_variations.id"), nullable=False
    # )

    checkout_session_id = db.Column(
        UUID(as_uuid=True),
        db.ForeignKey("checkout_sessions.id"),
        nullable=True,
        unique=True
    )

    total_price = db.Column(db.Numeric(10, 2), nullable=True)

    #confirmed, cancelled, refunded
    status = db.Column(db.String, default="confirmed", index=True)

    created_at = db.Column(db.DateTime(timezone=True), server_default=db.func.now())
    updated_at = db.Column(db.DateTime(timezone=True), server_default=db.func.now(), onupdate=db.func.now())

    customer = db.relationship("Customers", backref="orders")
    payment = db.relationship("Payment", backref="order", uselist=False)
    shipment = db.relationship("Shipment", backref="order", uselist=False)

    items = db.relationship("OrderItem", backref="order", cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "id": self.id,
            "status": self.status,
            "total_price": float(self.total_price),
            "items": [item.to_dict() for item in self.items],
            "payment": self.payment.to_dict() if self.payment else None,
            "customer": self.customer.to_dict() if self.customer else None,
            "shipment": self.shipment.to_dict() if self.shipment else None,
            "created_at": self.created_at.isoformat(),
        }

