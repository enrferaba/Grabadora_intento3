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

    settings = get_settings()

    engine = create_engine(settings.database_url, pool_pre_ping=True, future=True)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)

    @contextmanager
    def session_scope() -> Session:
        """Provide a transactional scope around a series of operations."""

        session: Session = SessionLocal()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
