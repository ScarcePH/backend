from utils.redis_client import redis_client

PREFIX = "handover:"
TTL = 3600  # 1 hour

def set_handover(sender_id):
    redis_client.setex(PREFIX + sender_id, TTL, "1")

def clear_handover(sender_id):
    redis_client.delete(PREFIX + sender_id)

def is_in_handover(sender_id):
    return redis_client.exists(PREFIX + sender_id) == 1
