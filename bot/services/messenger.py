from bot.services.send_text import send_text_message, send_template_message
from bot.core.constants import BOT_TAG, QUICK_REPLIES

def reply(sender_id, message, quick_replies=QUICK_REPLIES):
    send_text_message(sender_id, f"{message}\n{BOT_TAG}", quick_replies)



def send_carousel(sender_id, products=None):
    # sample_data= [
    #     {
    #         "title": "Nike Sb Stefan Janoski OG venom 2009",
    #         "subtitle": "Sizes: 10.5 | ₱5,900",
    #         "image_url": "https://scontent.fmnl14-2.fna.fbcdn.net/v/t39.30808-6/518243855_122304258218162841_5364217191055184753_n.jpg?stp=cp6_dst-jpg_tt6&_nc_cat=111&ccb=1-7&_nc_sid=833d8c&_nc_ohc=iSP_sw56eTEQ7kNvwGKANre&_nc_oc=AdkUKHgUxgaZlXMuSNgGBW4DPzGkmHAkVPpQ6Ru_ANqjVszKaUvK5Sxf-bGRw58Ddj0&_nc_zt=23&_nc_ht=scontent.fmnl14-2.fna&_nc_gid=91FIndRYeJcj_SSAOt67OQ&oh=00_AfnfkqKB8ghR7BsT9AbVnA5OyiRqk6B8PllL8AorOXUrxA&oe=693F5466",
    #         "buttons": [
    #             {
    #                 "type": "postback",
    #                 "title": "Order",
    #                 "payload": "ORDER_2"
    #             }
    #         ]
    #     }
    # ]

    items = []
    for item in products:
        carousel={
            "title":item['name'],
            "subtitle": f"Sizes:{item.size}|{item.price}|{item.status}",
            "buttons":[
                {
                    "type": "web_url",
                    "title": "View",
                    "payload": item.url
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

    return send_template_message(sender_id, message)