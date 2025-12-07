from db.models import Customers
from db.database import db

def save_customer(data: dict):
    customer = Customers(**data)
    db.session.add(customer)
    db.session.commit()
    return customer
    
def get_customer(sender_id: str):
    if not sender_id:
        return {'error': 'sender_id parameter is required'}, 400

    customer = Customers.query.filter_by(sender_id=sender_id).first()
    return customer
