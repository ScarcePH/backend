from flask import Flask, request, send_from_directory
import requests
import os
from dotenv import load_dotenv
from openai import OpenAI
import re

load_dotenv()

VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN")
PAGE_ACCESS_TOKEN = os.environ.get("PAGE_ACCESS_TOKEN")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
BASE_URL = os.environ.get("BASE_URL")
SYSTEM_PROMPT = os.environ.get("SYSTEM_PROMPT")


client = OpenAI(api_key=OPENAI_API_KEY)
app = Flask(__name__)

# Quick Reply Titles (shown as buttons in Messenger)
QUICK_REPLIES = [
    "💬 Talk to Human",
    "👟 Browse Products",
    "📦 How to Order",
    "💰 Payment Options",
    "🚚 Shipping Info",
]

# Auto replies for common FAQs
AUTO_REPLIES = {
    "💬 talk to human": "Got it! We'll connect you with someone from the team asap 👍 You can continue chatting here and a real person will reply shortly.",
    "👟 browse products": "You can browse our FB page or Visit Our Catalog here:\n👉 https://marionrosete.github.io/ScarcePH",
    "📦 how to order": "Simple lang! 👇\n1️⃣ Browse the catalog or FB posts\n2️⃣ Message us to reserve/order\n3️⃣ We’ll confirm and send payment details\n\nKung COD/COP, ₱500 deposit is needed 😊",
    "💰 payment options": "You can pay via:\n💸 GCash\n🏦 BPI\n🚚 COD/COP (with ₱500 deposit to avoid Flakers)\n\n*Reservation deposit is non-refundable.*",
    "🚚 shipping info": "Shipping is via LBC 📦\n📍 Luzon/Visayas: 5–8 days\n📍 Mindanao: 3–5 days\n\nCOD/COP available din (with ₱500 deposit).",
    "💬 talk to human": "Got it! We'll connect you with someone from the team asap 👍 You can continue chatting here and a real person will reply shortly."
}

HUMAN_HANDOVER = set()



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
def webhook():
    data = request.get_json()
    if data["object"] == "page":
        for entry in data["entry"]:
            for event in entry["messaging"]:
                sender_id = event["sender"]["id"]

                if "postback" in event:
                    postback = event["postback"]
                    if postback.get("payload") == "GET_STARTED":
                        HUMAN_HANDOVER.discard(sender_id)
                        welcome_text = "Hi there! Welcome to Scarceᴾᴴ 👋 \n How can we assist you today? \n Here are some quick options to get started:"
                        send_text_message(sender_id, welcome_text, quick_replies=QUICK_REPLIES)
                        continue


                if "message" in event:
                    message = event["message"]

                    if "text" in message:
                        text = message["text"].lower().strip()
                        

                        auto_reply = get_auto_reply(text, sender_id)
                        if auto_reply:
                            send_text_message(sender_id, auto_reply, quick_replies=QUICK_REPLIES)

                        elif sender_id in HUMAN_HANDOVER:
                            send_text_message(sender_id, "You can continue chatting here and a real person will reply soon.")

                        # else:
                        #     reply = get_gpt_response(text)
                        #     send_text_message(sender_id, reply, quick_replies=QUICK_REPLIES)

    return "ok", 200


def get_auto_reply(message, sender_id):
    for keyword, reply in AUTO_REPLIES.items():
        if keyword in message:
            if "talk to human" in keyword:
                HUMAN_HANDOVER.add(sender_id)
            return reply
    return None


def get_gpt_response(message):
    try:
        response = client.chat.completions.create(
            model="gpt-5-nano",            
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": message}
            ],
            reasoning_effort="medium",       
           
        )
    
        content = response.choices[0].message.content.strip()
        if not content:
            print("[WARN] GPT returned an empty message.")
            return "We will get back to you shortly! - Automated Message"
        return content
    except Exception as e:
        print(f"[ERROR] GPT request failed: {e}")
        return "We will get back to you shortly! - Automated Message"


def send_text_message(recipient_id, message_text, quick_replies=None):
    url = f"https://graph.facebook.com/v17.0/me/messages?access_token={PAGE_ACCESS_TOKEN}"

    message_payload = {"text": message_text}

    if quick_replies:
        message_payload["quick_replies"] = [
            {
                "content_type": "text",
                "title": reply,
                "payload": reply
            } for reply in quick_replies
        ]

    payload = {
        "recipient": {"id": recipient_id},
        "message": message_payload
    }

    response = requests.post(url, json=payload)
    if response.status_code != 200:
        print(f"[ERROR] Message send failed: {response.text}")


if __name__ == "__main__":
    app.run(debug=True)
