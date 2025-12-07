from flask import Blueprint, request, jsonify
from db.database import db
from db.repository.customer import save_customer,get_customer
customers_bp = Blueprint("customers", __name__)

@customers_bp.route("/customers",  methods=["POST"])
def create_customer():
    data = request.json
    record = save_customer(data)
    return jsonify({"status": "ok", "inventory": data})

@customers_bp.route("/get_customer", methods=["POST"])
def get_customer():
    request.args.get('sender_id')
    record = get_customer
