from datetime import datetime
from db.database import db


class Cart(db.Model):
    __tablename__ = "carts"

    id = db.Column(db.Integer, primary_key=True)

    customer_id = db.Column(db.Integer, db.ForeignKey("customers.id"), nullable=True)

    # for guest users (store session UUID in cookie)
    guest_id = db.Column(db.String(36), nullable=True, index=True)

    is_active = db.Column(db.Boolean, default=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    items = db.relationship("CartItem", backref="cart", cascade="all, delete-orphan")

    def owner(self):
        return self.customer_id or self.guest_id
