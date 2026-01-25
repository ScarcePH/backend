from db.database import db
from datetime import datetime


class CartItem(db.Model):
    __tablename__ = "cart_items"

    id = db.Column(db.Integer, primary_key=True)

    cart_id = db.Column(db.Integer, db.ForeignKey("carts.id"), nullable=False)

    inventory_id = db.Column(db.Integer, db.ForeignKey("inventory.id"), nullable=False)
    variation_id = db.Column(db.Integer, db.ForeignKey("inventory_variations.id"), nullable=True)

    quantity = db.Column(db.Integer, nullable=False, default=1)

    # snapshot price (important)
    price_at_add = db.Column(db.Numeric(10, 2), nullable=False)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    inventory = db.relationship("Inventory")
    variation = db.relationship("InventoryVariation")

    __table_args__ = (
        db.UniqueConstraint("cart_id", "inventory_id", "variation_id", name="uq_cart_item"),
    )
