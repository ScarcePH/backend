from db.database import db

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


