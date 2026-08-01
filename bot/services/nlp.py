import json
import logging
import os
import re
from bot.utils.gpt_client import call_gpt   
from bot.utils.redis_client import redis_client
from bot.core.constants import AUTO_REPLIES
from bot.state.manager import set_handover,set_state
from db.repository.customer import create_leads
from bot.services.confirm_order import confirm_order
from bot.services.messenger import reply as messender_reply, send_carousel
from db.repository.order import get_order
from db.repository.inventory import get_all_available_inventory

logger = logging.getLogger(__name__)


SYSTEM_PROMPT_ANALYSIS = os.environ.get("SYSTEM_PROMPT_ANALYSIS")
HISTORY_TTL_SECONDS = 1800
HISTORY_LIMIT = 2

DEFAULT_RESPONSE = {
    "intent": "smalltalk",
    "item": "",
    "size": "",
    "confidence": "low",
    "reply": "Got it.",
    "needs_handover": False,
}


def _history_key(sender_id):
    return f"chat_history:{sender_id}"


def push_user_message(sender_id, message):
    if not sender_id or not message:
        return

    try:
        key = _history_key(sender_id)
        payload = json.dumps({"role": "user", "content": message.strip()})
        redis_client.lpush(key, payload)
        # Keep a little extra room in case limits change
        redis_client.ltrim(key, 0, 5)
        redis_client.expire(key, HISTORY_TTL_SECONDS)
    except Exception:
        # Never block checkout flow because of memory failures
        return


def get_recent_user_history(sender_id, limit=HISTORY_LIMIT):
    if not sender_id:
        return []

    try:
        key = _history_key(sender_id)
        raw_items = redis_client.lrange(key, 0, max(limit - 1, 0))
        messages = []
        for raw in reversed(raw_items):
            item = json.loads(raw)
            if isinstance(item, dict) and item.get("role") == "user" and item.get("content"):
                messages.append(item.get("content"))
        return messages
    except Exception:
        return []


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
    confidence = parsed.get("confidence", "") or "low"
    needs_handover = bool(parsed.get("needs_handover", False))

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
        "confidence": confidence if confidence in {"high", "medium", "low"} else "low",
        "reply": reply.strip() if reply else "Okay.",
        "needs_handover": needs_handover,
    }

def get_gpt_analysis(user_message, sender_id=None):
    history = get_recent_user_history(sender_id, HISTORY_LIMIT)
    history_block = "\n".join([f"- {msg}" for msg in history]) if history else "- none"

    user_prompt = f"""
        Recent user messages (oldest to latest, max 2):
        {history_block}

        Current user message:
        "{user_message}"

        Return JSON:
        {{
            "intent": "",
            "item": "",
            "size": "",
            "confidence": "high|medium|low",
            "reply": "",
            "needs_handover": false
        }}

        Classify only sales essentials: availability, size, price, order status,
        payment steps, shipping, available-pairs browsing, and human handover.
        Extract item and US size if present. Do not invent prices, stock,
        shipping exceptions, payment accounts, refund policy, authenticity
        claims, meetup rules, cancellation terms, or reservations. Use
        needs_handover=true for unsupported policy questions.
    """

    raw = call_gpt(SYSTEM_PROMPT_ANALYSIS, user_prompt)
    logger.debug("gpt_analysis_completed has_output=%s", bool(raw))

    parsed = extract_json(raw)
    clean = sanitize(parsed)

    return clean


def _auto_reply_allowed(keyword, state):
    current = (state or {}).get("state", "idle")
    normalized = keyword.lower()

    if "talk to human" in normalized:
        return True
    if "notify me" in normalized:
        return bool((state or {}).get("item") and (state or {}).get("size"))
    if normalized in {"use this address", "change address"}:
        return current == "repeat_customer_confirm"
    if "my order" in normalized:
        return current == "idle"
    if normalized in {"📦 how to order", "🚚 shipping info"}:
        return current == "idle"

    return current == "idle"


def get_auto_reply(message, sender_id,state):
    for keyword, reply in AUTO_REPLIES.items():
        if keyword in message:
            if not _auto_reply_allowed(keyword, state):
                return None
            if "talk to human" in keyword:
                set_handover(sender_id)
            if "notify me" in keyword:                
                item = (state or {}).get("item")
                size = (state or {}).get("size")
                if item and size:
                    create_leads(sender_id, item, size)
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
                                        
            return reply
    return None
