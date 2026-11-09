from decimal import Decimal, ROUND_DOWN

from db.database import db


CENT = Decimal("0.01")


class Purchase(db.Model):
    __tablename__ = "purchases"
    __table_args__ = (
        db.CheckConstraint("shipping_fees >= 0", name="ck_purchases_shipping_fees_nonnegative"),
        db.CheckConstraint("other_fees >= 0", name="ck_purchases_other_fees_nonnegative"),
    )

    id = db.Column(db.Integer, primary_key=True)
    supplier = db.Column(db.String(255))
    purchase_date = db.Column(
        db.Date,
        nullable=False,
        index=True,
        server_default=db.func.current_date(),
    )
    shipping_fees = db.Column(db.Numeric(12, 2), nullable=False, default=0, server_default="0")
    other_fees = db.Column(db.Numeric(12, 2), nullable=False, default=0, server_default="0")
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime(timezone=True), server_default=db.func.now())

    items = db.relationship(
        "PurchaseItem",
        back_populates="purchase",
        cascade="all, delete-orphan",
        order_by="PurchaseItem.id",
    )

    def to_dict(self):
        items = list(self.items)
        fees = Decimal(self.shipping_fees or 0) + Decimal(self.other_fees or 0)
        weights = [
            Decimal(item.quantity) * Decimal(item.unit_cost)
            for item in items
        ]
        weight_total = sum(weights, Decimal("0"))
        if weight_total == 0:
            weights = [Decimal(item.quantity) for item in items]
            weight_total = sum(weights, Decimal("0"))

        allocated_fees = [Decimal("0.00") for _ in items]
        if fees and weight_total:
            raw_allocations = [
                fees * weight / weight_total
                for weight in weights
            ]
            allocated_fees = [
                amount.quantize(CENT, rounding=ROUND_DOWN)
                for amount in raw_allocations
            ]
            remaining_cents = int(
                (fees - sum(allocated_fees, Decimal("0.00"))) / CENT
            )
            remainder_order = sorted(
                range(len(items)),
                key=lambda index: (
                    raw_allocations[index] - allocated_fees[index],
                    -index,
                ),
                reverse=True,
            )
            for index in remainder_order[:remaining_cents]:
                allocated_fees[index] += CENT

        serialized_items = []
        subtotal = Decimal("0")
        for item, line_fees in zip(items, allocated_fees):
            line_subtotal = Decimal(item.quantity) * Decimal(item.unit_cost)
            subtotal += line_subtotal
            serialized_items.append(item.to_dict(line_fees))

        return {
            "id": self.id,
            "supplier": self.supplier,
            "purchase_date": self.purchase_date.isoformat() if self.purchase_date else None,
            "shipping_fees": float(self.shipping_fees or 0),
            "other_fees": float(self.other_fees or 0),
            "subtotal": float(subtotal),
            "total_cost": float(subtotal + fees),
            "notes": self.notes,
            "items": serialized_items,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
