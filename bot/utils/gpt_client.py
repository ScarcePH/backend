import logging

from openai import OpenAI
import os
from dotenv import load_dotenv

load_dotenv()
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
client = OpenAI(
    api_key=OPENAI_API_KEY,
    timeout=float(os.environ.get("OPENAI_TIMEOUT_SECONDS", "20")),
    max_retries=1,
)
logger = logging.getLogger(__name__)

def call_gpt(system_prompt,message):
    try:
        response = client.chat.completions.create(
            model="gpt-5.6-luna",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": message}
            ],
            reasoning_effort="none",
        )
        content = response.choices[0].message.content.strip()
        if not content:
            logger.warning("gpt_request_empty_response")
            return "We will get back to you shortly! - Automated Message"
        return content
    except Exception as exc:
        logger.error("gpt_request_failed error_class=%s", type(exc).__name__)
        return "We will get back to you shortly! - Automated Message"
