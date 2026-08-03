from db.database import db


class PromotionItem(db.Model):
    __tablename__ = "promotion_items"
    __table_args__ = (
        db.UniqueConstraint("promotion_id", "variation_id", name="uq_promotion_variation"),
        db.CheckConstraint("promo_price > 0", name="ck_promotion_items_positive_price"),
    )

    id = db.Column(db.Integer, primary_key=True)
    promotion_id = db.Column(
        db.Integer,
        db.ForeignKey("promotions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    variation_id = db.Column(
        db.Integer,
        db.ForeignKey("inventory_variations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    promo_price = db.Column(db.Numeric(10, 2), nullable=False)

    promotion = db.relationship("Promotion", back_populates="items")
    variation = db.relationship("InventoryVariation", backref="promotion_items")

