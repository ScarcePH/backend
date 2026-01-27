from flask import Blueprint, request, jsonify
from flask_jwt_extended import create_access_token
from db.models.users import User
from middleware.auth_required import auth_required
from db.database import db
from flask_jwt_extended import get_jwt_identity, jwt_required, get_jwt
from db.models.token_blocklist import TokenBlocklist
from api.helpers.cart import merge_guest_cart_to_user


auth_bp = Blueprint("auth", __name__)

@auth_bp.route("/auth/login", methods=["POST"])
def login():
    data = request.json
    email = data.get("email")
    password = data.get("password")

    user = User.query.filter_by(email=email).first()

    if not user or not user.check_password(password):
        return jsonify({"message": "Invalid credentials"}), 422

    access_token = create_access_token(
        identity=str(user.id),
        additional_claims={"role": user.role}
    )
    guest_id = request.cookies.get("guest_id")
    print('guest_id',guest_id)
    merge_guest_cart_to_user(user.id, guest_id)
    response = jsonify({
        "access_token": access_token,
        "user": User.to_dict(user)
    })
    response.set_cookie("guest_id", "", expires=0)
    return response



@auth_bp.route("/auth/register", methods=["POST"])
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

    guest_id = request.cookies.get("guest_id")
    print('guest_id',guest_id)
    merge_guest_cart_to_user(user.id, guest_id)

    response =  jsonify({
        "access_token": access_token,
        "user": User.to_dict(user)
    })
    response.set_cookie("guest_id", "", expires=0)
    return response


@auth_bp.route("/auth/validate", methods=["GET"])
@auth_required()
def protected():
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
     
    return jsonify({
        "status": True, 
        "message":"Authenticated",
        "user": User.to_dict(user)
    }), 200

@auth_bp.route("/auth/change-password", methods=["POST"])
@auth_required()
def change_password():

    new_password = request.json.get("new_password")
    password = request.json.get("password")
    if not new_password or not password:
        return jsonify({"message": "Password and new password are required"}), 400
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    if not user or not user.check_password(password):
        return jsonify({"message": "Incorrect password"}), 401
    user.set_password(new_password)
    db.session.commit()
    return jsonify({"message": "Password change successfully"}), 200


@auth_bp.route("/auth/logout", methods=["POST"])
@jwt_required()
def logout():
    jti = get_jwt()["jti"]

    db.session.add(TokenBlocklist(jti=jti))
    db.session.commit()

    return jsonify({"message": "Successfully logged out"}), 200