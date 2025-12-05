from bot.utils.redis_client import redis_client,redis_local
import json


PREFIX = "handover:"
TTL = 3600  # 1 hour

def set_handover(sender_id):
    redis_client.setex(PREFIX + sender_id, TTL, "1")

def clear_handover(sender_id):
    redis_client.delete(PREFIX + sender_id)

def is_in_handover(sender_id):
    return redis_client.exists(PREFIX + sender_id) == 1






## USER STATE
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
