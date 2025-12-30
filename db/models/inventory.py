from db.database import db
from bot.core.constants import SCARCE_IMG

class Inventory(db.Model):
    __tablename__ = "inventory"

    id = db.Column(db.Integer, primary_key=True)

    name = db.Column(db.String, nullable=False)
    description = db.Column(db.String)

    created_at = db.Column(db.DateTime, server_default=db.func.now())
    updated_at = db.Column(db.DateTime, server_default=db.func.now(), onupdate=db.func.now())

    # order = db.relationship("Order", back_populates="inventory_item", uselist=False)

    variations = db.relationship(
        "InventoryVariation",
        backref="inventory",
        cascade="all, delete-orphan",
    )
    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "variations": [variation.to_dict() for variation in self.variations],
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
