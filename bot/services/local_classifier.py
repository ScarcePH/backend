import re

from bot.utils.extract_size import extract_size


HANDOVER_PATTERN = re.compile(
    r"\b(?:agent|admin|staff|human|real\s+person|live\s+person)\b",
    re.IGNORECASE,
)
GREETING_PATTERN = re.compile(
    r"^[\W_]*(?:hi|hello|hey|good\s+morning|good\s+afternoon|good\s+evening)[\W_]*$",
    re.IGNORECASE,
)
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
SIZE_ONLY_WORDS = {
    "avail",
    "availability",
    "available",
    "do",
    "have",
    "in",
    "is",
    "meron",
    "naa",
    "pa",
    "please",
    "pls",
    "po",
    "size",
    "sizes",
    "sz",
    "us",
    "what",
    "you",
}


def _size_only_value(message):
    text = str(message or "")
    number_matches = list(re.finditer(r"\d+(?:\.\d+)?", text))
    if len(number_matches) != 1:
        return None

    size = extract_size(text)
    if not size:
        return None

    match = number_matches[0]
    remainder = text[:match.start()] + " " + text[match.end():]
    words = re.findall(r"[a-z]+", remainder.casefold())
    if all(word in SIZE_ONLY_WORDS for word in words):
        return size
    return None


def classify_local_message(message):
    """Classify messages that do not need GPT, in routing precedence order."""
    text = str(message or "")

    if HANDOVER_PATTERN.search(text):
        return {"intent": "handover", "size": ""}
    if GREETING_PATTERN.fullmatch(text):
        return {"intent": "greet", "size": ""}

    words = set(re.findall(r"[a-z]+", text.casefold()))
    if words & UNSUPPORTED_POLICY_TERMS:
        return {"intent": "unsupported_policy", "size": ""}

    size = _size_only_value(text)
    if size:
        return {"intent": "size_only", "size": size}

    return {"intent": "gpt", "size": ""}
