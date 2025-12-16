from db.database import db

class Order(db.Model):
    __tablename__ = "orders"

    id = db.Column(db.Integer, primary_key=True)

    customer_id = db.Column(
        db.Integer, db.ForeignKey("customers.id"), nullable=False
    )

    inventory_id = db.Column(
        db.Integer, db.ForeignKey("inventory.id"), nullable=False
    )

    variation_id = db.Column(
        db.Integer, db.ForeignKey("inventory_variations.id"), nullable=False
    )

    status = db.Column(db.String, default="pending", index=True)

    payment_method = db.Column(db.String, default="gcash")
    payment_reference = db.Column(db.String)
    payment_verified = db.Column(db.Boolean, default=False)
    payment_ss = db.Column(db.String)

    

    created_at = db.Column(db.DateTime, server_default=db.func.now())
    updated_at = db.Column(db.DateTime, server_default=db.func.now(), onupdate=db.func.now())

    customer = db.relationship("Customers", backref="orders")
    inventory_item = db.relationship("Inventory", back_populates="order")
