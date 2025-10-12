"""SQLAlchemy engine and session management."""
from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Iterator

try:  # pragma: no cover - optional dependency
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session, sessionmaker
except ImportError:  # pragma: no cover
    create_engine = None  # type: ignore
    Session = Any  # type: ignore
    sessionmaker = None  # type: ignore

    def session_scope() -> Iterator[Any]:  # type: ignore[override]
        raise RuntimeError("SQLAlchemy must be installed to access the database layer")
else:
    from app.config import get_settings

    _session_factory: sessionmaker | None = None
    _session_error: Exception | None = None

    def _ensure_session_factory() -> None:
        """Create the SQLAlchemy session factory on demand."""

        global _session_factory, _session_error
        if _session_factory is not None or _session_error is not None:
            return
        settings = get_settings()
        try:
            engine = create_engine(settings.database_url, pool_pre_ping=True, future=True)
            _session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
        except ModuleNotFoundError as exc:  # pragma: no cover - driver missing
            _session_error = exc

    @contextmanager
    def session_scope() -> Session:
        """Provide a transactional scope around a series of operations."""

        _ensure_session_factory()
        if _session_error is not None:
            raise RuntimeError(
                "Database driver not installed. Install psycopg2-binary or configure DATABASE_URL",
            ) from _session_error
        assert _session_factory is not None  # narrow type for mypy
        session: Session = _session_factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
