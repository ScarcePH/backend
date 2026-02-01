from bot.services.send_text import send_text_message, send_template_message
from bot.core.constants import BOT_TAG, QUICK_REPLIES, TRACK
import json

def reply(sender_id, message, quick_replies=QUICK_REPLIES):
    send_text_message(sender_id, f"{message}\n{BOT_TAG}", quick_replies)



def send_carousel(sender_id, products=None, is_my_order=False, quick_replies=[]):
    items = []
    if(is_my_order):
        for order in products:
            buttons = []
            if order['shipment']:
                buttons.append({
                    "type": "web_url",
                    "title": "Track Shipment",
                    "url": TRACK + order['shipment']['tracking']
                })
            carousel={
                "title": f"{ str(order['status']).upper()} ORDER",
                "subtitle": (
                    f"{order['inventory']['name']} ({order['variation']['size']}us) | "
                    f"Bal: ₱{order['payment']['to_settle']} | "
                    f"{order['shipment']['status'] if order['shipment'] else ''}"
                ),
                "image_url": coursel_image(order['inventory']['image']),
            }
            if buttons:
                carousel["buttons"] = buttons
            items.append(carousel)
    else:
        for inventory in products:
            for variation in inventory['variations']:
                carousel={
                    "title":inventory['name'],
                    "subtitle": f"{variation['status']} | {variation['condition']} | Size: {variation['size']} | ₱{variation['price']}",
                    "image_url": coursel_image(inventory['image']),
                    "buttons":[
                        {
                            "type": "web_url",
                            "title": "View",
                            "url": variation['url']
                        },
                        {
                            "type": "postback",
                            "title": "Order Now",
                            "payload": json.dumps({
                                "action": "ORDER",
                                "inventory_id": inventory['id'],
                                "variation_id": variation['id'],
                                "item": inventory['name'],
                                "size": variation['size'],
                                "price": str(variation['price']),
                                "url": variation['url'],
                                "status": variation['status']
                            })
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
            },
            
        }
    }
    if quick_replies and len(quick_replies) > 0:
        message["quick_replies"] = quick_replies

    send_template_message(sender_id, message)


def coursel_image(img_url):
    filename = img_url.split("/")[-1]
    image = "https://www.img.scarceph.com/carousel/"+filename
    return image