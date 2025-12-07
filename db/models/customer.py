from db.database import db

class Customers(db.Model):
    __tablename__ = "customers"

    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.String, unique=True, index=True, nullable=False)

    name = db.Column(db.String)
    phone = db.Column(db.String)
    address = db.Column(db.String)

    created_at = db.Column(db.DateTime, server_default=db.func.now())
