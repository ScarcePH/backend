from db.database import db

class Shipment(db.Model):
    __tablename__ = "shipments"

    id = db.Column(db.Integer, primary_key=True)

    carrier = db.Column(db.String)
    tracking = db.Column(db.String)
    status = db.Column(db.String)
    order_id = db.Column(
        db.Integer, db.ForeignKey("orders.id"), nullable=False
    )
    


    created_at = db.Column(db.DateTime, server_default=db.func.now())
    updated_at = db.Column(db.DateTime, server_default=db.func.now(), onupdate=db.func.now())

    def to_dict(self):
        return {
            "id": self.id,
            "carrier": self.carrier,
            "tracking": self.tracking,
            "status": self.status,
            "order_id": self.order_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

 
