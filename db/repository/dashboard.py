from flask import jsonify

from sqlalchemy import func
from datetime import datetime, timedelta
from db.models import Order, Payment, InventoryVariation
from db.database import db
from decimal import Decimal


def dashboard_summary():
    now = datetime.now()

    start_week = now - timedelta(days=now.weekday())
    start_week = start_week.replace(hour=0, minute=0, second=0, microsecond=0)
    start_last_week = start_week - timedelta(days=7)

    start_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    start_last_month = (start_month - timedelta(days=1)).replace(day=1)

    VALID_STATUS = ['confirmed', 'completed']

    pending_orders = (
        Order.query
        .filter_by(status="pending")
        .count()
    )

    orders_with_payments = (
        Order.query
        .all()
    )

    outstanding_amount = 0
    outstanding_count = 0

    for order in orders_with_payments:
        if not order.payment:
            continue

        total = order.payment.total_amount
        received = order.payment.received_amount or 0
        outstanding = total - received

        if outstanding > 0:
            outstanding_amount += outstanding
            outstanding_count += 1

    orders_this_week = (
        Order.query
        .filter(
            Order.status.in_(VALID_STATUS),
            Order.created_at >= start_week
        )
        .count()
    )

    orders_last_week = (
        Order.query
        .filter(
            Order.status.in_(VALID_STATUS),
            Order.created_at >= start_last_week,
            Order.created_at < start_week
        )
        .count()
    )

    orders_delta = orders_this_week - orders_last_week

    revenue_this_month = (
        db.session.query(
            func.coalesce(
                func.sum(Payment.received_amount),
                Decimal("0.00")
            )
        )
        .filter(Payment.created_at >= start_month)
        .scalar()
    )

    revenue_last_month = (
        db.session.query(
            func.coalesce(
                func.sum(Payment.received_amount),
                Decimal("0.00")
            )
        )
        .filter(
            Payment.created_at >= start_last_month,
            Payment.created_at < start_month
        )
        .scalar()
    )

    revenue_delta = revenue_this_month - revenue_last_month




    total_spent_this_month = Decimal("0.00")

    completed_orders_this_month = (
        Order.query
        .filter(
            Order.status.in_(VALID_STATUS),
            Order.created_at >= start_month
        )
        .all()
    )

    for order in completed_orders_this_month:
        if not order.variation or not order.variation.spent:
            continue
        total_spent_this_month += order.variation.spent


    this_month_net_profit = revenue_this_month - total_spent_this_month

    completed_orders_last_month = (
        Order.query
        .filter(
            Order.status.in_(VALID_STATUS),
            Order.created_at >= start_last_month,
            Order.created_at < start_month

        )
        .all()
    )
    total_spent_last_month = 0
    for order in completed_orders_last_month:
        if not order.variation:
            continue
        total_spent_last_month +=  order.variation.spent or 0

    last_month_net_profit = Decimal(revenue_last_month) - Decimal(total_spent_last_month)

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
        },
        "net_profit_this_month": {
            "amount": this_month_net_profit,
            "spent": total_spent_this_month,
            "delta": this_month_net_profit - last_month_net_profit
        }
    })