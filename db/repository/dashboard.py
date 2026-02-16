from flask import jsonify
from sqlalchemy import func
from datetime import datetime, timedelta
from decimal import Decimal
from db.database import db
from db.models import Order, OrderItem, Payment, InventoryVariation, CheckoutSession


def dashboard_summary():
    now = datetime.now()

    start_week = (now - timedelta(days=now.weekday())).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    start_last_week = start_week - timedelta(days=7)

    start_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    start_last_month = (start_month - timedelta(days=1)).replace(day=1)

    VALID_STATUS = ["confirmed", "completed"]

 
    pending_orders = (
        CheckoutSession.query
        .filter_by(status="proof_submitted")
        .count()
    )


    outstanding_amount, outstanding_count = (
        db.session.query(
            func.coalesce(func.sum(Payment.total_amount - Payment.received_amount), Decimal("0.00")),
            func.count(Payment.id)
        )
        .join(Order)
        .filter(Payment.received_amount < Payment.total_amount)
        .one()
    )


    orders_this_week = (
        db.session.query(func.count(Order.id))
        .filter(
            Order.status.in_(VALID_STATUS),
            Order.created_at >= start_week
        )
        .scalar()
    )

    orders_last_week = (
        db.session.query(func.count(Order.id))
        .filter(
            Order.status.in_(VALID_STATUS),
            Order.created_at >= start_last_week,
            Order.created_at < start_week
        )
        .scalar()
    )

    orders_delta = orders_this_week - orders_last_week


    revenue_this_month = (
        db.session.query(func.coalesce(func.sum(Payment.received_amount), Decimal("0.00")))
        .filter(Payment.created_at >= start_month)
        .scalar()
    )

    revenue_last_month = (
        db.session.query(func.coalesce(func.sum(Payment.received_amount), Decimal("0.00")))
        .filter(
            Payment.created_at >= start_last_month,
            Payment.created_at < start_month
        )
        .scalar()
    )

    revenue_delta = revenue_this_month - revenue_last_month


    total_spent_this_month = (
        db.session.query(
            func.coalesce(func.sum(OrderItem.quantity * InventoryVariation.spent), Decimal("0.00"))
        )
        .join(Order, OrderItem.order_id == Order.id)
        .join(InventoryVariation, OrderItem.variation_id == InventoryVariation.id)
        .filter(
            Order.status.in_(VALID_STATUS),
            Order.created_at >= start_month
        )
        .scalar()
    )


    total_spent_last_month = (
        db.session.query(
            func.coalesce(func.sum(OrderItem.quantity * InventoryVariation.spent), Decimal("0.00"))
        )
        .join(Order, OrderItem.order_id == Order.id)
        .join(InventoryVariation, OrderItem.variation_id == InventoryVariation.id)
        .filter(
            Order.status.in_(VALID_STATUS),
            Order.created_at >= start_last_month,
            Order.created_at < start_month
        )
        .scalar()
    )


    this_month_net_profit = revenue_this_month - total_spent_this_month
    last_month_net_profit = revenue_last_month - total_spent_last_month

    return jsonify({
        "pending_orders": pending_orders,

        "outstanding_balance": {
            "amount": float(outstanding_amount),
            "count": outstanding_count,
        },

        "orders_this_week": {
            "count": orders_this_week,
            "delta": orders_delta,
        },

        "revenue_this_month": {
            "amount": float(revenue_this_month),
            "delta": float(revenue_delta),
        },

        "net_profit_this_month": {
            "amount": float(this_month_net_profit),
            "spent": float(total_spent_this_month),
            "delta": float(this_month_net_profit - last_month_net_profit)
        }
    })
