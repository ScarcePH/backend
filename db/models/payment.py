from db.database import db

class Payment(db.Model):
    __tablename__ = "payments"

    id = db.Column(db.Integer, primary_key=True)


    received_amount = db.Column(db.Numeric(10,2), default=0)
    total_amount = db.Column(db.Numeric(10,2), default=0)
    payment_ss = db.Column(db.String)
    payment_method = db.Column(db.String)
    order_id = db.Column(db.Integer, db.ForeignKey("orders.id"))


    created_at = db.Column(db.DateTime, server_default=db.func.now())
    updated_at = db.Column(db.DateTime, server_default=db.func.now(), onupdate=db.func.now())

 

    def to_dict(self):
        return {
            "id": self.id,
            "received_amount": self.received_amount,
            "total_amount": self.total_amount,
            "payment_ss": self.payment_ss,
            "payment_method": self.payment_method,
            "order_id": self.order_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "to_settle": self.total_amount - self.received_amount,
        }