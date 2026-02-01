from uuid import uuid4
from db.models import Order, CheckoutSession
from db.database import db
from app import app


with app.app_context():
    orders = Order.query.filter(Order.checkout_session_id == None).all()

    print(f"Found {len(orders)} orders without checkout_session")

    for order in orders:
        session = CheckoutSession(
            id=uuid4(),
            customer_id=order.customer_id,
            items_json=[],
            total_price=order.payment.total_amount if order.payment else 0.0,
            status="paid"
        )
        db.session.add(session)
        db.session.flush()
        order.checkout_session_id = session.id

    db.session.commit()
    print("Backfill completed.")
