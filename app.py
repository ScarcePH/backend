from flask import Flask, request, send_from_directory
import os
from dotenv import load_dotenv
from services.webhook_handler import webhook

load_dotenv()

VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN")
SYSTEM_PROMPT = os.environ.get("SYSTEM_PROMPT")



app = Flask(__name__)



@app.route("/")
def index():
    return "Messenger AI bot is live!"


@app.route("/webhook", methods=["GET"])
def verify():
    if request.args.get("hub.verify_token") == VERIFY_TOKEN:
        return request.args.get("hub.challenge")
    return "Verification failed", 403

@app.route('/privacy-policy')
def privacy_policy():
    return send_from_directory('static/privacy-policy', 'index.html')


@app.route("/webhook", methods=["POST"])
def webhook_route():
    return webhook()


# @app.route("/test", methods=["POST"])
# def test_route():

#     return test()

if __name__ == "__main__":
    app.run(debug=True)
