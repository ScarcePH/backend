from flask import Blueprint, request, jsonify, json
from db.database import db
from db.models.inventory import Inventory
from db.repository.inventory import (
    get_all_inventory,
    save_inventory,
    get_item_sizes,
    save_variations,
    get_inventory_with_size,
    get_all_available_inventory,
    get_all_available
)
from middleware.auth_required import auth_required
from services.image.upload import upload
from services.image.resize import fit_subject_center
from PIL import Image
import io
import time
import random
import os
from api.helpers.inventory import upload_variation_img


inventory_bp = Blueprint("inventory", __name__)

@inventory_bp.route("/inventory/create", methods=["POST"])
@auth_required(allowed_roles=["super_admin"])
def create_inventory():

    name = request.form.get("name")
    description = request.form.get("description")
    file = request.files["file"]

    raw = file.stream.read()

    upload_buf = io.BytesIO(raw)
    process_buf = io.BytesIO(raw)

    ext = os.path.splitext(file.filename)[1]
    new_filename = f"{int(time.time())}_{random.randint(1000,9999)}{ext}"

    inv_url = upload(
        file=upload_buf,
        filename=new_filename,
        content_type=file.content_type,
        subfolder="inv"
    )

    img = Image.open(process_buf)

    square = fit_subject_center(img, 1080)

    out = io.BytesIO()
    square.save(out, format="PNG")
    out.seek(0)

    ext = os.path.splitext(file.filename)[1]
    new_filename = f"{int(time.time())}_{random.randint(1000,9999)}{ext}"

    upload(
        file=out,
        filename=new_filename,
        content_type="image/png",
        subfolder="carousel"
    )

    data = {
        "name": name,
        "description": description,
        "image": inv_url
    }

    res = save_inventory(data)

    return jsonify({
        "data": res,
        "message": "Inventory created"
    }), 201


@inventory_bp.route("/inventory/create-variation", methods=["POST"])
@auth_required(allowed_roles=["super_admin"])

def create_variation():

    variations_raw = request.form.get("variations")
    inventory_id = request.form.get("inventory_id")

    if not variations_raw or not inventory_id:
        return jsonify({"message": "Missing variations or inventory_id"}), 400

    try:
        variations = json.loads(variations_raw)
    except json.JSONDecodeError:
        return jsonify({"message": "Invalid JSON in variations"}), 400

    if not isinstance(variations, list):
        return jsonify({"message": "Variations must be a list"}), 400

    files = request.files
    variations = upload_variation_img(variations,files)
    data = save_variations(inventory_id, variations)

    return jsonify({
        "message": "Variations created successfully",
        "data": data,
    }), 200

 


@inventory_bp.route("inventory/get-all", methods=["GET"])
@auth_required(allowed_roles=["super_admin"])
def fetch_inventory():
    return get_all_inventory()



@inventory_bp.route("inventory/get-size", methods=["GET"])
@auth_required(allowed_roles=["super_admin"])
def fetch_item_by_size():
    size = request.args.get('size') 
    if not size:
        return {"message": "Size is required"}, 400
    
    return get_item_sizes(size)

@inventory_bp.route("inventory/get-name-size", methods=["GET"])
@auth_required(allowed_roles=["super_admin"])
def fetch_inventory_with_size():
    name = request.args.get('name') 
    size = request.args.get('size') 
    print('SIZE:',size)
   
    if not name or not size:
        return {"message": "name and size is required"}, 400
    
    return get_inventory_with_size(name,size)

@inventory_bp.route("inventory/get-available", methods=["GET"])
@auth_required(allowed_roles=["super_admin"])
def test():
    data = get_all_available_inventory()
    return data

@inventory_bp.route("inventory/get-all-available", methods=["GET"])
def get_all_available_item():
    data = get_all_available()
    return data

@inventory_bp.route("inventory/edit", methods=["POST"])
@auth_required(allowed_roles=["super_admin"])
def edit():
    data = request.json
    inventory_id = data.get("inventory_id")
    name = data.get("name")
    description = data.get("description")

    if not inventory_id:
        return jsonify({"message": "inventory_id is required"}), 400
    
    inventory = Inventory.query.get(inventory_id)
        
    if not inventory:
        return jsonify({"message": "pair not found"}), 404

    if name is not None:
        inventory.name = name

    if description is not None:
        inventory.description = description

    db.session.commit()

    return jsonify({
        "message": "Inventory updated successfully",
        "inventory": {
            "id": inventory.id,
            "name": inventory.name,
            "description": inventory.description
        }
    }), 200