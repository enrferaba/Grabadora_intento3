"""Utility to run RQ workers."""

from __future__ import annotations

import logging

from redis import Redis
from rq import Connection, Worker

from app.config import get_settings

logger = logging.getLogger(__name__)


def run_worker(queue_name: str | None = None) -> None:
    settings = get_settings()
    redis = Redis.from_url(settings.redis_url)
    queue_name = queue_name or settings.rq_default_queue
    with Connection(redis):
        logger.info("Starting RQ worker", extra={"queue": queue_name})
        worker = Worker([queue_name])
        worker.work()
