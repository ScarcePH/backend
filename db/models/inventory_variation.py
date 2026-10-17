from db.database import db
import json


class InventoryVariation(db.Model):
    __tablename__ = "inventory_variations"

    id = db.Column(db.Integer, primary_key=True)
    inventory_id = db.Column(db.Integer, db.ForeignKey("inventory.id"), nullable=False)

    condition = db.Column(db.String)
    price = db.Column(db.Numeric(10,2), nullable=False)
    size = db.Column(db.String(50))
    image = db.Column(db.String)
    status = db.Column(db.String)
    stock = db.Column(db.Integer, default=0)
    quantity_purchased = db.Column(db.Integer, default=1)
    url = db.Column(db.String)
    spent = db.Column(db.Numeric(10,2))
    created_at = db.Column(db.DateTime, server_default=db.func.now())
    updated_at = db.Column(db.DateTime, server_default=db.func.now(), onupdate=db.func.now())

    def to_dict(self):
        try:
            images = json.loads(self.image) if self.image else []
        except (TypeError, json.JSONDecodeError):
            images = []
        return {
            "id": self.id,
            "inventory_id": self.inventory_id,
            "condition": self.condition,
            "price": float(self.price) if self.price is not None else None,
            "size": self.size,
            "image": images,
            "status": self.status,
            "stock": self.stock,
            "url": self.url,
            "spent": self.spent,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

