import json
import os
import re
from bot.utils.gpt_client import call_gpt   
from bot.core.constants import AUTO_REPLIES
from bot.state.manager import set_handover,set_state
from db.repository.customer import create_leads
from bot.services.confirm_order import confirm_order
from bot.services.messenger import reply as messender_reply, send_carousel
from db.repository.order import get_order
from db.repository.inventory import get_all_available_inventory


SYSTEM_PROMPT_ANALYSIS = os.environ.get("SYSTEM_PROMPT_ANALYSIS")

DEFAULT_RESPONSE = {
    "intent": "smalltalk",
    "item": "",
    "size": "",
    "reply": "Got it."
}

def extract_json(text):
    """
    Extracts the first JSON object from a string, even if surrounded by noise.
    """
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return None
    
    snippet = match.group(0)

    # attempt to load as JSON
    try:
        return json.loads(snippet)
    except Exception:
        return None

def sanitize(parsed):
    """
    Enforces schema integrity and prevents missing keys.
    """
    if not isinstance(parsed, dict):
        return DEFAULT_RESPONSE.copy()
    
    intent = parsed.get("intent", "") or ""
    item = parsed.get("item", "") or ""
    size = parsed.get("size", "") or ""
    reply = parsed.get("reply", "") or ""

    # Hard safety: unknown intent → smalltalk
    VALID_INTENTS = {
        "greet",
        "ask_availability",
        "ask_price",
        "check_product",
        "smalltalk",
        "handover",
    }

    if intent not in VALID_INTENTS:
        intent = "smalltalk"

    return {
        "intent": intent,
        "item": item.strip(),
        "size": size.strip(),
        "reply": reply.strip() if reply else "Okay."
    }

def get_gpt_analysis(user_message):
    user_prompt = f"""
        User: "{user_message}"

        Return JSON:
        {{
            "intent": "",
            "item": "",
            "size": "",
            "reply": ""
        }}
    """

    raw = call_gpt(SYSTEM_PROMPT_ANALYSIS, user_prompt)
    print(f"[GPT ANALYSIS RAW] {raw}")

    parsed = extract_json(raw)
    clean = sanitize(parsed)

    return clean


def get_auto_reply(message, sender_id,state):
    for keyword, reply in AUTO_REPLIES.items():
        if keyword in message:
            if "talk to human" in keyword:
                set_handover(sender_id)
            if "notify me" in keyword:                
                create_leads(sender_id,  state["item"], state["size"])
            if "use this address" in keyword:
                confirm_order(sender_id)
                return None
            if "change address" in keyword:
                set_state(sender_id, {**state,
                    "state": "awaiting_customer_name",
                })
                messender_reply(sender_id, "Alright We will change your address for your shipment.", None)
            if "my order" in keyword:
                order = get_order(sender_id)
                if(order):
                    messender_reply(sender_id, "Here’s your current order.")
                    send_carousel(sender_id, order, is_my_order=True)
                else:
                    messender_reply(sender_id, "You don’t have any active orders.")
            if 'available pairs' in keyword:
                pairs = get_all_available_inventory(1)
                if pairs.get("found"):
                    send_carousel(sender_id, pairs["items"], quick_replies=pairs["quick_replies"])
                else:
                    messender_reply(sender_id, "We don't have available pairs currently.")
                    return None
                                        
            return reply
    return None