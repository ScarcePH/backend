from db.models import Order
from db.database import db
from db.models import Customers, Inventory, InventoryVariation, Payment
from flask import jsonify



def save_order(data: dict):
    order = Order(**data)
    db.session.add(order)
    db.session.commit()
    return order

def get_order(sender_id):
    orders = (
        Order.query
        .join(Customers)
        .filter(Customers.sender_id == sender_id)
        .all()
    )
    result = [Order.to_dict(order) for order in orders]
    return result

def get_all_pending_orders():
    orders = (
        Order.query
        .join(Customers)
        .filter(Order.status == "pending")
        .all()
    )
    result = [Order.to_dict(order) for order in orders]
    return result

def update_order(order_id, status, received_payment):
    order = Order.query.get_or_404(order_id)
    payment = Payment.query.filter_by(order_id=order.id).first()
    if payment:
        payment.received_amount = received_payment
    order.status = status
    db.session.commit()
    return jsonify({
        "message": "Order updated",
        "order_id": order.id,
        "status": order.status,
        "payment": payment.received_amount if payment else None
    })
 


    

