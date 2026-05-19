from collections import defaultdict
from threading import Lock
import os
import time

import redis
from flask import jsonify, request


_redis_client = None
_local_hits = defaultdict(int)
_local_expiry = {}
_local_lock = Lock()
DEFAULT_API_RATE_LIMIT = int(os.environ.get("DEFAULT_API_RATE_LIMIT", 60))
DEFAULT_API_RATE_LIMIT_WINDOW_SECONDS = int(os.environ.get("DEFAULT_API_RATE_LIMIT_WINDOW_SECONDS", 60))
RATE_LIMITED_RESPONSE = {
    "message": "Too many requests. Please wait before trying again.",
    "code": "RATE_LIMITED",
}


def _get_redis_client():
    global _redis_client

    if _redis_client is not None:
        return _redis_client

    redis_url = os.environ.get("REDIS_URL")
    if not redis_url:
        return None

    try:
        _redis_client = redis.StrictRedis.from_url(redis_url, decode_responses=True)
    except ValueError:
        return None

    return _redis_client


def client_ip() -> str:
    return request.remote_addr or "unknown"


def rate_limit_hit(key: str, limit: int, window_seconds: int) -> tuple[bool, int]:
    namespaced_key = f"rate-limit:{key}"
    redis_client = _get_redis_client()

    if redis_client:
        try:
            current = redis_client.incr(namespaced_key)
            if current == 1:
                redis_client.expire(namespaced_key, window_seconds)

            ttl = redis_client.ttl(namespaced_key)
            return current > limit, max(ttl, 1)
        except redis.RedisError:
            pass

    now = time.time()
    with _local_lock:
        expired_keys = [
            key for key, expires_at in _local_expiry.items()
            if expires_at <= now
        ]
        for expired_key in expired_keys:
            _local_expiry.pop(expired_key, None)
            _local_hits.pop(expired_key, None)

        expires_at = _local_expiry.get(namespaced_key, 0)
        if expires_at <= now:
            _local_hits[namespaced_key] = 0
            _local_expiry[namespaced_key] = now + window_seconds

        _local_hits[namespaced_key] += 1
        retry_after = int(max(_local_expiry[namespaced_key] - now, 1))
        return _local_hits[namespaced_key] > limit, retry_after


def _env_int(name: str, default: int) -> int:
    try:
        value = int(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default

    return value if value > 0 else default


def _rate_limited_response(retry_after: int):
    response = jsonify(RATE_LIMITED_RESPONSE)
    response.status_code = 429
    response.headers["Retry-After"] = str(retry_after)
    return response


def register_api_rate_limit(app):
    @app.before_request
    def check_api_rate_limit():
        if not request.path.startswith("/api/") or request.method == "OPTIONS":
            return None

        limit = _env_int("API_RATE_LIMIT", DEFAULT_API_RATE_LIMIT)
        window_seconds = _env_int(
            "API_RATE_LIMIT_WINDOW_SECONDS",
            DEFAULT_API_RATE_LIMIT_WINDOW_SECONDS,
        )
        endpoint_key = request.endpoint or request.path
        limited, retry_after = rate_limit_hit(
            f"api:{client_ip()}:{request.method}:{endpoint_key}",
            limit,
            window_seconds,
        )

        if limited:
            return _rate_limited_response(retry_after)

        return None
