from flask import Blueprint, request, jsonify
from db.database import db
from db.repository.customer import save_customer
from middleware.auth_required import auth_required
from db.models import Customers

customers_bp = Blueprint("customers", __name__)

@customers_bp.route("/customer/create",  methods=["POST"])
@auth_required(allowed_roles=["super_admin"])
def create_customer():
    data = request.json
    record = save_customer(data)
    return jsonify({"status": "ok", "data": record})



@customers_bp.route("/customer/get-all-from-messenger", methods=["GET"])
@auth_required(allowed_roles=["super_admin"])
def get_all_customer():
    customers = Customers.query.filter(Customers.sender_id.isnot(None)).all()
    result = [Customers.to_dict(customer) for customer in customers]
    return jsonify({"status": "ok", "customers": result})

