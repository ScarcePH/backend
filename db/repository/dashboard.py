from flask import jsonify

from sqlalchemy import func
from datetime import datetime, timedelta
from db.models import Order, Payment
from db.database import db

def dashboard_summary():
    now = datetime.now()

    start_week = now - timedelta(days=now.weekday())
    start_last_week = start_week - timedelta(days=7)

    start_month = now.replace(day=1)
    start_last_month = (start_month - timedelta(days=1)).replace(day=1)

    pending_orders = (
        db.session.query(func.count(Order.id))
        .filter(Order.status == "pending")
        .scalar()
    )

    paid_per_order = (
        db.session.query(
            Payment.order_id,
            func.coalesce(func.sum(Payment.received_amount), 0).label("paid")
        )
        .group_by(Payment.order_id)
        .subquery()
    )

    outstanding_per_order = (
        db.session.query(
            Order.id,
            (
                func.max(Payment.total_amount)
                - func.coalesce(paid_per_order.c.paid, 0)
            ).label("outstanding")
        )
        .outerjoin(paid_per_order, Order.id == paid_per_order.c.order_id)
        .outerjoin(Payment, Payment.order_id == Order.id)
        .group_by(Order.id, paid_per_order.c.paid)
        .subquery()
    )

    outstanding_summary = (
        db.session.query(
            func.coalesce(func.sum(outstanding_per_order.c.outstanding), 0),
            func.count(outstanding_per_order.c.id)
        )
        .filter(outstanding_per_order.c.outstanding > 0)
        .one()
    )

    outstanding_amount, outstanding_count = outstanding_summary

    orders_this_week = (
        db.session.query(func.count(Order.id))
        .filter(
            Order.status == 'confirmed',
            Order.created_at >= start_week
        )
        .scalar()
    )

    orders_last_week = (
        db.session.query(func.count(Order.id))
        .filter(
            Order.status == 'confirmed',
            Order.created_at >= start_last_week,
            Order.created_at < start_week
        )
        .scalar()
    )

    orders_delta = orders_this_week - orders_last_week

    revenue_this_month = (
        db.session.query(func.coalesce(func.sum(Payment.received_amount), 0))
        .filter(Payment.created_at >= start_month)
        .scalar()
    )

    revenue_last_month = (
        db.session.query(func.coalesce(func.sum(Payment.received_amount), 0))
        .filter(
            Payment.created_at >= start_last_month,
            Payment.created_at < start_month
        )
        .scalar()
    )

    revenue_delta = revenue_this_month - revenue_last_month
    return jsonify({

        "pending_orders": pending_orders,
        "outstanding_balance": {
            "amount": outstanding_amount,
            "count": outstanding_count,
        },
        "orders_this_week": {
            "count": orders_this_week,
            "delta": orders_delta,
        },
        "revenue_this_month": {
            "amount": revenue_this_month,
            "delta": revenue_delta,
        }
        
    })
