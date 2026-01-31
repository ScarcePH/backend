from db.database import db

class Customers(db.Model):
    __tablename__ = "customers"

    id = db.Column(db.Integer, primary_key=True)

    sender_id = db.Column(db.String, unique=True, index=True, nullable=True)

    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True, unique=True)

    guest_id = db.Column(db.String, unique=True, index=True, nullable=True)

    name = db.Column(db.String)
    phone = db.Column(db.String)
    address = db.Column(db.String)
    email = db.Column(db.String)

    created_at = db.Column(db.DateTime, server_default=db.func.now())

    user = db.relationship("User", backref="customer", uselist=False)

    def to_dict(self):
        return {
            "id": self.id,
            "sender_id": self.sender_id,
            "user_id": self.user_id,
            "guest_id": self.guest_id,
            "name": self.name,
            "phone": self.phone,
            "address": self.address,
            "email": self.email,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
