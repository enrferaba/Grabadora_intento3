# app/infra/redis_conn.py
import os
from redis import Redis
from rq import Queue

REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")

_redis = Redis.from_url(REDIS_URL)
q_transcription = Queue("transcription", connection=_redis)

def get_redis():
    return _redis

def get_queue(name: str = "transcription") -> Queue:
    return Queue(name, connection=_redis)
