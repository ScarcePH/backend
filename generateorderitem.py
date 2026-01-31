from db.database import db
from db.models import Order, OrderItem, InventoryVariation
from decimal import Decimal

orders = Order.query.filter(
    Order.inventory_id != None,
    Order.variation_id != None
).all()

print(f"Found {len(orders)} orders to migrate into OrderItem")

count = 0

for order in orders:
    existing = OrderItem.query.filter_by(order_id=order.id).first()
    if existing:
        continue

    variation = InventoryVariation.query.get(order.variation_id)

    if not variation:
        print(f"Skipping order {order.id}, variation not found")
        continue

    price = variation.price or Decimal("0.00")

    existing.total_price = price
    db.session.commit(existing)

    item = OrderItem(
        order_id=order.id,
        inventory_id=order.inventory_id,
        variation_id=order.variation_id,
        quantity=1,  # old schema = 1 item per order
        price_at_purchase=price
    )

    db.session.add(item)
    count += 1

db.session.commit()

print(f"Migration completed. Created {count} order_items.")
