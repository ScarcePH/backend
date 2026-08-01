import re

from bot.core.constants import NOTIFY_USER, QUICK_REPLIES, SIZE_QUICK_REPLIES
from bot.services.messenger import reply, send_carousel
from bot.services.nlp import get_gpt_analysis, push_user_message
from bot.state.manager import set_handover, set_state
from bot.utils.extract_size import extract_size
from bot.utils.redis_client import redis_client
from db.repository.inventory import get_item_sizes, search_inventory_matches


SALES_INTENTS = {"check_product", "ask_price", "ask_availability"}
CONFUSION_TTL_SECONDS = 900
CONFUSION_LIMIT = 2
UNSUPPORTED_POLICY_TERMS = {
    "refund",
    "return",
    "exchange",
    "authentic",
    "legit",
    "meetup",
    "cancel",
    "reservation",
    "reserve",
}


def _confusion_key(sender_id):
    return f"bot_confusion:{sender_id}"


def increment_confusion(sender_id):
    if not sender_id:
        return 1
    try:
        count = redis_client.incr(_confusion_key(sender_id))
        redis_client.expire(_confusion_key(sender_id), CONFUSION_TTL_SECONDS)
        return int(count)
    except Exception:
        return 1


def reset_confusion(sender_id):
    if not sender_id:
        return
    try:
        redis_client.delete(_confusion_key(sender_id))
    except Exception:
        return


def _contains_unsupported_policy(message):
    words = set(re.findall(r"[a-z]+", str(message or "").lower()))
    return bool(words & UNSUPPORTED_POLICY_TERMS)


def _message_without_size(message, size):
    text = str(message or "")
    if size:
        text = re.sub(rf"\b{re.escape(str(size))}\s*(?:us)?\b", " ", text, flags=re.I)
    text = re.sub(
        r"\b(size|sz|avail|available|naa|meron|pa|po|price|hm|how much|us)\b",
        " ",
        text,
        flags=re.I,
    )
    return re.sub(r"\s+", " ", text).strip(" ?.,!")


def build_intent_result(message, sender_id=None):
    extracted_size = extract_size(message)
    analysis = get_gpt_analysis(message, sender_id)
    push_user_message(sender_id, message)

    intent = analysis.get("intent") or "smalltalk"
    size = extracted_size or analysis.get("size") or ""
    item = (analysis.get("item") or "").strip()
    if not item and size:
        item = _message_without_size(message, size)
    if item and item.lower() in {"size", "sz", "avail", "available", "naa", "meron"}:
        item = ""

    needs_handover = intent == "handover" or _contains_unsupported_policy(message)
    confidence = "high" if item and (size or intent in SALES_INTENTS) else "low"

    return {
        "intent": intent,
        "item": item,
        "size": str(size).strip(),
        "confidence": confidence,
        "reply": analysis.get("reply") or "Okay.",
        "needs_handover": needs_handover,
    }


def _send_unclear(sender_id, message=None):
    count = increment_confusion(sender_id)
    if count >= CONFUSION_LIMIT:
        set_handover(sender_id)
        reply(
            sender_id,
            "I may need help from the team for this one. I’ll connect you with a real person here.",
            None,
        )
        return "ok"

    reply(
        sender_id,
        (
            "I can help check pairs, price, size, order status, payment, or shipping. "
            "Try: 'Venom size 10.5', 'size 9 available?', or tap an option below."
        ),
        QUICK_REPLIES,
    )
    return "ok"


def _send_missing_item(sender_id, size=None):
    if size:
        reply(sender_id, f"What pair are you looking for in US {size}?", QUICK_REPLIES)
    else:
        reply(sender_id, "What pair are you looking for?", QUICK_REPLIES)
    return "ok"


def _send_size_only(sender_id, size):
    stocks = get_item_sizes(size)
    if stocks.get("found"):
        reset_confusion(sender_id)
        reply(sender_id, f"Here are available pairs in US {size}.")
        send_carousel(sender_id, stocks["items"])
        return "ok"

    reply(sender_id, f"We don't have available pairs in US {size} right now. What pair do you want us to watch for?")
    return "ok"


def _send_item_only(sender_id, item):
    stocks = search_inventory_matches(name=item)
    if stocks.get("found"):
        reset_confusion(sender_id)
        set_state(sender_id, {
            "state": "awaiting_size",
            "item": stocks["items"][0]["name"],
        })
        reply(sender_id, f"What US size are you looking for in {stocks['items'][0]['name']}?", SIZE_QUICK_REPLIES)
        return "ok"

    reply(sender_id, f"I couldn't find '{item}' in our available pairs. Try another pair name or tap Available Pairs.", QUICK_REPLIES)
    return "ok"


def _send_unavailable(sender_id, item, size, stocks):
    alternate_sizes = stocks.get("alternate_sizes") or []
    same_size_items = stocks.get("same_size_items") or []

    set_state(sender_id, {
        "item": item,
        "size": size,
    })

    if alternate_sizes:
        reply(sender_id, f"We don't have {item} in US {size} right now. These sizes are available for the same pair:", NOTIFY_USER)
        send_carousel(sender_id, alternate_sizes)
        return "ok"

    if same_size_items:
        reply(sender_id, f"We don't have {item} in US {size} right now. Here are other available pairs in US {size}:", NOTIFY_USER)
        send_carousel(sender_id, same_size_items)
        return "ok"

    reply(sender_id, f"We don't have {item} in US {size} right now. Would you like us to notify you when it becomes available?", NOTIFY_USER)
    return "ok"


def handle_inquiry(sender_id, chat, state=None, known_item=None):
    result = build_intent_result(chat, sender_id)
    item = known_item or result.get("item")
    size = result.get("size")
    intent = result.get("intent")

    if result.get("needs_handover"):
        set_handover(sender_id)
        reply(
            sender_id,
            "I’ll connect you with a real person for that so we don’t give you the wrong details.",
            None,
        )
        return "ok"

    if not item and not size:
        return _send_unclear(sender_id, chat)

    if size and not item:
        return _send_size_only(sender_id, size)

    if item and not size:
        if intent in SALES_INTENTS or result.get("confidence") == "high":
            return _send_item_only(sender_id, item)
        return _send_missing_item(sender_id)

    stocks = search_inventory_matches(name=item, size=size)
    if stocks.get("found"):
        reset_confusion(sender_id)
        matched_name = stocks["items"][0]["name"]
        reply(sender_id, f"We have {matched_name} in US {size}.")
        send_carousel(sender_id, stocks["items"])
        return "ok"

    return _send_unavailable(sender_id, item, size, stocks)
