from openai import OpenAI
import os

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
client = OpenAI(api_key=OPENAI_API_KEY)

def call_gpt(system_prompt,message):
    try:
        response = client.chat.completions.create(
            model="gpt-5-nano",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": message}
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
