from db.models import Order
from db.database import db
from db.models import Customers, Inventory, InventoryVariation


def save_order(data: dict):
    order = Order(**data)
    db.session.add(order)
    db.session.commit()
    return order

def get_order(sender_id):
    orders = (
        Order.query
        .join(Customers)
        .filter(Customers.sender_id == sender_id)
        .all()
    )
    result = []
    for order in orders:
        result.append({
            "order_id": order.id,
            "status": order.status,
            "created_at": order.created_at,
            "updated_at": order.updated_at,
            "customer": {
                "id": order.customer.id,
                "name": order.customer.name,
                "phone": order.customer.phone,
                "address": order.customer.address,
            } if order.customer else None,
            "inventory": {
                "id": order.inventory.id,
                "name": order.inventory.name,
                "description": order.inventory.description,
            } if order.inventory else None,
            "variation": {
                "id": order.variation.id,
                "size": order.variation.size,
                "condition": order.variation.condition,
                "price": float(order.variation.price),  # convert Decimal to float if needed
                "stock": order.variation.stock,
                "url": order.variation.url,
                "image": order.variation.image,
                "status": order.variation.status,
            } if order.variation else None,
            "payment": {
                "id": order.payment.id,
                "payment_method": order.payment.payment_method,
                "to_settle": order.payment.total_amount - order.payment.received_amount,
            } if order.shipment else None,
            "shipment": {
                "id": order.shipment.id,
                "carrier": order.shipment.carrier,
                "tracking": order.shipment.tracking,
                "status": order.shipment.status,
            } if order.shipment else None,
    
        })
    return result

    

