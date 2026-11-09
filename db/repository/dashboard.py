from flask import jsonify
from sqlalchemy import func
from datetime import datetime, timedelta
from decimal import Decimal, ROUND_DOWN
from db.database import db
from db.models import (
    Order,
    OrderItem,
    Payment,
    InventoryVariation,
    CheckoutSession,
    Purchase,
)
from db.repository.purchase import fifo_inventory_accounting
from sqlalchemy.orm import selectinload
from dateutil.relativedelta import relativedelta

from db.models.inventory import Inventory


CENT = Decimal("0.01")


def _to_local_naive_datetime(value):
    if value.tzinfo is None:
        return value
    return value.astimezone().replace(tzinfo=None)


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
        .filter(
            Order.status.in_(VALID_STATUS),
            Payment.received_amount < Payment.total_amount
        )
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
        .filter(
            Payment.created_at >= start_month,
        )
        .filter(
            Payment.order_id.in_(
                db.session.query(Order.id)
                .filter(Order.status.in_(["completed"]))
            )
        )
        .scalar()
    )

    revenue_last_month = (
        db.session.query(func.coalesce(func.sum(Payment.received_amount), Decimal("0.00")))
        .filter(
            Payment.created_at >= start_last_month,
            Payment.created_at < start_month
        )
        .filter(
            Payment.order_id.in_(
                db.session.query(Order.id)
                .filter(Order.status.in_(["completed"]))
            )
        )
        .scalar()
    )

    revenue_delta = revenue_this_month - revenue_last_month


    fifo_costs, remaining_cost_by_variation = fifo_inventory_accounting()
    completed_order_items = (
        db.session.query(OrderItem, Order.created_at)
        .join(Order, OrderItem.order_id == Order.id)
        .filter(Order.status == "completed")
        .all()
    )
    total_spent_this_month = sum(
        (
            fifo_costs.get(item.id, {}).get("cost", Decimal("0.00"))
            for item, created_at in completed_order_items
            if _to_local_naive_datetime(created_at) >= start_month
        ),
        Decimal("0.00"),
    )
    total_spent_last_month = sum(
        (
            fifo_costs.get(item.id, {}).get("cost", Decimal("0.00"))
            for item, created_at in completed_order_items
            if start_last_month <= _to_local_naive_datetime(created_at) < start_month
        ),
        Decimal("0.00"),
    )


    this_month_cost_complete = all(
        fifo_costs.get(item.id, {}).get("complete", False)
        for item, created_at in completed_order_items
        if _to_local_naive_datetime(created_at) >= start_month
    )
    last_month_cost_complete = all(
        fifo_costs.get(item.id, {}).get("complete", False)
        for item, created_at in completed_order_items
        if start_last_month <= _to_local_naive_datetime(created_at) < start_month
    )
    this_month_net_profit = (
        revenue_this_month - total_spent_this_month
        if this_month_cost_complete else None
    )
    last_month_net_profit = (
        revenue_last_month - total_spent_last_month
        if last_month_cost_complete else None
    )

    stocked_variation_ids = {
        variation_id
        for (variation_id,) in db.session.query(InventoryVariation.id).filter(
            InventoryVariation.status.in_(["onhand", "preorder"])
        )
    }
    total_spent = sum(
        (
            cost
            for variation_id, cost in remaining_cost_by_variation.items()
            if variation_id in stocked_variation_ids
        ),
        Decimal("0.00"),
    )

    total_value_in_stocks_profit = (
            db.session.query(func.coalesce(func.sum(InventoryVariation.price), Decimal("0.00")))
            .filter(InventoryVariation.status.in_(["onhand", "preorder"]))
            .scalar()
    )

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
            "amount": (
                float(this_month_net_profit)
                if this_month_net_profit is not None
                else None
            ),
            "spent": float(total_spent_this_month),
            "cost_data_complete": this_month_cost_complete,
            "delta": (
                float(this_month_net_profit - last_month_net_profit)
                if this_month_net_profit is not None
                and last_month_net_profit is not None
                else None
            )
        },
        "total_value_in_stocks": float(total_spent),
        "total_value_in_stocks_profit": float(total_value_in_stocks_profit - total_spent),
    })

def last_6_months_sale_bar_chart():
    now = datetime.now()
    start_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    fifo_costs, _ = fifo_inventory_accounting()
    completed_order_items = (
        db.session.query(OrderItem, Order.created_at)
        .join(Order, OrderItem.order_id == Order.id)
        .filter(Order.status == "completed")
        .all()
    )
    months = []
    for i in range(6):
        month_start = (start_month - timedelta(days=i * 30)).replace(day=1)
        month_end = (month_start + timedelta(days=32)).replace(day=1)

        cost = sum(
            (
                fifo_costs.get(item.id, {}).get("cost", Decimal("0.00"))
                for item, created_at in completed_order_items
                if month_start <= _to_local_naive_datetime(created_at) < month_end
            ),
            Decimal("0.00"),
        )
        cost_complete = all(
            fifo_costs.get(item.id, {}).get("complete", False)
            for item, created_at in completed_order_items
            if month_start <= _to_local_naive_datetime(created_at) < month_end
        )

        received = (
            db.session.query(func.coalesce(func.sum(Payment.received_amount), Decimal("0.00")))
            .filter(
                Payment.created_at >= month_start,
                Payment.created_at < month_end
            )
            .filter(
                Payment.order_id.in_(
                    db.session.query(Order.id)
                    .filter(Order.status.in_(["completed"]))
                )
            )
            .scalar()
        )
        profit = received - cost if cost_complete else None

        months.append({
            "month": month_start.strftime("%b"),
            "cost": float(cost),
            "profit": float(profit) if profit is not None else None,
            "cost_data_complete": cost_complete,
        })



    return jsonify(months[::-1]) 

def last_3_months_cc_statement():
    now = datetime.now()

    if now.day >= 26:
        current_period_start = now.replace(
            day=26, hour=0, minute=0, second=0, microsecond=0
        )
    else:
        previous_month = now - relativedelta(months=1)
        current_period_start = previous_month.replace(
            day=26, hour=0, minute=0, second=0, microsecond=0
        )

    periods = []
    purchases = (
        Purchase.query.options(selectinload(Purchase.items))
        .order_by(Purchase.purchase_date, Purchase.id)
        .all()
    )

    for i in range(2, -1, -1):
        period_start = current_period_start - relativedelta(months=i)
        period_end = period_start + relativedelta(months=1)

        period_end = period_end.replace(day=26)

        cost = sum(
            (
                Decimal(str(purchase.to_dict()["total_cost"]))
                for purchase in purchases
                if period_start.date() <= purchase.purchase_date < period_end.date()
            ),
            Decimal("0.00"),
        )

        payment_received = (
            db.session.query(
                func.coalesce(
                    func.sum(Payment.received_amount),
                    Decimal("0.00")
                )
            )
            .filter(
                Payment.created_at >= period_start,
                Payment.created_at < period_end
            )
            .scalar()
        )


        label = (
            f"{period_start.strftime('%b %d')} - "
            f"{(period_end - timedelta(days=1)).strftime('%b %d')}"
        )

        periods.append({
            "month": label,
            "cost": float(cost),
            "payment_received": float(payment_received),
            
        })

    return jsonify(periods)

def purchase_statement(start_date, end_date):
    query = Purchase.query.order_by(Purchase.purchase_date, Purchase.id)
    if start_date is not None:
        query = query.filter(Purchase.purchase_date >= start_date)
    if end_date is not None:
        query = query.filter(Purchase.purchase_date < end_date)

    result = []
    for purchase in query.all():
        purchase_data = purchase.to_dict()
        for item in purchase_data["items"]:
            result.append({
                "purchase_id": purchase.id,
                "supplier": purchase.supplier,
                "variation_id": item["variation_id"],
                "inventory_name": item["inventory_name"],
                "condition": item["condition"],
                "size": item["size"],
                "date": purchase.purchase_date.strftime("%b %d"),
                "purchase_date": purchase.purchase_date.isoformat(),
                "quantity": item["quantity"],
                "unit_cost": item["unit_cost"],
                "allocated_fees": item["allocated_fees"],
                "total_spent": item["actual_total_cost"],
                "total_price": item["listed_total"],
            })

    total_spent = sum(row["total_spent"] for row in result)
    total_price = sum(row["total_price"] for row in result)

    return jsonify({"data": result, "total_spent": float(total_spent), "total_price": float(total_price)})

def income_statement(start_date, end_date):
    fifo_costs, _ = fifo_inventory_accounting()
    income = (
        db.session.query(
            OrderItem,
            Order,
            Payment,
            InventoryVariation,
            Inventory,
        )
        .join(Order, OrderItem.order_id == Order.id)
        .join(Payment, Payment.order_id == Order.id)
        .join(InventoryVariation, OrderItem.variation_id == InventoryVariation.id)
        .join(Inventory, InventoryVariation.inventory_id == Inventory.id)
        .filter(
            Order.status.in_(["completed", "confirmed"]),
            Payment.created_at >= start_date,
            Payment.created_at < end_date,
        )
        .order_by(Payment.created_at, Order.id, OrderItem.id)
        .all()
    )

    items_by_order = {}
    for row in income:
        items_by_order.setdefault(row[1].id, []).append(row)
    received_allocations = {}
    for order_rows in items_by_order.values():
        order_total = sum(
            (
                Decimal(row[0].price_at_purchase) * row[0].quantity
                for row in order_rows
            ),
            Decimal("0.00"),
        )
        total_received = Decimal(order_rows[0][2].received_amount or 0)
        allocations = []
        if order_total:
            for row in order_rows:
                line_revenue = Decimal(row[0].price_at_purchase) * row[0].quantity
                allocations.append(total_received * line_revenue / order_total)
        else:
            allocations = [Decimal("0.00") for _ in order_rows]

        rounded_allocations = [
            amount.quantize(CENT, rounding=ROUND_DOWN)
            for amount in allocations
        ]
        remaining_cents = int(
            (total_received - sum(rounded_allocations, Decimal("0.00"))) / CENT
        )
        remainder_order = sorted(
            range(len(order_rows)),
            key=lambda index: (
                allocations[index] - rounded_allocations[index],
                -index,
            ),
            reverse=True,
        )
        for index in remainder_order[:remaining_cents]:
            rounded_allocations[index] += CENT
        for row, amount in zip(order_rows, rounded_allocations):
            received_allocations[row[0].id] = amount

    result = []
    for order_item, order, payment, variation, inventory in income:
        payment_date = payment.created_at
        revenue = Decimal(order_item.price_at_purchase) * order_item.quantity
        cost_info = fifo_costs.get(order_item.id, {})
        cogs = cost_info.get("cost", Decimal("0.00"))
        cost_complete = cost_info.get("complete", False)
        result.append({
            "order_id": order.id,
            "order_item_id": order_item.id,
            "variation_id": variation.id,
            "inventory_name": inventory.name,
            "date": payment_date.strftime("%b %d"),
            "condition": variation.condition,
            "size": variation.size,
            "quantity": order_item.quantity,
            "total_received": float(received_allocations[order_item.id]),
            "total_revenue": float(revenue),
            "total_spent": float(cogs),
            "cost_data_complete": cost_complete,
            "net_profit": float(revenue - cogs) if cost_complete else None,
        })

    total_received = sum(
        (Decimal(str(row["total_received"])) for row in result),
        Decimal("0.00"),
    )
    total_revenue = sum(
        (Decimal(str(row["total_revenue"])) for row in result),
        Decimal("0.00"),
    )
    total_spent = sum(
        (Decimal(str(row["total_spent"])) for row in result),
        Decimal("0.00"),
    )
    cost_data_complete = all(row["cost_data_complete"] for row in result)
    total_net_profit = (
        total_revenue - total_spent if cost_data_complete else None
    )

    return jsonify({
        "data": result,
        "total_received": float(total_received),
        "total_revenue": float(total_revenue),
        "total_spent": float(total_spent),
        "total_net_profit": (
            float(total_net_profit) if total_net_profit is not None else None
        ),
        "cost_data_complete": cost_data_complete,
    })