from datetime import datetime
from decimal import Decimal, InvalidOperation
import logging

from flask import jsonify
from db.database import db
from db.models.checkout_session import CheckoutSession
from db.models.inventory import Inventory
from db.models.inventory_variation import InventoryVariation
from db.models.order import Order
from db.models.order_item import OrderItem
from db.models.payment import Payment
from db.repository.customer_service import get_or_create_customer
from db.repository.inventory import is_variation_sellable
from bot.services.messenger import send_carousel, reply
from task.email import enqueue_email
from bot.observability import increment
from db.repository.promotion import active_promotion_prices


logger = logging.getLogger(__name__)


class InventoryUnavailableError(ValueError):
    pass


def abandon_checkout_session(session_id, reason="Customer cancelled checkout"):
    session = (
        CheckoutSession.query
        .filter_by(id=session_id)
        .with_for_update()
        .one_or_none()
    )
    if not session:
        return {"message": "Checkout session not found"}, 404
    if session.status in ("pending", "proof_submitted"):
        session.status = "expired"
        session.rejection_reason = reason
        db.session.commit()
        return {"session": session}, 200
    if session.status == "expired":
        return {"session": session}, 200
    return {"message": f"Checkout session already {session.status}"}, 409


def _authoritative_items(session, lock=False):
    """Revalidate inventory while preserving prices locked when checkout started."""
    raw_items = session.items_json or []
    variation_ids = sorted({item.get("variation_id") for item in raw_items if item.get("variation_id")})
    query = InventoryVariation.query.filter(InventoryVariation.id.in_(variation_ids))
    if lock:
        query = query.order_by(InventoryVariation.id).with_for_update()
    variations = {variation.id: variation for variation in query.all()}

    refreshed = []
    total = Decimal("0")
    for item in raw_items:
        try:
            quantity = int(item.get("qty", 0))
        except (TypeError, ValueError):
            quantity = 0
        variation = variations.get(item.get("variation_id"))
        if (
            not variation
            or quantity < 1
            or variation.inventory_id != item.get("inventory_id")
            or not is_variation_sellable(variation)
            or variation.stock < quantity
        ):
            raise InventoryUnavailableError("One or more checkout items are no longer available")
        try:
            price = Decimal(str(item["price"]))
        except (KeyError, InvalidOperation, TypeError, ValueError):
            raise ValueError("Checkout contains an invalid locked price")
        if not price.is_finite() or price <= 0:
            raise ValueError("Checkout contains an invalid locked price")
        total += price * quantity
        refreshed.append({
            "inventory_id": variation.inventory_id,
            "variation_id": variation.id,
            "qty": quantity,
            "price": float(price),
            "regular_price": item.get("regular_price"),
            "promotion_id": item.get("promotion_id"),
        })
    if not refreshed:
        raise ValueError("Checkout has no items")
    return refreshed, total, variations


def submit_checkout_for_review(session_id, payment_method=None, expected_amount=None):
    """Refresh an uploaded-proof checkout without creating an order or payment."""
    session = (
        CheckoutSession.query
        .filter_by(id=session_id)
        .with_for_update()
        .one_or_none()
    )
    if not session:
        return {"message": "Checkout session not found"}, 404
    if session.status == "approved":
        return {"message": "Checkout session already approved"}, 409
    if session.status == "rejected":
        return {"message": "Checkout session already rejected"}, 409
    if session.is_expired():
        session.status = "expired"
        db.session.commit()
        return {"message": "Checkout session expired"}, 409
    if session.status != "proof_submitted":
        return {"message": "Payment proof has not been submitted"}, 409

    try:
        items, total, _ = _authoritative_items(session)
        session.items_json = items
        session.total_price = total
        if payment_method:
            session.payment_method = payment_method
        if expected_amount is not None:
            amount = Decimal(str(expected_amount))
            if amount < 0:
                raise ValueError("Expected payment amount cannot be negative")
            session.expected_payment_amount = min(amount, total)
        elif session.expected_payment_amount is None:
            session.expected_payment_amount = total
        db.session.commit()
    except (ValueError, InvalidOperation) as exc:
        db.session.rollback()
        return {"message": str(exc)}, 409
    return {"session": session}, 200

def start_checkout(items: list[dict], customer_id=None, user_id=None, guest_id=None, sender_id=None):
    
    if not isinstance(items, list):
        return {"error": "items must be a list of objects"}

    customer = get_or_create_customer(
        customer_id=customer_id,
        user_id=user_id,
        guest_id=guest_id,
        sender_id=sender_id
    )

    if not customer:
        return jsonify({"error": "Unable to resolve customer"}), 400

    validated_items = []
    total = Decimal("0")
    promotion, promotion_prices = active_promotion_prices()

    for item in items:
        try:
            quantity = int(item["qty"])
            variation_id = int(item["variation_id"])
        except (KeyError, TypeError, ValueError):
            return jsonify({"error": "Invalid checkout item"}), 400
        variation = InventoryVariation.query.get(variation_id)

        if quantity < 1 or not variation or not is_variation_sellable(variation) or variation.stock < quantity:
            return jsonify({"error": "Item unavailable"}), 400

        supplied_inventory_id = item.get("inventory_id")
        if supplied_inventory_id is not None:
            try:
                supplied_inventory_id = int(supplied_inventory_id)
            except (TypeError, ValueError):
                return jsonify({"error": "Invalid checkout item"}), 400
            if variation.inventory_id != supplied_inventory_id:
                return jsonify({"error": "Variation does not belong to inventory item"}), 400

        price = promotion_prices.get(variation.id, variation.price)
        total += price * quantity

        validated_items.append({
            "inventory_id": variation.inventory_id,
            "variation_id": variation.id,
            "qty": quantity,
            "price": float(price),
            "regular_price": float(variation.price),
            "promotion_id": promotion.id if promotion and variation.id in promotion_prices else None,
        })

    existing_session = (
        CheckoutSession.query
        .filter(CheckoutSession.customer_id == customer.id)
        .filter(CheckoutSession.status == "pending")
        .filter(CheckoutSession.expires_at > datetime.utcnow())
        .order_by(CheckoutSession.created_at.desc())
        .first()
    )

    if existing_session:
        if existing_session.items_json == validated_items:
            return {"checkout_session_id": str(existing_session.id)}
        existing_session.status = "expired"


    if(customer_id):
        session = CheckoutSession(
            customer_id=customer.id,
            items_json=validated_items,
            total_price=total,
            status='added_by_admin'
        )
    else:
        session = CheckoutSession(
            customer_id=customer.id,
            items_json=validated_items,
            total_price=total
        )



    db.session.add(session)
    db.session.commit()

    return {"checkout_session_id": str(session.id), "items":session.items_json}


def _send_approval_notifications(session, order_data, paid):
    approved_items = []
    for item in session.items_json or []:
        inventory = Inventory.query.get(item.get("inventory_id"))
        variation = InventoryVariation.query.get(item["variation_id"])
        approved_items.append({
            "image_url": inventory.image if inventory else None,
            "name": inventory.name if inventory else "Item",
            "condition": variation.condition if variation else None,
            "size": f"{variation.size}us" if variation and variation.size else None,
            "price": str(item.get("price")) if item.get("price") is not None else None,
        })
    if session.customer and session.customer.email:
        enqueue_email({
            "type": "approve_payment",
            "to": session.customer.email,
            "template_variables": {
                "customer_name": session.customer.name or "Customer",
                "items": approved_items,
                "total": str(session.total_price),
                "remaining_balance": str(session.total_price - paid),
                "fulfillment_eta": "3-8 days",
                "year": str(datetime.utcnow().year),
                "store_name": "Scarceᴾᴴ",
            },
        }, task_id=f"checkout-approved-{session.id}")
    if session.customer and session.customer.sender_id:
        if order_data.get("items"):
            send_carousel(session.customer.sender_id, [order_data], is_my_order=True)
        reply(session.customer.sender_id, "Your order is approved.", None)


def _send_rejection_notifications(session):
    reason = session.rejection_reason or "Payment could not be validated"
    declined_items = []
    for item in session.items_json or []:
        inventory = Inventory.query.get(item.get("inventory_id"))
        variation = InventoryVariation.query.get(item["variation_id"])
        declined_items.append({
            "image_url": inventory.image if inventory else None,
            "name": inventory.name if inventory else "Item",
            "category": variation.condition if variation else None,
            "size": f"{variation.size}us" if variation and variation.size else None,
            "price": str(item.get("price")) if item.get("price") is not None else None,
        })
    if session.customer and session.customer.sender_id:
        reply(session.customer.sender_id, f"Your checkout was rejected. Reason: {reason}", None)
    if session.customer and session.customer.email:
        enqueue_email({
            "type": "decline_payment",
            "to": session.customer.email,
            "template_variables": {
                "customer_name": session.customer.name or "Customer",
                "decline_reason": reason,
                "items": declined_items,
                "total": str(session.total_price),
                "year": str(datetime.utcnow().year),
                "store_name": "Scarceᴾᴴ",
            },
        }, task_id=f"checkout-rejected-{session.id}")


def approve_checkout_session(session_id, received_amount=None):
    session = (
        CheckoutSession.query
        .filter_by(id=session_id)
        .with_for_update()
        .one_or_none()
    )
    if not session:
        return {"message": "Checkout session not found"}, 404

    if session.orders:
        order_data = session.orders.to_dict()
        payment = Payment.query.filter_by(order_id=session.orders.id).first()
        paid = payment.received_amount if payment else Decimal("0")
        try:
            _send_approval_notifications(session, order_data, paid)
        except Exception:
            logger.exception("approval_notification_failed", extra={"checkout_id": str(session.id)})
            return {"message": "Order approved; notification delivery is pending"}, 503
        return {"session": session, "order": order_data}, 200
    if session.status in ("rejected", "expired"):
        return {
            "message": f"Checkout session already {session.status}",
            "id": str(session.id),
            "status": session.status,
        }, 409
    if session.status != "added_by_admin" and session.is_expired():
        session.status = "expired"
        db.session.commit()
        return {
            "message": "Checkout session expired",
            "id": str(session.id),
            "status": session.status,
        }, 409
    if session.status not in ("proof_submitted", "added_by_admin"):
        return {"message": "Checkout session is not ready for approval"}, 409

    try:
        items, total, variations = _authoritative_items(session, lock=True)
        session.items_json = items
        session.total_price = total
        session.approve()

        order = Order(
            customer_id=session.customer_id,
            checkout_session_id=session.id,
            total_price=total,
            status="confirmed",
        )
        db.session.add(order)
        db.session.flush()

        for item in items:
            variation = variations[item["variation_id"]]
            variation.stock -= item["qty"]
            if variation.stock == 0:
                variation.status = "sold"
            db.session.add(OrderItem(
                order_id=order.id,
                inventory_id=item["inventory_id"],
                variation_id=item["variation_id"],
                quantity=item["qty"],
                price_at_purchase=item["price"],
            ))

        paid = (
            Decimal(str(received_amount))
            if received_amount is not None
            else (session.expected_payment_amount or total)
        )
        if paid < 0 or paid > total:
            raise ValueError("Received payment amount must be between zero and the order total")
        db.session.add(Payment(
            order_id=order.id,
            total_amount=total,
            received_amount=paid,
            payment_ss=session.proof_image_url,
            payment_method=session.payment_method,
        ))
        db.session.commit()
        increment("checkout_approvals")
    except InventoryUnavailableError as exc:
        db.session.rollback()
        unavailable_session = (
            CheckoutSession.query
            .filter_by(id=session_id)
            .with_for_update()
            .one_or_none()
        )
        if unavailable_session and unavailable_session.status == "proof_submitted":
            unavailable_session.reject("Item became unavailable before approval")
            db.session.commit()
            increment("checkout_rejections")
            try:
                _send_rejection_notifications(unavailable_session)
            except Exception:
                logger.exception(
                    "stock_loss_notification_failed",
                    extra={"checkout_id": str(session_id)},
                )
                return {
                    "message": "Checkout rejected; notification delivery is pending",
                    "id": str(session_id),
                    "status": unavailable_session.status,
                }, 503
        return {
            "message": str(exc),
            "id": str(session_id),
            "status": unavailable_session.status if unavailable_session else "unavailable",
        }, 409
    except (ValueError, InvalidOperation) as exc:
        db.session.rollback()
        return {
            "message": str(exc),
            "id": str(session.id),
            "status": session.status
        }, 409
    except Exception as exc:
        db.session.rollback()
        logger.exception("checkout_approval_failed", extra={"checkout_id": str(session_id)})
        return {
            "message": "Failed to approve checkout",
            "id": str(session.id),
            "status": session.status
        }, 500

    order_data = order.to_dict()

    try:
        _send_approval_notifications(session, order_data, paid)
    except Exception:
        logger.exception("approval_notification_failed", extra={"checkout_id": str(session.id)})
        return {"message": "Order approved; notification delivery is pending"}, 503

    return {"session": session, "order": order_data}, 200


def reject_checkout_session(session_id, reject_reason=None):
    session = (
        CheckoutSession.query
        .filter_by(id=session_id)
        .with_for_update()
        .one_or_none()
    )
    if not session:
        return {"message": "Checkout session not found"}, 404

    if session.status == "rejected":
        try:
            _send_rejection_notifications(session)
        except Exception:
            logger.exception("rejection_notification_failed", extra={"checkout_id": str(session.id)})
            return {"message": "Checkout rejected; notification delivery is pending"}, 503
        return {"session": session}, 200
    if session.status in ("approved", "expired"):
        return {
            "message": f"Checkout session already {session.status}",
            "id": str(session.id),
            "status": session.status,
        }, 409

    try:
        session.reject(reject_reason)
    except ValueError as exc:
        return {
            "message": str(exc),
            "id": str(session.id),
            "status": session.status
        }, 400

    db.session.commit()
    increment("checkout_rejections")

    try:
        _send_rejection_notifications(session)
    except Exception:
        logger.exception("rejection_notification_failed", extra={"checkout_id": str(session.id)})
        return {"message": "Checkout rejected; notification delivery is pending"}, 503

    return {"session": session}, 200
