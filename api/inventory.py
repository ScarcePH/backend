from flask import Blueprint, request, jsonify
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

    inv_url = upload(
        file=upload_buf,
        filename=file.filename,
        content_type=file.content_type,
        subfolder="inv"
    )

    img = Image.open(process_buf)

    square = fit_subject_center(img, 1080)

    out = io.BytesIO()
    square.save(out, format="PNG")
    out.seek(0)

    upload(
        file=out,
        filename=file.filename.replace(".jpg", ".png"),
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
    payload = request.json
    if not isinstance(payload, dict):
        return jsonify({"message": "Payload must be a JSON object"}), 400
    inventory_id = payload.get("inventory_id", None)
    variations = payload.get("variations", None)
    if not inventory_id or not variations:
        return jsonify({"message": "Invalid JSON payload"}), 400
 
    data = save_variations(inventory_id, variations)
    return jsonify({
        "message": "Variations synchronized successfully"
    }), 201
 


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
