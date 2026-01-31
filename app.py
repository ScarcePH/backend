from flask import Flask, request, send_from_directory
from dotenv import load_dotenv
from bot.webhook_handler import bot_bp
from api import customers_bp, orders_bp, inventory_bp, auth_bp, dashboard_bp, cart_bp
from db.database import db, migrate
from config import Config
import os
from flask_migrate import upgrade
from flask_jwt_extended import JWTManager
from flask_cors import CORS
from db.models.token_blocklist import TokenBlocklist

from scripts.migration import orders_to_order_items, generate_checkout_session




load_dotenv()




app = Flask(__name__)
app.config.from_object(Config)



db.init_app(app)
migrate.init_app(app, db)

with app.app_context():
    try:
        upgrade()
        if os.environ.get("RUN_SCRIPT") == "true":
            print("Running one-time Order → OrderItem migration...")
            orders_to_order_items()
            generate_checkout_session()
            print("One-time migration done.")
        print("✓ Migrations applied successfully.")

    except Exception as e:
        print("✗ Migration failed:", e)
# ---------------------------------
# AUTO-RUN MIGRATIONS ON STARTUP
# ---------------------------------
# with app.app_context():
#     try:
#         upgrade()
#         print("✓ Migrations applied successfully.")
#     except Exception as e:
#         print("✗ Migration failed:", e)
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
app.register_blueprint(auth_bp, url_prefix="/api")
app.register_blueprint(dashboard_bp, url_prefix="/api")
app.register_blueprint(cart_bp, url_prefix="/api")

app.config["JWT_SECRET_KEY"] = os.environ.get("JWT_SECRET_KEY")
app.config["JWT_ACCESS_TOKEN_EXPIRES"] = 60 * 60  # 1 hour

allowed_origins = [
    "http://localhost:5173",
    "https://scarceph.com",
    "https://www.scarceph.com"
]
CORS(
    app, 
    supports_credentials=True,
    resources={r"/api/*": {"origins": allowed_origins}}
)

jwt = JWTManager(app)

@jwt.token_in_blocklist_loader
def check_if_token_revoked(jwt_header, jwt_payload):
    jti = jwt_payload["jti"]
    return TokenBlocklist.query.filter_by(jti=jti).first() is not None



@app.route('/privacy-policy')
def privacy_policy():
    return send_from_directory('static/privacy-policy', 'index.html')



if __name__ == "__main__":
    app.run(debug=False)
