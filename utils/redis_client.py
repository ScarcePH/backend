import os
import redis
from dotenv import load_dotenv

load_dotenv()

REDIS_URL = os.environ.get("REDIS_URL")  



redis_client = redis.StrictRedis.from_url(
    REDIS_URL,
    decode_responses=True  # return strings instead of bytes
)



redis_local = redis.Redis(host='localhost', port=6379, db=0)


