import json
import os
from utils.gpt_client import call_gpt   


SYSTEM_PROMPT = os.environ.get("SYSTEM_PROMPT_ANALYSIS")

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

    raw = call_gpt(SYSTEM_PROMPT, user_prompt)
    print(f"[GPT ANALYSIS RAW] {raw}")
    return json.loads(raw)
