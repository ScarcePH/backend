from flask import Blueprint, request, jsonify
from db.database import db
from db.models.inventory import Inventory

inventory_bp = Blueprint("inventory", __name__)

@inventory_bp.route("/inventory", methods=["POST"])
def create_inventory():
    data = request.json
    print(f"[DATA]: {data}")
    inventory = Inventory(**data)
    db.session.add(inventory)
    db.session.commit()
    return jsonify({"status": "ok", "inventory": data})