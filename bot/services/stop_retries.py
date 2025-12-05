from bot.utils.redis_client import redis_client
## STOP META RETRIES WHEN RENDER IS DOWN
def stop_retries(mid):
    key = f"mid:{mid}"
    if redis_client.exists(key):
        return "ok", 200
    ## 2 MINS 
    redis_client.setex(key, 120, 1)