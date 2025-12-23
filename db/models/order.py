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

    #pending, confirmed, cancelled
    status = db.Column(db.String, default="pending", index=True)
    

    created_at = db.Column(db.DateTime, server_default=db.func.now())
    updated_at = db.Column(db.DateTime, server_default=db.func.now(), onupdate=db.func.now())

    customer = db.relationship("Customers", backref="orders")
    inventory = db.relationship("Inventory", backref="order")
    variation = db.relationship("InventoryVariation", backref="orders")
    payment = db.relationship("Payment", backref="orders", uselist=False)
    shipment = db.relationship("Shipment", backref="order", uselist=False)

    def to_dict(self):
        return {
            "id":self.id,
            "customer": self.customer.to_dict() if self.customer else None,
            "inventory": self.inventory.to_dict() if self.inventory else None,
            "variation": self.variation.to_dict() if self.variation else None,
            "payment": self.payment.to_dict() if self.payment else None,
            "shipment": self.shipment.to_dict() if self.shipment else None,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,

    }
