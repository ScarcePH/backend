from flask import Flask, request, send_from_directory
from dotenv import load_dotenv
from bot.webhook_handler import bot_bp
from api import customers_bp, orders_bp, inventory_bp
from db.database import db, migrate
from config import Config
import os
from db.models import Customers, Inventory, Order
from flask_migrate import upgrade

load_dotenv()




app = Flask(__name__)
app.config.from_object(Config)

db.init_app(app)
migrate.init_app(app, db)
# ---------------------------------
# AUTO-RUN MIGRATIONS ON STARTUP
# ---------------------------------
with app.app_context():
    try:
        upgrade()
        print("✓ Migrations applied successfully.")
    except Exception as e:
        print("✗ Migration failed:", e)
# -------------------------------
# Bot POST webhook
# -------------------------------
app.register_blueprint(bot_bp)

# -------------------------------
# API blueprints
# -------------------------------
app.register_blueprint(customers_bp, url_prefix="/api")
app.register_blueprint(orders_bp, url_prefix="/api")
app.register_blueprint(inventory_bp, url_prefix="/api")

@app.route("/")
def index():
    return "Messenger AI bot is live!"


# @app.route("/webhook", methods=["GET"])
# def verify():
#     if request.args.get("hub.verify_token") == os.environ.get("VERIFY_TOKEN"):
#         return request.args.get("hub.challenge")
#     return "Verification failed", 403

@app.route('/privacy-policy')
def privacy_policy():
    return send_from_directory('static/privacy-policy', 'index.html')



# @app.route("/test", methods=["POST"])
# def test_route():

#     return test()

if __name__ == "__main__":
    app.run(debug=True)
