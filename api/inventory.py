from flask import Blueprint, request, jsonify
from db.database import db
from db.models.inventory import Inventory
from db.repository.inventory import get_all_inventory,save_inventory

inventory_bp = Blueprint("inventory", __name__)

@inventory_bp.route("/create-inventory", methods=["POST"])
def create_inventory():
    data = request.json
    record = save_inventory(data)
    return jsonify({"status": "ok", "inventory": data})

@inventory_bp.route("/get-all-inventory", methods=["GET"])
def fetch_inventory():
    return get_all_inventory()