from db.database import db


class DataDeletionRequest(db.Model):
    __tablename__ = "data_deletion_requests"

    id = db.Column(db.Integer, primary_key=True)
    confirmation_code = db.Column(db.String(32), unique=True, nullable=False)
    status = db.Column(db.String(20), nullable=False, default="completed")
    requested_at = db.Column(db.DateTime, nullable=False, server_default=db.func.now())
    completed_at = db.Column(db.DateTime, nullable=False, server_default=db.func.now())
