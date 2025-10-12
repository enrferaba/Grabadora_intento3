import asyncio
import json


class DummyJob:
    def __init__(self) -> None:
        self.id = "job1"
        self._status = "started"
        self.meta = {"progress": 0, "status": "transcribing"}
        self._refreshes = 0

    def refresh(self) -> None:
        self._refreshes += 1
        if self._refreshes == 1:
            self.meta.update({"progress": 1, "last_token": json.dumps({"text": "Hello", "t0": 0.0, "t1": 1.0})})
        elif self._refreshes == 2:
            self.meta.update({"progress": 2, "last_token": json.dumps({"text": " ", "t0": 1.0, "t1": 2.0})})
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


def test_stream_job_emits_delta_events(monkeypatch):
    from app.main import _stream_job

    job = DummyJob()

    def fake_queue(name, connection):
        return DummyQueue(job)

    monkeypatch.setattr("app.main.Queue", fake_queue)
    original_sleep = asyncio.sleep
    monkeypatch.setattr("app.main.asyncio.sleep", lambda _: original_sleep(0))

    async def run_stream():
        events = []
        async for event in _stream_job("job1", DummyRedis()):
            events.append(event)
        return events

    events = asyncio.run(run_stream())

    delta_tokens = [json.loads(item["data"]) for item in events if item.get("event") == "delta"]
    assert delta_tokens == [
        {"text": "Hello", "t0": 0.0, "t1": 1.0},
        {"text": " ", "t0": 1.0, "t1": 2.0},
    ]
    assert any(item.get("event") == "completed" for item in events)
