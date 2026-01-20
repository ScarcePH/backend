from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from passlib.hash import argon2
from db.database import db


class Admin(db.Model):
    __tablename__ = "admins"


    id = db.Column(db.Integer, primary_key=True)

    email = db.Column(db.String(255), unique=True, nullable=False, index=True)

    password_hash = db.Column(db.String(255), nullable=False)

    role = db.Column(
        db.Enum("super_admin", "staff", name="admin_roles"),
        nullable=False,
        default="staff"
    )

    is_active = db.Column(db.Boolean, default=True, nullable=False)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    last_login_at = db.Column(db.DateTime)

    # -----------------------------
    # Password helpers
    # -----------------------------

    def set_password(self, password: str):
        """
        Hash and store password.
        """
        self.password_hash = argon2.hash(password)

    def check_password(self, password: str) -> bool:
        """
        Verify password against stored hash.
        """
        return argon2.verify(password, self.password_hash)

    # -----------------------------
    # Utility
    # -----------------------------

    def to_dict(self):
        """
        Safe admin representation (NEVER expose password_hash).
        """
        return {
            "id": self.id,
            "email": self.email,
            "role": self.role,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat(),
            "last_login_at": self.last_login_at.isoformat() if self.last_login_at else None,
        }

    def __repr__(self):
        return f"<Admin {self.email} ({self.role})>"
