
BOT_TAG = " --Scarceᴾᴴ Bot"
WELCOME_MSG = "Hi there! Welcome to Scarceᴾᴴ 👋\nHow can we help you today?"
ERROR_MSG = "I didn't catch that. What item are you looking for?"
CONFIRM_HEADER = "All set!\n\n🛒 *Checkout Submitted*\n"
IMAGE_SENT_MSG = "I can’t read images. If you're looking for a pair. Type the item name and size so I can check the availability for you."
SCARCE_IMG = "https://scontent.fceb10-1.fna.fbcdn.net/v/t39.30808-6/457018195_122193654590162841_769628168669116497_n.jpg?_nc_cat=107&ccb=1-7&_nc_sid=6ee11a&_nc_ohc=GHFZatA3m88Q7kNvwGmVwni&_nc_oc=AdkeMTObOZvUGk4CFeAX15UZMtKoOZfFO7MmkrAqyDzzLCbYQmecKf4qT6U-h_cJGqw&_nc_zt=23&_nc_ht=scontent.fceb10-1.fna&_nc_gid=ofzqrM3DA1DN5fZguo0jOw&oh=00_Afkjp7FezYmvxJUzNrxQfPGZTdkEJgpda9AluXFO5HsxAw&oe=693FEF8C"
TRACK = "https://parcelsapp.com/en/tracking/"

QUICK_REPLIES = [
    "👟 Available Pairs",
    "🛒 My Order",
    "💬 Talk to Human",
    "📦 How to Order",
    # "🚚 Shipping Info",
]

AUTO_REPLIES = {
    "💬 talk to human": "Got it! We'll connect you with someone from the team asap 👍 You can continue chatting here and a real person will reply shortly.",
    "📦 how to order": "Simple lang! 👇 \n \n Just tell me the `item` and `size`(in us). \n \n SAMPLE: Avail pa og venom size 10.5? \n",
    "🚚 shipping info": "Shipping is via J&T/JRS 📦 \n 📍 Luzon/Visayas: 5–8 days \n 📍 Mindanao: 3–5 days\n",
    "🔔 notify me": "All set. We’ll notify you as soon as the item is back.",
    "change address": " We will start with your name, please provide your full name",
    "use this address": "We’re validating your order now. We’ll message you shortly once it’s confirmed.",
    "🛒 my order" : "Orders marked as pending are still being processed.\nTracking will appear once the order is shipped.",
    # "👟 available pairs" : "Above is the available pairs"

}

NOTIFY_USER =[
    f"🔔 Notify me"
]

def quick_reply(title, payload):
    return {"title": title, "payload": payload}


GLOBAL_CHECKOUT_ACTIONS = [
    quick_reply("Cancel", "ORDER_CANCEL"),
    quick_reply("Start over", "CHECKOUT_RESTART"),
    quick_reply("Talk to Human", "TALK_TO_HUMAN"),
]

YES_OR_NO = [
    quick_reply("Yes, order", "ORDER_CONFIRM"),
    quick_reply("No, cancel", "ORDER_CANCEL"),
] + GLOBAL_CHECKOUT_ACTIONS[1:]

SIZE_QUICK_REPLIES = ["7", "7.5", "8", "8.5", "9", "9.5", "10", "10.5", "11"]

PAYMENT_METHOD = [
    quick_reply("Full Payment", "PAYMENT_FULL"),
    quick_reply("COD", "PAYMENT_COD"),
    quick_reply("COP", "PAYMENT_COP"),
] + GLOBAL_CHECKOUT_ACTIONS

USE_OR_CHANGE_ADDRESS = [
    quick_reply("Use this address", "ADDRESS_USE"),
    quick_reply("Change address", "ADDRESS_CHANGE"),
] + GLOBAL_CHECKOUT_ACTIONS
