from __future__ import annotations

from taskqueue import tasks
from taskqueue.fallback import InMemoryQueue, InMemoryRedis, drain_completed_jobs


def test_inmemory_queue_executes_jobs_and_updates_meta():
    queue = InMemoryQueue(
        "default", connection=InMemoryRedis.from_url("memory://tests")
    )

    def sample_job() -> None:
        job = tasks.get_current_job()
        assert job is not None
        job.meta["status"] = "completed"
        job.meta["last_token"] = '{"text":"hola"}'
        job.save_meta()

    job = queue.enqueue(sample_job)
    drain_completed_jobs(timeout=0.2)
    job.refresh()

    assert job.get_status(refresh=False) == "finished"
    assert job.meta["status"] == "completed"
    assert queue.count == 0
