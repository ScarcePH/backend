from flask import Blueprint, request, jsonify
from db.database import db
from db.models.inventory import Inventory
from db.repository.inventory import get_all_inventory,save_inventory,search_items,get_item_sizes

inventory_bp = Blueprint("inventory", __name__)

@inventory_bp.route("/create-inventory", methods=["POST"])
def create_inventory():
    data = request.json
    record = save_inventory(data)
    return jsonify({"status": "ok", "inventory": data})

@inventory_bp.route("/get-all-inventory", methods=["GET"])
def fetch_inventory():
    return get_all_inventory()

@inventory_bp.route("/get-inventory-name-size", methods=["GET"])
def fetch_inventory_name_size():
    name = request.args.get('name') 
    size = request.args.get('size')

    if not name:
        return {"message": "Name is required"}, 400
    
  
    result = search_items(name, size)  
    
    return result

@inventory_bp.route("/get-inventory-by-size", methods=["GET"])
def fetch_item_by_size():
    name = request.args.get('name') 
    size = request.args.get('size') 
    if not size:
        return {"message": "Size is required"}, 400
    
    return get_item_sizes(size,name)