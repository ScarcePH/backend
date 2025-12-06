from flask import Blueprint, request, jsonify
from db.database import db
from db.models import Customers

customers_bp = Blueprint("customers", __name__)

@customers_bp.post("/customers")
def create_customer():
    data = request.json
    customer = Customers(**data)
    db.session.add(customer)
    db.session.commit()
    return jsonify({"status": "ok", "customer": data})

