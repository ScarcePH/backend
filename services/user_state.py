import utils.redis_client as redis_client
import json


def get_state(user_id):
    key = f"user_state:{user_id}"
    data = redis_client.get(key)
    if not data:
        return {"state": "idle"}
    return json.loads(data)


def set_state(user_id, state_dict):
    key = f"user_state:{user_id}"
    redis_client.set(key, json.dumps(state_dict))


def reset_state(user_id):
    key = f"user_state:{user_id}"
    redis_client.delete(key)
