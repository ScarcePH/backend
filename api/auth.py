from flask import Blueprint, request, jsonify
from flask_jwt_extended import create_access_token
from db.models.users import User
from middleware.auth_required import auth_required
from db.database import db
from flask_jwt_extended import get_jwt_identity



auth_bp = Blueprint("auth", __name__)

@auth_bp.route("/login", methods=["POST"])
def login():
    data = request.json
    email = data.get("email")
    password = data.get("password")

    user = User.query.filter_by(email=email).first()

    if not user or not user.check_password(password):
        return jsonify({"message": "Invalid credentials"}), 401

    access_token = create_access_token(
        identity=str(user.id),
        additional_claims={"role": user.role}
    )

    return jsonify({
        "access_token": access_token,
        "user": User.to_dict(user)
    })


@auth_bp.route("/register", methods=["POST"])
def register_user():
    data = request.get_json() or {}
    try:
        user = User.create(
            email=data.get("email", ""),
            password=data.get("password", ""),
            role=data.get("role", "user")
        )
    except ValueError as e:
        return jsonify({"message": str(e)}), 422
    
    access_token = create_access_token(
        identity=str(user.id),
        additional_claims={"role": user.role}
    )

    return jsonify({
        "access_token": access_token,
        "user": User.to_dict(user)
    })


@auth_bp.route("/auth/validate", methods=["GET"])
@auth_required()
def protected():
    return jsonify({"status": True, "message":"Authenticated"}), 200

@auth_bp.route("/auth/change-password", methods=["POST"])
@auth_required()
def change_password():

    new_password = request.json.get("new_password")
    password = request.json.get("password")
    if not new_password or not password:
        return jsonify({"message": "Password and new password are required"}), 400
    user_id = get_jwt_identity()
    admin = User.query.get(user_id)
    if not admin or not admin.check_password(password):
        return jsonify({"message": "Incorrect password"}), 401
    admin.set_password(new_password)
    db.session.commit()
    return jsonify({"message": "Password change successfully"}), 200
