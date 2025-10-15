"""In-memory replacements for Redis/RQ so the app works without extra services."""

from __future__ import annotations

import threading
import time
import uuid
from typing import Any, Callable, Dict, Optional, Tuple

from taskqueue import tasks


class InMemoryRedis:
    """Tiny Redis stand-in used when the real dependency is unavailable."""

    _jobs: Dict[str, "InMemoryJob"] = {}

    def __init__(self, url: str = "memory://local") -> None:
        self.url = url

    @staticmethod
    def from_url(url: str) -> "InMemoryRedis":
        return InMemoryRedis(url)

    # Compatibility helpers -------------------------------------------------
    def ping(self) -> bool:  # pragma: no cover - trivial
        return True


class InMemoryJob:
    """Background job executed in a Python thread."""

    def __init__(
        self,
        func: Callable[..., Any],
        args: Tuple[Any, ...],
        kwargs: Dict[str, Any],
        *,
        queue: "InMemoryQueue",
        meta: Optional[Dict[str, Any]] = None,
        job_timeout: Optional[int] = None,
        result_ttl: Optional[int] = None,
        failure_ttl: Optional[int] = None,
    ) -> None:
        self.id = str(uuid.uuid4())
        self.func = func
        self.args = args
        self.kwargs = kwargs
        self.queue = queue
        base_meta = {"status": "queued", "progress": 0, "segment": 0}
        if meta:
            base_meta.update(meta)
        self.meta: Dict[str, Any] = base_meta
        self._status = "queued"
        self._result: Any = None
        self._exception: Optional[BaseException] = None
        self.timeout = job_timeout
        self.result_ttl = result_ttl
        self.failure_ttl = failure_ttl
        self._thread = threading.Thread(target=self._run, daemon=True)
        InMemoryRedis._jobs[self.id] = self
        self._thread.start()

    # RQ-style helpers ------------------------------------------------------
    def refresh(self) -> None:
        if not self._thread.is_alive() and self._status == "started":
            self._status = (
                "failed" if self.meta.get("status") == "failed" else "finished"
            )

    def get_status(self, refresh: bool = True) -> str:
        if refresh:
            self.refresh()
        if self._status in {"finished", "failed"}:
            return "failed" if self.meta.get("status") == "failed" else "finished"
        return self._status

    def save_meta(self) -> None:  # pragma: no cover - nothing to persist
        pass

    # Convenience API -------------------------------------------------------
    def is_finished(self) -> bool:
        return self.get_status(refresh=False) in {"finished", "failed"}

    # Internal --------------------------------------------------------------
    def _run(self) -> None:
        tasks.set_current_job(self)
        self._status = "started"
        try:
            self._result = self.func(*self.args, **self.kwargs)
            if self.meta.get("status") not in {"failed", "completed"}:
                self.meta["status"] = "completed"
        except BaseException as exc:  # pragma: no cover - defensive
            self._exception = exc
            self.meta["status"] = "failed"
            self.meta.setdefault("error_message", str(exc))
        finally:
            self._status = (
                "failed" if self.meta.get("status") == "failed" else "finished"
            )
            tasks.clear_current_job()


class InMemoryQueue:
    """Simple queue facade compatible with the bits of RQ that we use."""

    def __init__(self, name: str, connection: Optional[InMemoryRedis] = None) -> None:
        self.name = name
        self.connection = connection or InMemoryRedis()

    def enqueue(
        self, func: Callable[..., Any], *args: Any, **kwargs: Any
    ) -> InMemoryJob:
        meta = kwargs.pop("meta", None)
        job_timeout = kwargs.pop("job_timeout", None)
        result_ttl = kwargs.pop("result_ttl", None)
        failure_ttl = kwargs.pop("failure_ttl", None)
        job = InMemoryJob(
            func,
            args,
            kwargs,
            queue=self,
            meta=meta,
            job_timeout=job_timeout,
            result_ttl=result_ttl,
            failure_ttl=failure_ttl,
        )
        return job

    def fetch_job(self, job_id: str) -> Optional[InMemoryJob]:
        return self.connection._jobs.get(job_id)

    @property
    def count(self) -> int:
        return sum(1 for job in self.connection._jobs.values() if not job.is_finished())


def drain_completed_jobs(timeout: float = 0.0) -> None:
    """Utility for tests: wait for any running in-memory jobs to settle."""

    if timeout <= 0:
        timeout = 0.0
    deadline = time.monotonic() + timeout
    while True:
        running = [job for job in InMemoryRedis._jobs.values() if not job.is_finished()]
        if not running or time.monotonic() >= deadline:
            break
        time.sleep(0.01)
