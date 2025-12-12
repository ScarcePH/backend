from db.database import db

class Leads(db.Model):
    __tablename__ = "leads"

    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.String, unique=True, index=True, nullable=False)
    name = db.Column(db.String, nullable=False)
    size = db.Column(db.String)

    created_at = db.Column(db.DateTime, server_default=db.func.now())
    updated_at = db.Column(db.DateTime, server_default=db.func.now(), onupdate=db.func.now())