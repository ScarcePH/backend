from flask import Blueprint, request, jsonify
from flask_jwt_extended import create_access_token
from db.models.admin import Admin

auth_bp = Blueprint("auth", __name__)

@auth_bp.route("/login", methods=["POST"])
def admin_login():
    data = request.json
    email = data.get("email")
    password = data.get("password")

    admin = Admin.query.filter_by(email=email).first()

    if not admin or not admin.check_password(password):
        return jsonify({"message": "Invalid credentials"}), 401

    access_token = create_access_token(
        identity=str(admin.id),
        additional_claims={"role": admin.role}
    )

    return jsonify({
        "access_token": access_token,
        "admin": Admin.to_dict(admin)
    })
