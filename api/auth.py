from datetime import datetime
from flask import Blueprint, current_app, request, jsonify
from flask_jwt_extended import create_access_token
from db.models.users import EMAIL_REGEX, User
from middleware.auth_required import auth_required
from db.database import db
from flask_jwt_extended import get_jwt_identity, jwt_required, get_jwt
from db.models.token_blocklist import TokenBlocklist
from api.helpers.cart import merge_guest_cart_to_user
from api.helpers.rate_limit import client_ip, rate_limit_hit
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from task.email import enqueue_email
import hashlib
import os


auth_bp = Blueprint("auth", __name__)
RESET_TOKEN_MAX_AGE_SECONDS = 60 * 60
MAX_RESET_TOKEN_LENGTH = 2048
FORGOT_PASSWORD_EMAIL_LIMIT = 3
FORGOT_PASSWORD_IP_LIMIT = 20
FORGOT_PASSWORD_WINDOW_SECONDS = 15 * 60
RESET_PASSWORD_IP_LIMIT = 10
RESET_PASSWORD_TOKEN_LIMIT = 5
RESET_PASSWORD_WINDOW_SECONDS = 5 * 60


def _password_reset_serializer():
    secret = current_app.config.get("JWT_SECRET_KEY") or os.environ.get("JWT_SECRET_KEY")
    if not secret:
        raise RuntimeError("JWT_SECRET_KEY is required for password reset tokens")
    return URLSafeTimedSerializer(secret_key=secret, salt="password-reset")


def _build_reset_url(token: str) -> str:
    frontend_url = os.environ.get("FRONTEND_URL", "http://localhost:5173").rstrip("/")
    return f"{frontend_url}/reset-password?token={token}"


def _password_hash_digest(user: User) -> str:
    return hashlib.sha256(user.password_hash.encode()).hexdigest()


def _hash_rate_limit_value(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _rate_limited_response(retry_after: int):
    response = jsonify({
        "message": "Too many requests. Please wait before trying again.",
        "code": "RATE_LIMITED",
    })
    response.status_code = 429
    response.headers["Retry-After"] = str(retry_after)
    return response

@auth_bp.route("/auth/login", methods=["POST"])
def login():
    data = request.get_json() or {}
    email = (data.get("email") or "").strip().lower()
    password = data.get("password")

    if not email or not password:
        return jsonify({"message": "Email and password are required"}), 400

    user = User.query.filter_by(email=email).first()

    if not user or not user.check_password(password):
        return jsonify({"message": "Invalid credentials"}), 422

    access_token = create_access_token(
        identity=str(user.id),
        additional_claims={"role": user.role}
    )
    guest_id = request.cookies.get("guest_id")
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

    data = request.get_json() or {}
    new_password = data.get("new_password")
    password = data.get("password")
    if not new_password or not password:
        return jsonify({"message": "Password and new password are required"}), 400
    try:
        User.validate_password(new_password)
    except ValueError as e:
        return jsonify({"message": str(e)}), 422
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    if not user or not user.check_password(password):
        return jsonify({"message": "Incorrect password"}), 401
    user.set_password(new_password)
    db.session.commit()
    return jsonify({"message": "Password change successfully"}), 200


@auth_bp.route("/auth/forgot-password", methods=["POST"])
def forgot_password():
    data = request.get_json() or {}
    email = (data.get("email") or "").strip().lower()

    ip_limited, ip_retry_after = rate_limit_hit(
        f"forgot-password:ip:{client_ip()}",
        FORGOT_PASSWORD_IP_LIMIT,
        FORGOT_PASSWORD_WINDOW_SECONDS,
    )
    if ip_limited:
        return _rate_limited_response(ip_retry_after)

    if not email:
        return jsonify({"message": "Email is required"}), 400
    if len(email) > 255 or not EMAIL_REGEX.match(email):
        return jsonify({"message": "Invalid email format"}), 422

    email_limited, email_retry_after = rate_limit_hit(
        f"forgot-password:email:{_hash_rate_limit_value(email)}",
        FORGOT_PASSWORD_EMAIL_LIMIT,
        FORGOT_PASSWORD_WINDOW_SECONDS,
    )

    if ip_limited or email_limited:
        return _rate_limited_response(max(ip_retry_after, email_retry_after))

    user = User.query.filter_by(email=email).first()
    if user:
        token = _password_reset_serializer().dumps({
            "user_id": user.id,
            "email": user.email,
            "purpose": "password_reset",
            "password_hash_digest": _password_hash_digest(user),
        })
        reset_url = _build_reset_url(token)

        payload = {
            "type": "password_reset",
            "to": user.email,
            "template_variables": {
                "reset_url": reset_url,
                "email": user.email,
                "expires_in": "1 hour",
                "store_name": "ScarcePH",
                "year": datetime.utcnow().year,
            },
        }

        try:
            enqueue_email(payload)
        except Exception as exc:
            current_app.logger.error(
                "password_reset_email_enqueue_failed error_class=%s",
                type(exc).__name__,
            )

    return jsonify({
        "message": "If an account exists for that email, a reset link has been sent."
    }), 200


@auth_bp.route("/auth/reset-password", methods=["POST"])
def reset_password():
    data = request.get_json() or {}
    token = (data.get("token") or "").strip()
    password = data.get("password")

    ip_limited, ip_retry_after = rate_limit_hit(
        f"reset-password:ip:{client_ip()}",
        RESET_PASSWORD_IP_LIMIT,
        RESET_PASSWORD_WINDOW_SECONDS,
    )
    if ip_limited:
        return _rate_limited_response(ip_retry_after)

    if not token or not password:
        return jsonify({"message": "Token and password are required"}), 400

    if len(token) > MAX_RESET_TOKEN_LENGTH:
        return jsonify({"message": "Invalid reset link"}), 400

    token_limited, token_retry_after = rate_limit_hit(
        f"reset-password:token:{_hash_rate_limit_value(token)}",
        RESET_PASSWORD_TOKEN_LIMIT,
        RESET_PASSWORD_WINDOW_SECONDS,
    )

    if ip_limited or token_limited:
        return _rate_limited_response(max(ip_retry_after, token_retry_after))

    try:
        User.validate_password(password)
    except ValueError as e:
        return jsonify({"message": str(e)}), 422

    try:
        payload = _password_reset_serializer().loads(
            token,
            max_age=RESET_TOKEN_MAX_AGE_SECONDS,
        )
    except SignatureExpired:
        return jsonify({"message": "Reset link has expired"}), 400
    except BadSignature:
        return jsonify({"message": "Invalid reset link"}), 400

    if payload.get("purpose") != "password_reset":
        return jsonify({"message": "Invalid reset link"}), 400

    user = User.query.get(payload.get("user_id"))
    if not user or user.email != payload.get("email"):
        return jsonify({"message": "Invalid reset link"}), 400

    if payload.get("password_hash_digest") != _password_hash_digest(user):
        return jsonify({"message": "Reset link has already been used"}), 400

    original_password_hash = user.password_hash
    updated_count = User.query.filter(
        User.id == user.id,
        User.password_hash == original_password_hash,
    ).update(
        {"password_hash": User.hash_password(password)},
        synchronize_session=False,
    )

    if updated_count != 1:
        db.session.rollback()
        return jsonify({"message": "Reset link has already been used"}), 400

    db.session.commit()

    return jsonify({"message": "Password reset successfully"}), 200


@auth_bp.route("/auth/logout", methods=["POST"])
@jwt_required()
def logout():
    jti = get_jwt()["jti"]

    db.session.add(TokenBlocklist(jti=jti))
    db.session.commit()

    return jsonify({"message": "Successfully logged out"}), 200
