from db.models import Customers
from db.models import Leads
from db.database import db

def save_customer(data: dict):
    customer = Customers(**data)
    db.session.add(customer)
    db.session.commit()
    res = Customers.to_dict(customer)
    return res
    
def get_customer(sender_id: str):
    if not sender_id:
        return {'error': 'sender_id parameter is required'}, 400

    customer = Customers.query.filter_by(sender_id=sender_id).first()
    return customer

def update_customer(sender_id: str, name: str = None, phone: str = None, address: str = None):
    if not sender_id:
        return {'error': 'sender_id parameter is required'}, 400
    
    customer = Customers.query.filter_by(sender_id=sender_id).first()
    if not customer:
        return None

    if name is not None:
        customer.name = name
    if phone is not None:
        customer.phone = phone
    if address is not None:
        customer.address = address

    db.session.commit()
    return customer

def create_leads(sender_id, item, size):
    if not sender_id:
        return {'error': 'sender_id parameter is required'}, 400
    
    data= {
        "sender_id":sender_id,
        "name":item,
        "size": size
    }
    lead = Leads(**data)
    db.session.add(lead)
    db.session.commit()
    return lead

def get_customers():
    customers =  Customers.query.all()
    result = [Customers.to_dict(order) for order in customers]
    return result
