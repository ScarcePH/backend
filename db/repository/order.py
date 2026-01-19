from db.models import Order
from db.database import db
from db.models import Customers, Inventory, InventoryVariation, Payment, Shipment
from flask import jsonify
from bot.services.messenger import send_carousel, reply
import re
from datetime import datetime
from bot.utils.date import parse_date




def save_order(data: dict):
    order = Order(**data)
    db.session.add(order)
    db.session.commit()
    res = Order.to_dict(order)
    return res

def get_order(sender_id):
    orders = (
        Order.query
        .join(Customers)
        .filter(Customers.sender_id == sender_id)
        .all()
    )
    result = [Order.to_dict(order) for order in orders]
    return result

def get_all_order(status, date_from=None, date_to=None):
    orders = (
        Order.query
        .join(Customers)
    )

    if status != 'all':
        orders = orders.filter(Order.status == status)

    if date_from and date_to:
        orders = orders.filter(
            Order.created_at.between(
                parse_date(date_from),
                parse_date(date_to, end=True)
            )
        )

    orders = orders.order_by(Order.created_at.desc())


    result = [Order.to_dict(order) for order in orders.all()]
    return result

def get_all_confirmed_orders():
    orders = (
        Order.query
        .filter(Order.status == "confirmed")
        .join(Customers)
        .all()
    )
    result = [Order.to_dict(order) for order in orders]

    orders = []
    total = 0
    balance = 0
    for order in result:
        total += order['variation']['price']
        balance += order['payment']['to_settle'] if order['payment'] else 0
        orders.append({
            "customer": order['customer']['name'],
            "pair": re.sub(r"nike sb stefan janoski\s*", "", order['inventory']['name'], flags=re.IGNORECASE),
            "tracking": order['shipment']['tracking'] if order['shipment'] else "pending",
            "balance": order['payment']['to_settle'] if order['payment'] else None,
            "amount": order['variation']['price'],
            "size": order['variation']['size'],
        })
       

    return {
        "orders":orders,
        "total_balance":balance,
        "total":total
    }

def update_order(order_id, status, received_payment, cancel_reason, release):
    order = Order.query.get_or_404(order_id)
    payment = Payment.query.filter_by(order_id=order.id).first()
    order_data = Order.to_dict(order)
    if not payment:
        payment = Payment(
            order_id=order.id,
            received_amount=received_payment,
            total_amount=order_data['variation']['price']  
        )
        db.session.add(payment)
    else:
        payment.received_amount = received_payment
    
    item = InventoryVariation.query.get_or_404(order.variation_id)
    if(status=='confirmed'):
        item.status = "sold"
    if(status=='cancelled' and release):
        item.status = release
    if(status=='completed' and payment):
        payment.received_amount = payment.total_amount

    order.status = status
    db.session.commit()
    
    notif_user = (
        Order.query
        .join(Customers)
        .filter(Order.id == order_id)
        .all()
    )

    result = [Order.to_dict(order) for order in notif_user]
    sender_id = result[0]['customer']['sender_id']
    send_carousel(sender_id, result, is_my_order=True)
    reply(sender_id, f"Your order is {status}. \n {cancel_reason}")

    return jsonify({
        "message": "Order updated",
        "order_id": order.id,
        "status": order.status,
        "payment": payment.received_amount if payment else None
    })
 


    

