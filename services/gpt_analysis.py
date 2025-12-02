import json
import os
import re
from utils.gpt_client import call_gpt   

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
