from __future__ import annotations

import importlib

from sqlalchemy import text
from sqlalchemy.exc import OperationalError

import app.config


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


def test_session_scope_keeps_instances_attached(monkeypatch, tmp_path):
    monkeypatch.setenv("GRABADORA_DATABASE_URL", f"sqlite:///{tmp_path/'attached.db'}")
    app.config.get_settings.cache_clear()

    import app.database as database
    import models.user as models

    importlib.reload(database)
    importlib.reload(models)

    with database.session_scope() as session:
        models.Base.metadata.create_all(session.get_bind())

    with database.session_scope() as session:
        user = models.User(email="attached@example.com", hashed_password="hash")
        profile = models.Profile(name="Default")
        user.profiles.append(profile)
        session.add(user)
        session.flush()
        created_id = user.id

    assert user.id == created_id
    assert user.profiles[0].name == "Default"

    app.config.get_settings.cache_clear()
