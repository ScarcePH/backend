from bot.services.send_text import (
    MessengerTransientError,
    send_template_message,
    send_text_message,
)
from bot.core.constants import BOT_TAG, QUICK_REPLIES, TRACK
import json

def reply(sender_id, message, quick_replies=QUICK_REPLIES):
    result = send_text_message(sender_id, f"{message}\n{BOT_TAG}", quick_replies)
    if not result.ok and result.retryable:
        raise MessengerTransientError(result.error_class or "messenger_send_failed")
    return result



def send_carousel(sender_id, products=None, is_my_order=False, quick_replies=None):
    items = []
    if(is_my_order):
        for order in products or []:
            order_items = order.get("items") or []
            if not order_items:
                continue

            first_item = order_items[0]
            inventory = first_item.get("inventory") or {}
            variation = first_item.get("variation") or {}
            payment = order.get("payment") or {}
            shipment = order.get("shipment")

            buttons = []
            if shipment and shipment.get("tracking"):
                buttons.append({
                    "type": "web_url",
                    "title": "Track Shipment",
                    "url": TRACK + shipment["tracking"]
                })

            balance = payment.get("to_settle")
            if balance is None:
                balance = order.get("total_price", 0)

            subtitle_parts = [
                f"{inventory.get('name', 'Item')} ({variation.get('size', '')}us)",
                f"Bal: ₱{balance}",
            ]
            if shipment and shipment.get("status"):
                subtitle_parts.append(shipment["status"])

            carousel = {
                "title": f"{ str(order.get('status', '')).upper()} ORDER",
                "subtitle": " | ".join([part for part in subtitle_parts if part]),
                "image_url": coursel_image(inventory.get("image", "")),
            }
            if buttons:
                carousel["buttons"] = buttons
            items.append(carousel)
            if len(items) == 10:
                break
    else:
        for inventory in products or []:
            for variation in inventory.get('variations', []):
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
                                "variation_id": variation['id']
                            })
                        }
                    ]
                }
                items.append(carousel)
                if len(items) == 10:
                    break
            if len(items) == 10:
                break

    if not items:
        return None
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
        message["quick_replies"] = [
            {
                "content_type": "text",
                "title": str(item.get("title", ""))[:20],
                "payload": str(item.get("payload", item.get("title", "")))[:1000],
            }
            if isinstance(item, dict)
            else {
                "content_type": "text",
                "title": str(item)[:20],
                "payload": str(item)[:1000],
            }
            for item in list(quick_replies)[:13]
        ]

    result = send_template_message(sender_id, message)
    if not result.ok and result.retryable:
        raise MessengerTransientError(result.error_class or "messenger_send_failed")
    return result


def coursel_image(img_url):
    filename = img_url.split("/")[-1]
    image = "https://www.img.scarceph.com/carousel/"+filename
    return image
