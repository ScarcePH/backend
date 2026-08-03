from datetime import date
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from flask import Blueprint, jsonify, request
from sqlalchemy.exc import IntegrityError

from db.database import db
from db.models.inventory_variation import InventoryVariation
from db.models.promotion import Promotion
from db.models.promotion_item import PromotionItem
from db.repository.promotion import (
    get_active_promotion,
    manila_now,
    manila_today,
    promotion_query,
    promotion_status,
    serialize_promotion,
)
from middleware.auth_required import auth_required


promotions_bp = Blueprint("promotions", __name__)


class PromotionValidationError(ValueError):
    pass


def _parse_date(value, field):
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError):
        raise PromotionValidationError(f"{field} must use YYYY-MM-DD format")


def _parse_payload(data):
    name = str(data.get("name") or "").strip()
    description = str(data.get("description") or "").strip()
    if not name:
        raise PromotionValidationError("name is required")
    if not description:
        raise PromotionValidationError("description is required")

    start_date = _parse_date(data.get("start_date"), "start_date")
    end_date = _parse_date(data.get("end_date"), "end_date")
    if end_date < start_date:
        raise PromotionValidationError("end_date must be on or after start_date")

    raw_items = data.get("items")
    if not isinstance(raw_items, list) or not raw_items:
        raise PromotionValidationError("at least one promotion item is required")

    parsed_items = []
    variation_ids = []
    for raw_item in raw_items:
        try:
            variation_id = int(raw_item.get("variation_id"))
            promo_price = Decimal(str(raw_item.get("promo_price")))
        except (AttributeError, TypeError, ValueError, InvalidOperation):
            raise PromotionValidationError("each item needs a valid variation_id and promo_price")
        if variation_id in variation_ids:
            raise PromotionValidationError("each variation may only appear once")
        if not promo_price.is_finite() or promo_price <= 0:
            raise PromotionValidationError("promotional prices must be positive")
        if promo_price.as_tuple().exponent < -2:
            raise PromotionValidationError("promotional prices may have at most two decimals")
        variation_ids.append(variation_id)
        parsed_items.append((variation_id, promo_price.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)))

    variations = {
        variation.id: variation
        for variation in InventoryVariation.query.filter(InventoryVariation.id.in_(variation_ids)).all()
    }
    if len(variations) != len(variation_ids):
        raise PromotionValidationError("one or more variations do not exist")
    for variation_id, promo_price in parsed_items:
        if promo_price >= Decimal(str(variations[variation_id].price)):
            raise PromotionValidationError(
                f"promo_price for variation {variation_id} must be below its regular price"
            )

    return {
        "name": name,
        "description": description,
        "start_date": start_date,
        "end_date": end_date,
        "items": parsed_items,
    }


def _overlapping_promotion(start_date, end_date, exclude_id=None):
    query = Promotion.query.filter(
        Promotion.early_ended_at.is_(None),
        Promotion.start_date <= end_date,
        Promotion.end_date >= start_date,
    )
    if exclude_id is not None:
        query = query.filter(Promotion.id != exclude_id)
    return query.first()


def _save_items(promotion, parsed_items):
    promotion.items.clear()
    for variation_id, promo_price in parsed_items:
        promotion.items.append(PromotionItem(
            variation_id=variation_id,
            promo_price=promo_price,
        ))


def _integrity_error_response():
    db.session.rollback()
    return jsonify({
        "message": "Promotion dates overlap another scheduled or active promotion",
        "code": "promotion_overlap",
    }), 409


@promotions_bp.route("/promotions", methods=["GET"])
@auth_required(allowed_roles=["super_admin"])
def list_promotions():
    promotions = promotion_query().order_by(Promotion.start_date.desc(), Promotion.id.desc()).all()
    return jsonify([serialize_promotion(promotion) for promotion in promotions])


@promotions_bp.route("/promotions", methods=["POST"])
@auth_required(allowed_roles=["super_admin"])
def create_promotion():
    try:
        parsed = _parse_payload(request.get_json(silent=True) or {})
    except PromotionValidationError as exc:
        return jsonify({"message": str(exc)}), 400

    if parsed["start_date"] < manila_today():
        return jsonify({"message": "start_date cannot be in the past"}), 400

    if _overlapping_promotion(parsed["start_date"], parsed["end_date"]):
        return _integrity_error_response()

    promotion = Promotion(
        name=parsed["name"],
        description=parsed["description"],
        start_date=parsed["start_date"],
        end_date=parsed["end_date"],
    )
    _save_items(promotion, parsed["items"])
    db.session.add(promotion)
    try:
        db.session.commit()
    except IntegrityError:
        return _integrity_error_response()
    return jsonify(serialize_promotion(promotion)), 201


@promotions_bp.route("/promotions/<int:promotion_id>", methods=["PUT"])
@auth_required(allowed_roles=["super_admin"])
def update_promotion(promotion_id):
    promotion = promotion_query().filter(Promotion.id == promotion_id).one_or_none()
    if not promotion:
        return jsonify({"message": "Promotion not found"}), 404
    status = promotion_status(promotion)
    if status == "ended":
        return jsonify({"message": "Ended promotions are read-only"}), 409

    try:
        parsed = _parse_payload(request.get_json(silent=True) or {})
    except PromotionValidationError as exc:
        return jsonify({"message": str(exc)}), 400
    if status == "active" and parsed["start_date"] != promotion.start_date:
        return jsonify({"message": "An active promotion's start date cannot be changed"}), 409
    if status == "active" and parsed["end_date"] < manila_today():
        return jsonify({"message": "Use end now to end an active promotion"}), 409
    if _overlapping_promotion(parsed["start_date"], parsed["end_date"], promotion.id):
        return _integrity_error_response()

    promotion.name = parsed["name"]
    promotion.description = parsed["description"]
    promotion.start_date = parsed["start_date"]
    promotion.end_date = parsed["end_date"]
    _save_items(promotion, parsed["items"])
    try:
        db.session.commit()
    except IntegrityError:
        return _integrity_error_response()
    return jsonify(serialize_promotion(promotion))


@promotions_bp.route("/promotions/<int:promotion_id>/end", methods=["POST"])
@auth_required(allowed_roles=["super_admin"])
def end_promotion(promotion_id):
    promotion = db.session.get(Promotion, promotion_id)
    if not promotion:
        return jsonify({"message": "Promotion not found"}), 404
    if promotion_status(promotion) != "active":
        return jsonify({"message": "Only an active promotion can be ended"}), 409
    promotion.early_ended_at = manila_now()
    db.session.commit()
    return jsonify(serialize_promotion(promotion))


@promotions_bp.route("/promotions/<int:promotion_id>", methods=["DELETE"])
@auth_required(allowed_roles=["super_admin"])
def delete_promotion(promotion_id):
    promotion = db.session.get(Promotion, promotion_id)
    if not promotion:
        return jsonify({"message": "Promotion not found"}), 404
    if promotion_status(promotion) != "scheduled":
        return jsonify({"message": "Only future promotions can be deleted"}), 409
    db.session.delete(promotion)
    db.session.commit()
    return "", 204


@promotions_bp.route("/promotions/active", methods=["GET"])
def active_promotion():
    promotion = get_active_promotion()
    if not promotion:
        return jsonify({"promotion": None})
    return jsonify({"promotion": serialize_promotion(promotion)})
