from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from passlib.hash import argon2
from db.database import db
import re

EMAIL_REGEX = re.compile(
    r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$"
)


class User(db.Model):
    __tablename__ = "users"


    id = db.Column(db.Integer, primary_key=True)

    email = db.Column(db.String(255), unique=True, nullable=False, index=True)

    password_hash = db.Column(db.String(255), nullable=False)

    role = db.Column(
        db.Enum("super_admin", "user", name="user_roles"),
        nullable=False,
        default="user"
    )

    is_active = db.Column(db.Boolean, default=True, nullable=False)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    last_login_at = db.Column(db.DateTime)

    @classmethod
    def create(cls, email: str, password: str, role: str = "user"):
        email = email.strip().lower()

        # Basic validation
        if not email or not password:
            raise ValueError("Email and password are required")

        if not EMAIL_REGEX.match(email):
            raise ValueError("Invalid email format")

        cls.validate_password(password)

        # Check for existing user
        if cls.query.filter_by(email=email).first():
            raise ValueError("Email already registered")

        # Create user
        user = cls(email=email, role=role)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()

        return user

    @staticmethod
    def validate_password(password: str):
        if not isinstance(password, str):
            raise ValueError("Password is required")
        if len(password) < 8:
            raise ValueError("Password must be at least 8 characters")
        if len(password) > 128:
            raise ValueError("Password must be 128 characters or fewer")
        if password.strip() != password:
            raise ValueError("Password cannot start or end with spaces")
        has_mixed_case = password.lower() != password and password.upper() != password
        has_number = any(char.isdigit() for char in password)
        if not has_mixed_case or not has_number:
            raise ValueError("Password must include uppercase, lowercase, and a number")

    @staticmethod
    def hash_password(password: str) -> str:
        return argon2.hash(password)

    # -----------------------------
    # Password helpers
    # -----------------------------

    def set_password(self, password: str):
        """
        Hash and store password.
        """
        self.password_hash = self.hash_password(password)

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
        return f"<User {self.email} ({self.role})>"
