from collections import Counter
from threading import Lock


_COUNTERS = Counter()
_LOCK = Lock()


def increment(name: str, amount: int = 1) -> None:
    """Increment a process-local metric that can be exported by the runtime."""
    with _LOCK:
        _COUNTERS[name] += amount


def snapshot() -> dict[str, int]:
    with _LOCK:
        return dict(_COUNTERS)
