from bot.services.send_text import send_text_message, send_template_message
from bot.core.constants import BOT_TAG, QUICK_REPLIES

def reply(sender_id, message, quick_replies=QUICK_REPLIES):
    print("SENDING TEXT")
    send_text_message(sender_id, f"{message}\n{BOT_TAG}", quick_replies)



def send_carousel(sender_id, products=None):
    print("SENDING CAROUSEL")
    items = []
    for item in products:
        print("[ITEM]:",item)
        for variation in item['variations']:
            carousel={
                "title":item['name'],
                "subtitle": f"Sizes:{variation['size']}|{variation['price']}",
                "image_url":variation['image'],
                "buttons":[
                    {
                        "type": "web_url",
                        "title": "View",
                        "url": variation['url']
                    },
                    {
                        "type": "postback",
                        "title": "Order Now",
                        "payload": variation['name']
                    }
                ]
            }
            items.append(carousel)

    print(f"[items]:", items)
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