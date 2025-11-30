import json
from utils.redis_client import redis_client


DEFAULT_STATE = {"state": "idle"}
TTL_SECONDS = 3600 


def get_state(user_id):
    key = f"user_state:{user_id}"
    raw = redis_client.get(key)

    if raw is None:
        return DEFAULT_STATE.copy()

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return DEFAULT_STATE.copy()


def set_state(user_id, state_dict):
    key = f"user_state:{user_id}"
    redis_client.setex(key, TTL_SECONDS, json.dumps(state_dict))


def reset_state(user_id):
    key = f"user_state:{user_id}"
    redis_client.delete(key)
