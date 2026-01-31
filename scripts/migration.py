from decimal import Decimal
from db.database import db
from db.models.order import Order
from db.models.order_item import OrderItem
from db.models.inventory_variation import InventoryVariation

from db.models import Order, CheckoutSession
from uuid import uuid4




def orders_to_order_items():
    orders = Order.query.all()

    print(f"Found {len(orders)} orders to migrate")

    count = 0

    for order in orders:
        existing = OrderItem.query.filter_by(order_id=order.id).first()
        if existing:
            continue

        variation = InventoryVariation.query.get(order.variation_id)
        if not variation:
            print(f"Skipping order {order.id}: variation not found")
            continue

        price = variation.price or Decimal("0.00")

        item = OrderItem(
            order_id=order.id,
            inventory_id=order.inventory_id,
            variation_id=order.variation_id,
            quantity=1,
            price_at_purchase=price
        )

        db.session.add(item)
        order.total_price = price * 1
        db.session.add(order)
        count += 1

    db.session.commit()
    print(f"Migration completed. Created {count} order_items.")

def generate_checkout_session():
    orders = Order.query.filter(Order.checkout_session_id == None).all()

    print(f"Found {len(orders)} orders without checkout_session")

    for order in orders:
        session = CheckoutSession(
            id=uuid4(),
            customer_id=order.customer_id,
            items_json=[],
            total_price=order.payment.total_amount if order.payment else 0.0,
            status="approved"
        )
        db.session.add(session)
        db.session.flush()
        order.checkout_session_id = session.id

    db.session.commit()
    print("Backfill completed.")
