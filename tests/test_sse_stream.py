from __future__ import annotations

import pytest
import json

import asyncio

from app.main import _stream_job


class DummyJob:
    def __init__(self) -> None:
        self.id = "job1"
        self._status = "started"
        self.meta = {"progress": 0, "status": "transcribing"}
        self._refreshes = 0

    def refresh(self) -> None:
        self._refreshes += 1
        if self._refreshes == 1:
            self.meta.update({"progress": 1, "last_token": "Hello"})
        elif self._refreshes == 2:
            self.meta.update({"progress": 2, "last_token": " "})
        elif self._refreshes == 3:
            self.meta.update({"status": "completed", "transcript_key": "k", "language": "en"})

    def get_status(self, refresh: bool = False) -> str:
        if self.meta.get("status") == "completed":
            return "finished"
        return self._status


class DummyQueue:
    def __init__(self, job: DummyJob) -> None:
        self._job = job
        self._count = 1

    def fetch_job(self, job_id: str):
        return self._job

    @property
    def count(self) -> int:
        return self._count


class DummyRedis:
    pass


@pytest.mark.asyncio
async def test_stream_job_emits_delta_events(monkeypatch):
    job = DummyJob()

    def fake_queue(name, connection):
        return DummyQueue(job)

    monkeypatch.setattr("app.main.Queue", fake_queue)
    monkeypatch.setattr("app.main.asyncio.sleep", lambda _: asyncio.sleep(0))

    events = []
    async for event in _stream_job("job1", DummyRedis()):
        events.append(event)

    payloads = [json.loads(e) for e in events]
    delta_tokens = [item["data"] for item in payloads if item.get("event") == "delta"]
    assert delta_tokens == ["Hello", " "]
    assert any(item.get("event") == "completed" for item in payloads)
