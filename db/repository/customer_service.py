from db.models import Customers
from db.database import db


def get_or_create_customer(customer_id=None, user_id=None, guest_id=None, sender_id=None):
    if customer_id:
        customer = Customers.query.filter_by(id=customer_id).first()
        if customer:
            return customer
    if sender_id:
        customer = Customers.query.filter_by(sender_id=sender_id).first()
        if customer:
            return customer
        customer = Customers(sender_id=sender_id)
        db.session.add(customer)
        db.session.commit()
        return customer

    if user_id:
        customer = Customers.query.filter_by(user_id=user_id).first()
        if customer:
            return customer
        customer = Customers(user_id=user_id)
        db.session.add(customer)
        db.session.commit()
        return customer

    if guest_id:
        customer = Customers.query.filter_by(guest_id=guest_id).first()
        if customer:
            return customer
        customer = Customers(guest_id=guest_id)
        db.session.add(customer)
        db.session.commit()
        return customer

    raise Exception("No identity provided")



