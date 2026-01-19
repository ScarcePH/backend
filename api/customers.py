from flask import Blueprint, request, jsonify
from db.database import db
from db.repository.customer import save_customer,get_customers
from middleware.admin_required import admin_required

customers_bp = Blueprint("customers", __name__)

@customers_bp.route("/customer/create",  methods=["POST"])
@admin_required(allowed_roles=["super_admin"])
def create_customer():
    data = request.json
    record = save_customer(data)
    return jsonify({"status": "ok", "data": record})



@customers_bp.route("/customer/get-all", methods=["GET"])
@admin_required(allowed_roles=["super_admin"])
def get_all_customer():
    customers = get_customers()
    return jsonify({"status": "ok", "customers": customers})