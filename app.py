from flask import Flask, request, send_from_directory
from dotenv import load_dotenv
from bot.webhook_handler import bot_bp
from api import customers_bp, orders_bp, inventory_bp, auth_bp, dashboard_bp
from db.database import db, migrate
from config import Config
import os
from flask_migrate import upgrade
from flask_jwt_extended import JWTManager
from flask_cors import CORS



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
app.register_blueprint(auth_bp, url_prefix="/api")
app.register_blueprint(dashboard_bp, url_prefix="/api")

app.config["JWT_SECRET_KEY"] = os.environ.get("JWT_SECRET_KEY")
app.config["JWT_ACCESS_TOKEN_EXPIRES"] = 60 * 60  # 1 hour

allowed_origins = [
    "http://localhost:5173",
    "https://scarce-admin.onrender.com",
    "https://www.admin.scarceph.com"
]
CORS(app, resources={r"/api/*": {"origins": allowed_origins}})

jwt = JWTManager(app)



@app.route('/privacy-policy')
def privacy_policy():
    return send_from_directory('static/privacy-policy', 'index.html')



if __name__ == "__main__":
    app.run(debug=True)
