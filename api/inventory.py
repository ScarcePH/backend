from flask import Blueprint, request, jsonify
from db.database import db
from db.models.inventory import Inventory
from db.repository.inventory import (
    get_all_inventory,
    save_inventory,
    get_item_sizes,
    save_variation,
    get_inventory_with_size,
    get_all_available_inventory
)
from middleware.admin_required import admin_required

inventory_bp = Blueprint("inventory", __name__)

@inventory_bp.route("inventory/create", methods=["POST"])
@admin_required(allowed_roles=["super_admin"])
def create_inventory():
    data = request.json
    item = save_inventory(data)
    return jsonify({"data": data, "message": "Inventory created"}),201


@inventory_bp.route("/inventory/create-variation", methods=["POST"])
@admin_required(allowed_roles=["super_admin"])
def create_variation():
    inventory_id= request.args.get('inventory_id')
    data = request.json
    save_variation(inventory_id, data)
    return jsonify({"data": data , "message": "Variation created"}),201


@inventory_bp.route("inventory/get-all", methods=["GET"])
def fetch_inventory():
    return get_all_inventory()



@inventory_bp.route("inventory/get-size", methods=["GET"])
def fetch_item_by_size():
    size = request.args.get('size') 
    if not size:
        return {"message": "Size is required"}, 400
    
    return get_item_sizes(size)

@inventory_bp.route("inventory/get-name-size", methods=["GET"])
def fetch_inventory_with_size():
    name = request.args.get('name') 
    size = request.args.get('size') 
    print('SIZE:',size)
   
    if not name or not size:
        return {"message": "name and size is required"}, 400
    
    return get_inventory_with_size(name,size)