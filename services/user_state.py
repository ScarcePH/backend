from utils.redis_client import redis_client
import json


def get_state(user_id):
    key = f"user_state:{user_id}"
    data = redis_client.exists(key)
    if not data:
        return {"state": "idle"}
    return json.loads(data)


def set_state(user_id, state_dict):
    key = f"user_state:{user_id}"
    redis_client.setex(key, json.dumps(state_dict))


def reset_state(user_id):
    key = f"user_state:{user_id}"
    redis_client.delete(key)
