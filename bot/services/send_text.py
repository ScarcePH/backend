import requests
import os

PAGE_ACCESS_TOKEN = os.environ.get("PAGE_ACCESS_TOKEN")

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
        print(f"[ERROR] Message send failed: {response.text}. [RECIPIENT_ID]:{recipient_id}")

def send_template_message(recipient_id, payload):
    data = {
        "recipient": {"id": recipient_id},
        "message": payload
    }

    url = f"https://graph.facebook.com/v17.0/me/messages?access_token={PAGE_ACCESS_TOKEN}"
    r = requests.post(url, json=data)
    return r.json()