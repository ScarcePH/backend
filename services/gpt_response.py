from openai import OpenAI
import os

SYSTEM_PROMPT = os.environ.get("SYSTEM_PROMPT")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
client = OpenAI(api_key=OPENAI_API_KEY)

def get_gpt_response(message, inventory_context):
    try:
        response = client.chat.completions.create(
            model="gpt-5-nano",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"User asked: {message}\n Inventory context: {inventory_context}"}
            ],
            reasoning_effort="medium",
        )
        content = response.choices[0].message.content.strip()
        if not content:
            print("[WARN] GPT returned an empty message.")
            return "We will get back to you shortly! - Automated Message"
        return content
    except Exception as e:
        print(f"[ERROR] GPT request failed: {e}")
        return "We will get back to you shortly! - Automated Message"
