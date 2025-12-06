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

    item_name = db.Column(db.String, nullable=False)
    size = db.Column(db.String)
    amount = db.Column(db.Integer, nullable=False)

    payment_method = db.Column(db.String)
    payment_reference = db.Column(db.String)
    payment_verified = db.Column(db.Boolean, default=False)

    status = db.Column(db.String, default="pending", index=True)

    created_at = db.Column(db.DateTime, server_default=db.func.now())
    updated_at = db.Column(db.DateTime, server_default=db.func.now(), onupdate=db.func.now())

    customer = db.relationship("Customers", backref="orders")
    inventory_item = db.relationship("Inventory", back_populates="order")
