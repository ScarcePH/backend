from db.database import db


class OrderItem(db.Model):
    __tablename__ = "order_items"

    id = db.Column(db.Integer, primary_key=True)

    order_id = db.Column(db.Integer, db.ForeignKey("orders.id"), nullable=False)

    inventory_id = db.Column(db.Integer, db.ForeignKey("inventory.id"), nullable=False)
    variation_id = db.Column(db.Integer, db.ForeignKey("inventory_variations.id"), nullable=False)

    quantity = db.Column(db.Integer, nullable=False)

    price_at_purchase = db.Column(db.Numeric(10, 2), nullable=False)

    created_at = db.Column(db.DateTime(timezone=True), server_default=db.func.now())

    inventory = db.relationship("Inventory")
    variation = db.relationship("InventoryVariation")

    def to_dict(self):
        return {
            "inventory": self.inventory.to_dict(),
            "variation": self.variation.to_dict(),
            "quantity": self.quantity,
            "price": float(self.price_at_purchase),
        }
