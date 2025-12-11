from bot.services.send_text import send_text_message, send_template_message
from bot.core.constants import BOT_TAG, QUICK_REPLIES

def reply(sender_id, message, quick_replies=QUICK_REPLIES):
    send_text_message(sender_id, f"{message}\n{BOT_TAG}", quick_replies)



def send_carousel(sender_id, products=None):
    items = []
    for item in products:
        carousel={
            "title":item['name'],
            "subtitle": f"Sizes:{item['size']}|{item['price']}|{item['status']}",
            "image_url":item['image'],
            "buttons":[
                {
                    "type": "web_url",
                    "title": "View",
                    "payload": item['url']
                },
                {
                    "type": "postback",
                    "title": "Order Now",
                    "payload": f"{item['name']}"
                }
            ]
        }
        items.append(carousel)
    message = {
        "attachment": {
            "type": "template",
            "payload": {
                "template_type": "generic",
                "elements": items
            }
        }
    }

    send_template_message(sender_id, message)