from datetime import date

from flask import Blueprint, jsonify, request

from db.repository.purchase import create_purchase, get_purchase, list_purchases
from middleware.auth_required import auth_required


purchases_bp = Blueprint("purchases", __name__)


def _parse_query_date(value, field):
    if value is None:
        return None
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError):
        raise ValueError(f"{field} must use YYYY-MM-DD format")


@purchases_bp.route("/purchases", methods=["POST"])
@auth_required(allowed_roles=["super_admin"])
def create_purchase_record():
    data = request.get_json(silent=True)
    try:
        purchase = create_purchase(data)
    except ValueError as exc:
        return jsonify({"message": str(exc)}), 400
    return jsonify({
        "message": "Purchase record created",
        "purchase": purchase.to_dict(),
    }), 201


@purchases_bp.route("/purchases", methods=["GET"])
@auth_required(allowed_roles=["super_admin"])
def get_purchase_records():
    try:
        start_date = _parse_query_date(request.args.get("start_date"), "start_date")
        end_date = _parse_query_date(request.args.get("end_date"), "end_date")
        limit = int(request.args.get("limit", 100))
        offset = int(request.args.get("offset", 0))
    except ValueError as exc:
        return jsonify({"message": str(exc)}), 400

    if not 1 <= limit <= 500 or offset < 0:
        return jsonify({"message": "limit must be 1-500 and offset must be non-negative"}), 400
    if start_date and end_date and start_date >= end_date:
        return jsonify({"message": "start_date must be earlier than end_date"}), 400

    purchases = list_purchases(start_date, end_date, limit, offset)
    return jsonify({"purchases": [purchase.to_dict() for purchase in purchases]}), 200


@purchases_bp.route("/purchases/<int:purchase_id>", methods=["GET"])
@auth_required(allowed_roles=["super_admin"])
def get_purchase_record(purchase_id):
    purchase = get_purchase(purchase_id)
    if purchase is None:
        return jsonify({"message": "Purchase record not found"}), 404
    return jsonify({"purchase": purchase.to_dict()}), 200
