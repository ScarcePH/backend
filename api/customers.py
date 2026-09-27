import os

from flask import Blueprint, request, jsonify
import requests
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


@customers_bp.route("/customer/get-messenger-customer", methods=["GET"])
@auth_required(allowed_roles=["super_admin"])
def get_messenger_customer():
    APP_SENDER_ID = os.environ.get("APP_SENDER_ID")
    PAGE_ACCESS_TOKEN = os.environ.get("PAGE_ACCESS_TOKEN")
    url = "https://graph.facebook.com/v18.0/"+APP_SENDER_ID+"/conversations?fields=participants{id}&access_token="+PAGE_ACCESS_TOKEN
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        customer_data = [conversation["participants"]["data"][0] for conversation in data.get("data", [])]
        return customer_data

    return jsonify({"status":"error","message":"Failed to fetch messenger customers"}), response.status_code
