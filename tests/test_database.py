from __future__ import annotations

import importlib

import app.config
from sqlalchemy import text
from sqlalchemy.exc import OperationalError


def test_session_scope_falls_back_to_sqlite(monkeypatch, tmp_path):
    fallback_db = tmp_path / "fallback.db"
    monkeypatch.setenv("GRABADORA_DATABASE_URL", "postgresql+psycopg2://invalid")
    monkeypatch.setenv("GRABADORA_FALLBACK_SQLITE_URL", f"sqlite:///{fallback_db}")
    app.config.get_settings.cache_clear()

    import app.database as database

    importlib.reload(database)

    real_create_engine = database.create_engine
    calls = {"primary": 0, "fallback": 0}

    def fake_create_engine(url: str, *args, **kwargs):
        if url.startswith("postgresql"):
            calls["primary"] += 1
            raise OperationalError("fail", None, None, None)
        calls["fallback"] += 1
        return real_create_engine(url, *args, **kwargs)

    monkeypatch.setattr(database, "create_engine", fake_create_engine)

    try:
        with database.session_scope() as session:
            result = session.execute(text("SELECT 1")).scalar_one()
            assert result == 1
    finally:
        app.config.get_settings.cache_clear()

    assert calls["primary"] >= 1
    assert calls["fallback"] >= 1
    assert fallback_db.exists()
