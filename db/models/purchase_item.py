from decimal import Decimal, ROUND_HALF_UP

from db.database import db


class PurchaseItem(db.Model):
    __tablename__ = "purchase_items"
    __table_args__ = (
        db.CheckConstraint("quantity > 0", name="ck_purchase_items_quantity_positive"),
        db.CheckConstraint("unit_cost >= 0", name="ck_purchase_items_unit_cost_nonnegative"),
        db.CheckConstraint("listed_price >= 0", name="ck_purchase_items_listed_price_nonnegative"),
    )

    id = db.Column(db.Integer, primary_key=True)
    purchase_id = db.Column(
        db.Integer,
        db.ForeignKey("purchases.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    variation_id = db.Column(
        db.Integer,
        db.ForeignKey("inventory_variations.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    inventory_name = db.Column(db.String, nullable=False)
    condition = db.Column(db.String)
    size = db.Column(db.String(50))
    quantity = db.Column(db.Integer, nullable=False)
    unit_cost = db.Column(db.Numeric(12, 2), nullable=False)
    listed_price = db.Column(db.Numeric(12, 2), nullable=False)

    purchase = db.relationship("Purchase", back_populates="items")
    variation = db.relationship("InventoryVariation")

    def to_dict(self, allocated_fees=Decimal("0.00")):
        line_subtotal = Decimal(self.quantity) * Decimal(self.unit_cost)
        actual_total_cost = line_subtotal + Decimal(allocated_fees)
        actual_unit_cost = (actual_total_cost / self.quantity).quantize(
            Decimal("0.01"),
            rounding=ROUND_HALF_UP,
        )
        return {
            "id": self.id,
            "variation_id": self.variation_id,
            "inventory_name": self.inventory_name,
            "condition": self.condition,
            "size": self.size,
            "quantity": self.quantity,
            "unit_cost": float(self.unit_cost),
            "line_subtotal": float(line_subtotal),
            "allocated_fees": float(allocated_fees),
            "actual_total_cost": float(actual_total_cost),
            "actual_unit_cost": float(actual_unit_cost),
            "listed_price": float(self.listed_price),
            "listed_total": float(Decimal(self.quantity) * Decimal(self.listed_price)),
        }
