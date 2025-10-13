from __future__ import annotations

import asyncio
import io
import json
import secrets
import wave
from typing import Dict, List, Tuple

import pytest


def _make_wav_bytes(duration_ms: int = 200) -> bytes:
    buffer = io.BytesIO()
    sample_rate = 16_000
    total_samples = int(sample_rate * duration_ms / 1000)
    with wave.open(buffer, "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(b"\x00\x00" * total_samples)
    return buffer.getvalue()


@pytest.fixture()
def api_context(tmp_path, monkeypatch):
    from app import config

    database_path = tmp_path / "grabadora.db"
    storage_root = tmp_path / "storage"
    monkeypatch.setenv("GRABADORA_QUEUE_BACKEND", "memory")
    monkeypatch.setenv("GRABADORA_DATABASE_URL", f"sqlite+aiosqlite:///{database_path}")
    monkeypatch.setenv("GRABADORA_STORAGE_DIR", str(storage_root))
    monkeypatch.setenv("GRABADORA_TRANSCRIPTS_DIR", "transcripts")
    monkeypatch.setenv("GRABADORA_AUDIO_CACHE_DIR", "audio-cache")
    monkeypatch.setenv("GRABADORA_MODELS_CACHE_DIR", "models")
    monkeypatch.setenv("GRABADORA_ENABLE_DUMMY_TRANSCRIBER", "true")
    monkeypatch.setenv("GRABADORA_FRONTEND_ORIGIN", "*")

    config.get_settings.cache_clear()
    config.settings = config.get_settings()

    storage_root.mkdir(parents=True, exist_ok=True)
    (storage_root / config.settings.audio_cache_dir).mkdir(parents=True, exist_ok=True)
    (storage_root / config.settings.transcripts_dir).mkdir(parents=True, exist_ok=True)

    from app.auth import (
        AuthenticatedProfile,
        AuthenticatedUser,
        get_current_user,
        get_password_hash,
    )
    from app.database import session_scope, sync_engine
    from app.main import create_app
    from models.user import Base, Profile, User

    Base.metadata.create_all(bind=sync_engine)
    with session_scope():
        pass

    app = create_app()

    with session_scope() as session:
        user = User(email=f"tester-{secrets.token_hex(4)}@example.com", hashed_password=get_password_hash("secret123"))
        profile = Profile(name="Default", description="Perfil por defecto")
        user.profiles.append(profile)
        session.add(user)
        session.flush()
        session.refresh(profile)
        auth_user = AuthenticatedUser(
            id=user.id,
            email=user.email,
            profiles=[
                AuthenticatedProfile(
                    id=profile.id,
                    name=profile.name,
                    description=profile.description,
                )
            ],
        )

    app.dependency_overrides[get_current_user] = lambda: auth_user
    app.state.test_user = auth_user  # type: ignore[attr-defined]
    return app, auth_user


pytestmark = pytest.mark.anyio("asyncio")


Headers = List[Tuple[str, str]]


@pytest.fixture()
def anyio_backend():
    return "asyncio"


async def _asgi_request(
    app,
    method: str,
    path: str,
    *,
    headers: Headers | None = None,
    body: bytes = b"",
) -> Tuple[int, Headers, List[bytes]]:
    scope_headers = [(b"host", b"testserver")]
    if headers:
        scope_headers.extend((name.lower().encode(), value.encode()) for name, value in headers)
    if "?" in path:
        path_only, query_string = path.split("?", 1)
        raw_query = query_string.encode()
    else:
        path_only = path
        raw_query = b""

    scope = {
        "type": "http",
        "http_version": "1.1",
        "asgi": {"version": "3.0"},
        "method": method.upper(),
        "scheme": "http",
        "path": path_only,
        "raw_path": path_only.encode(),
        "query_string": raw_query,
        "headers": scope_headers,
        "client": ("testclient", 50000),
        "server": ("testserver", 80),
        "state": {},
    }

    body_parts: List[bytes] = [body] if body else []
    sent_final = False

    async def receive() -> Dict[str, object]:
        nonlocal sent_final
        if body_parts:
            chunk = body_parts.pop(0)
            message = {
                "type": "http.request",
                "body": chunk,
                "more_body": bool(body_parts),
            }
            if not body_parts:
                sent_final = True
            return message
        if not sent_final:
            sent_final = True
            return {"type": "http.request", "body": b"", "more_body": False}
        await asyncio.sleep(0)
        return {"type": "http.disconnect"}

    status_code = 500
    response_headers: Headers = []
    body_chunks: List[bytes] = []

    async def send(message: Dict[str, object]) -> None:
        nonlocal status_code, response_headers
        message_type = message.get("type")
        if message_type == "http.response.start":
            status_code = int(message.get("status", 500))
            raw_headers = message.get("headers") or []
            response_headers = [
                (key.decode(), value.decode()) for key, value in raw_headers  # type: ignore[arg-type]
            ]
        elif message_type == "http.response.body":
            body_chunks.append(message.get("body", b"") or b"")

    await app(scope, receive, send)
    return status_code, response_headers, body_chunks


def _encode_multipart_form(
    data: Dict[str, str], files: Dict[str, Tuple[str, bytes, str]]
) -> Tuple[str, bytes]:
    boundary = f"----testboundary{secrets.token_hex(8)}"
    lines: List[bytes] = []
    for field, value in data.items():
        lines.append(f"--{boundary}".encode())
        lines.append(f'Content-Disposition: form-data; name="{field}"'.encode())
        lines.append(b"")
        lines.append(value.encode())
    for field, (filename, content, content_type) in files.items():
        lines.append(f"--{boundary}".encode())
        disposition = f'Content-Disposition: form-data; name="{field}"; filename="{filename}"'
        lines.append(disposition.encode())
        lines.append(f"Content-Type: {content_type}".encode())
        lines.append(b"")
        lines.append(content)
    lines.append(f"--{boundary}--".encode())
    lines.append(b"")
    body = b"\r\n".join(lines)
    return f"multipart/form-data; boundary={boundary}", body


def _parse_sse_events(payload: str) -> List[Dict[str, str]]:
    events: List[Dict[str, str]] = []
    event_name: str | None = None
    data_lines: List[str] = []
    for raw_line in payload.replace("\r\n", "\n").split("\n"):
        line = raw_line.strip()
        if not line:
            if event_name or data_lines:
                events.append({"event": event_name, "data": "\n".join(data_lines)})
                event_name = None
                data_lines = []
            continue
        if line.startswith(":"):
            continue
        if line.startswith("event:"):
            event_name = line.split(":", 1)[1].strip()
        elif line.startswith("data:"):
            data_lines.append(line.split(":", 1)[1].strip())
    if event_name or data_lines:
        events.append({"event": event_name, "data": "\n".join(data_lines)})
    return events


async def _enqueue_completed_transcription(app) -> Tuple[str, int]:
    from taskqueue.fallback import drain_completed_jobs

    audio_bytes = _make_wav_bytes()

    form_fields = {
        "language": "es",
        "profile": "balanced",
        "title": "Prueba",
        "tags": "demo",
        "diarization": "false",
        "word_timestamps": "true",
    }
    files = {"file": ("sample.wav", audio_bytes, "audio/wav")}
    content_type, body = _encode_multipart_form(form_fields, files)
    status, _, chunks = await _asgi_request(
        app,
        "POST",
        "/transcribe",
        headers=[
            ("content-type", content_type),
            ("content-length", str(len(body))),
        ],
        body=body,
    )

    assert status == 200
    payload = json.loads(b"".join(chunks).decode())
    job_id = payload.get("job_id")
    assert job_id

    drain_completed_jobs(timeout=5.0)

    status, _, job_chunks = await _asgi_request(app, "GET", f"/jobs/{job_id}")
    assert status == 200
    job_payload = json.loads(b"".join(job_chunks).decode())
    transcript_id = job_payload.get("transcript_id")
    assert transcript_id
    return job_id, int(transcript_id)


async def test_upload_and_stream_flow(api_context):
    app, _ = api_context

    job_id, _ = await _enqueue_completed_transcription(app)

    status, response_headers, sse_chunks = await _asgi_request(
        app,
        "GET",
        f"/transcribe/{job_id}",
        headers=[("accept", "text/event-stream")],
    )
    assert status == 200
    assert any(
        value.lower().startswith("text/event-stream")
        for key, value in response_headers
        if key.lower() == "content-type"
    )
    events = _parse_sse_events(b"".join(sse_chunks).decode())

    assert any(event.get("event") == "completed" for event in events)
    completed_event = next(event for event in events if event.get("event") == "completed")
    completed_payload = json.loads(completed_event["data"])
    assert completed_payload.get("job_id") == job_id


async def test_cors_configuration(api_context):
    from fastapi.middleware.cors import CORSMiddleware

    app, _ = api_context
    cors = next((mw for mw in app.user_middleware if mw.cls is CORSMiddleware), None)
    assert cors is not None
    options = cors.kwargs or {}
    assert options.get("allow_origins") == ["*"]
    assert options.get("allow_methods") == ["*"]
    assert options.get("allow_headers") == ["*"]
    assert options.get("allow_credentials") is False


async def test_download_transcript(api_context):
    app, _ = api_context

    _, transcript_id = await _enqueue_completed_transcription(app)

    from app.database import session_scope
    from models.user import Transcript
    from storage.s3 import S3StorageClient

    storage = S3StorageClient()
    storage.ensure_buckets()
    object_name = f"tests/transcript-{transcript_id}.txt"
    storage.upload_transcript("Transcripción de prueba", object_name)

    with session_scope() as session:
        transcript = (
            session.query(Transcript)
            .filter(Transcript.id == transcript_id)
            .one()
        )
        transcript.transcript_key = object_name
        session.add(transcript)
        session.commit()
    with session_scope() as session:
        refreshed = (
            session.query(Transcript)
            .filter(Transcript.id == transcript_id)
            .one()
        )
        assert refreshed.transcript_key == object_name
        assert refreshed.user_id == app.state.test_user.id  # type: ignore[attr-defined]

    storage_check = S3StorageClient()
    storage_check.ensure_buckets()
    assert storage_check.download_transcript(object_name) is not None

    status, headers, chunks = await _asgi_request(
        app,
        "GET",
        f"/transcripts/{transcript_id}/download?format=md",
    )
    body_text = b"".join(chunks).decode()
    assert status == 200, body_text
    content_type_header = next((value for key, value in headers if key.lower() == "content-type"), "")
    assert "text/plain" in content_type_header
    disposition = next((value for key, value in headers if key.lower() == "content-disposition"), "")
    assert "attachment" in disposition.lower()
    body = b"".join(chunks).decode()
    assert "#" in body
