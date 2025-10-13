from __future__ import annotations

import io
import json
import secrets
import wave
from tempfile import SpooledTemporaryFile
from typing import Dict, List, Tuple

import pytest

pytestmark = pytest.mark.anyio("asyncio")

Headers = Dict[str, str]


@pytest.fixture()
def anyio_backend():
    return "asyncio"


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


def _make_upload(filename: str, content: bytes, content_type: str = "audio/wav"):
    file_obj = SpooledTemporaryFile()
    file_obj.write(content)
    file_obj.seek(0)
    from fastapi import UploadFile

    return UploadFile(filename=filename, file=file_obj, headers={"content-type": content_type})


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


async def test_upload_and_stream_flow(api_context):
    from app.main import _stream_job, create_transcription_job
    from taskqueue.fallback import drain_completed_jobs

    app, user = api_context

    audio_bytes = _make_wav_bytes()
    upload = _make_upload("sample.wav", audio_bytes)
    response = await create_transcription_job(
        file=upload,
        language="es",
        profile="balanced",
        title="Prueba",
        tags="demo",
        diarization=False,
        word_timestamps=True,
        user=user,
    )
    assert response.status == "queued"
    assert response.job_id

    drain_completed_jobs(timeout=5.0)

    events: List[Dict[str, str]] = []
    async for event in _stream_job(response.job_id, expected_user_id=user.id):
        events.append(event)
        if event.get("event") == "completed":
            break

    assert any(event.get("event") == "completed" for event in events)
    payload = json.loads(events[-1]["data"])
    assert payload.get("job_id") == response.job_id


async def test_cors_configuration(api_context):
    from fastapi.middleware.cors import CORSMiddleware

    app, _ = api_context
    cors = next((mw for mw in app.user_middleware if mw.cls is CORSMiddleware), None)
    assert cors is not None
    options = cors.kwargs or {}
    assert options.get("allow_origins") == ["*"]
    assert options.get("allow_methods") == ["*"]
    assert options.get("allow_headers") == ["*"]
