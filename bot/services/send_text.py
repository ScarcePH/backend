import logging
import os
import time
from dataclasses import dataclass
from typing import Any, Optional

import requests

from bot.observability import increment


logger = logging.getLogger(__name__)

GRAPH_API_VERSION = os.environ.get("META_GRAPH_API_VERSION", "v17.0")
PAGE_ACCESS_TOKEN = os.environ.get("PAGE_ACCESS_TOKEN")
CONNECT_TIMEOUT = float(os.environ.get("MESSENGER_CONNECT_TIMEOUT_SECONDS", "3.05"))
READ_TIMEOUT = float(os.environ.get("MESSENGER_READ_TIMEOUT_SECONDS", "10"))
MAX_ATTEMPTS = max(1, int(os.environ.get("MESSENGER_SEND_ATTEMPTS", "3")))


@dataclass(frozen=True)
class SendResult:
    ok: bool
    status_code: Optional[int] = None
    error_class: Optional[str] = None
    retryable: bool = False


class MessengerTransientError(RuntimeError):
    """Raised so the durable event worker retries a transient delivery failure."""



def _validate_payload(recipient_id: Any, message: Any) -> Optional[str]:
    if not isinstance(recipient_id, (str, int)) or not str(recipient_id).strip():
        return "invalid_recipient"
    if not isinstance(message, dict) or not message:
        return "invalid_message"
    return None


def _send_message(recipient_id, message) -> SendResult:
    validation_error = _validate_payload(recipient_id, message)
    if validation_error:
        increment("messenger_send_failures")
        return SendResult(False, error_class=validation_error)
    if not PAGE_ACCESS_TOKEN:
        increment("messenger_send_failures")
        logger.error("messenger_send_failed error_class=missing_page_access_token")
        return SendResult(False, error_class="missing_page_access_token")

    url = f"https://graph.facebook.com/{GRAPH_API_VERSION}/me/messages"
    data = {"recipient": {"id": str(recipient_id)}, "message": message}

    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            response = requests.post(
                url,
                params={"access_token": PAGE_ACCESS_TOKEN},
                json=data,
                timeout=(CONNECT_TIMEOUT, READ_TIMEOUT),
                allow_redirects=False,
            )
        except (requests.Timeout, requests.ConnectionError) as exc:
            retryable = True
            error_class = type(exc).__name__
            status_code = None
        except requests.RequestException as exc:
            increment("messenger_send_failures")
            logger.warning(
                "messenger_send_failed attempt=%s error_class=%s retryable=false",
                attempt,
                type(exc).__name__,
            )
            return SendResult(False, error_class=type(exc).__name__)
        else:
            status_code = response.status_code
            if 200 <= status_code < 300:
                return SendResult(True, status_code=status_code)
            retryable = status_code == 429 or status_code >= 500
            error_class = "graph_transient" if retryable else "graph_rejected"

        logger.warning(
            "messenger_send_failed attempt=%s status_code=%s error_class=%s retryable=%s",
            attempt,
            status_code,
            error_class,
            str(retryable).lower(),
        )
        if not retryable or attempt == MAX_ATTEMPTS:
            increment("messenger_send_failures")
            return SendResult(
                False,
                status_code=status_code,
                error_class=error_class,
                retryable=retryable,
            )
        time.sleep(min(0.25 * (2 ** (attempt - 1)), 1.0))

    return SendResult(False, error_class="unknown")


def send_text_message(recipient_id, message_text, quick_replies=None) -> SendResult:
    if not isinstance(message_text, str) or not message_text.strip():
        increment("messenger_send_failures")
        return SendResult(False, error_class="invalid_text")

    message_payload = {"text": message_text[:2000]}
    if quick_replies:
        message_payload["quick_replies"] = [
            {
                "content_type": "text",
                "title": str(item.get("title", ""))[:20],
                "payload": str(item.get("payload", item.get("title", "")))[:1000],
            }
            if isinstance(item, dict)
            else {
                "content_type": "text",
                "title": str(item)[:20],
                "payload": str(item)[:1000],
            }
            for item in list(quick_replies)[:13]
        ]

    return _send_message(recipient_id, message_payload)


def send_template_message(recipient_id, payload) -> SendResult:
    return _send_message(recipient_id, payload)
