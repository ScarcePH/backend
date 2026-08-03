from db.database import db
from bot.core.constants import SCARCE_IMG

INVENTORY_CATEGORIES = ("janoski", "basketball")


class Inventory(db.Model):
    __tablename__ = "inventory"
    __table_args__ = (
        db.CheckConstraint(
            "category IN ('janoski', 'basketball')",
            name="ck_inventory_category",
        ),
    )

    id = db.Column(db.Integer, primary_key=True)

    name = db.Column(db.String, nullable=False)
    description = db.Column(db.String)
    image = db.Column(db.String)
    category = db.Column(db.String(32), nullable=False)

    created_at = db.Column(db.DateTime, server_default=db.func.now())
    updated_at = db.Column(db.DateTime, server_default=db.func.now(), onupdate=db.func.now())

    # order = db.relationship("Order", back_populates="inventory_item", uselist=False)

    variations = db.relationship(
        "InventoryVariation",
        backref="inventory",
        cascade="all, delete-orphan",
    )
    def to_dict(self):
        status_order = {"onhand": 0, "preorder": 1, "sold": 2}
        sorted_variations = sorted(
            self.variations,
            key=lambda v: status_order.get(v.status, 3)
        )
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "image": self.image,
            "category": self.category,
            "variations": [variation.to_dict() for variation in sorted_variations],
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
