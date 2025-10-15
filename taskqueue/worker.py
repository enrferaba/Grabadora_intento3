from redis import Redis
from rq import Worker, Queue, Connection
from app.config import get_settings

def run_worker():
    settings = get_settings()
    redis_conn = Redis.from_url(settings.redis_url)
    listen_queues = ["transcription"]

    with Connection(redis_conn):
        worker = Worker(listen_queues)
        print(f"🚀 Worker listening on queues: {listen_queues}")
        worker.work(with_scheduler=True)

if __name__ == "__main__":
    run_worker()
