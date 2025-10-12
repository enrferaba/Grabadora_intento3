"""SQLAlchemy engine and session management."""
from __future__ import annotations

import logging
import os
from contextlib import contextmanager
from typing import Any, Iterator

try:  # pragma: no cover - optional dependency
    from sqlalchemy import create_engine
    from sqlalchemy.exc import OperationalError
    from sqlalchemy.orm import Session, sessionmaker
except ImportError:  # pragma: no cover
    create_engine = None  # type: ignore
    OperationalError = Exception  # type: ignore
    Session = Any  # type: ignore
    sessionmaker = None  # type: ignore

    def session_scope() -> Iterator[Any]:  # type: ignore[override]
        raise RuntimeError("SQLAlchemy must be installed to access the database layer")

    def get_session() -> Iterator[Any]:  # type: ignore[override]
        raise RuntimeError("SQLAlchemy must be installed to access the database layer")
else:
    from app.config import get_settings

    logger = logging.getLogger(__name__)

    from models.user import Base  # type: ignore

    _session_factory: sessionmaker | None = None
    _session_error: Exception | None = None
    _sync_engine: Any | None = None

    class _SyncEngineProxy:
        def __getattr__(self, item: str) -> Any:
            _ensure_session_factory()
            if _sync_engine is None:
                raise AttributeError(item)
            return getattr(_sync_engine, item)

        def __repr__(self) -> str:  # pragma: no cover - debug helper
            _ensure_session_factory()
            return repr(_sync_engine)

        def __bool__(self) -> bool:  # pragma: no cover - truthiness
            _ensure_session_factory()
            return _sync_engine is not None

    sync_engine: Any = _SyncEngineProxy()

    _FALLBACK_ENV = "GRABADORA_FALLBACK_SQLITE_URL"
    _DEFAULT_FALLBACK = "sqlite:///./grabadora.db"

    def _bootstrap_factory(database_url: str) -> tuple[sessionmaker, Any]:
        engine = create_engine(database_url, pool_pre_ping=True, future=True)
        factory = sessionmaker(
            bind=engine,
            autoflush=False,
            autocommit=False,
            expire_on_commit=False,
            future=True,
        )
        return factory, engine

    def _initialize_fallback(exc: Exception) -> None:
        """Configure a SQLite session factory when the primary database is unavailable."""

        global _session_factory, _session_error, _sync_engine
        fallback_url = os.getenv(_FALLBACK_ENV, _DEFAULT_FALLBACK)
        try:
            factory, engine = _bootstrap_factory(fallback_url)
            # Asegura las tablas para crear cuentas sin ejecutar migraciones manuales en local.
            from models.user import Base  # lazy import to avoid circular dependency

            Base.metadata.create_all(engine)  # type: ignore[arg-type]
            logger.warning(
                "Falling back to SQLite database at %s because the primary database is unavailable: %s",
                fallback_url,
                exc,
            )
            _session_factory = factory
            _sync_engine = engine
        except Exception as fallback_exc:  # pragma: no cover - catastrophic failure
            _session_error = fallback_exc
            logger.exception("Could not initialize fallback SQLite database", exc_info=fallback_exc)

    def _ensure_session_factory() -> None:
        """Create the SQLAlchemy session factory on demand."""

        global _session_factory, _session_error, _sync_engine
        if _session_factory is not None or _session_error is not None:
            return
        settings = get_settings()
        try:
            factory, engine = _bootstrap_factory(settings.database_url)
            # Touch the connection early to surface connectivity issues immediately.
            with engine.connect():
                pass
            _session_factory = factory
            _sync_engine = engine
        except (ModuleNotFoundError, OperationalError) as exc:
            _initialize_fallback(exc)

    @contextmanager
    def session_scope() -> Session:
        """Provide a transactional scope around a series of operations."""

        _ensure_session_factory()
        if _session_factory is None:
            raise RuntimeError(
                "No database engine could be initialized. Install the required drivers or configure DATABASE_URL.",
            ) from _session_error
        session: Session = _session_factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    @contextmanager
    def get_session() -> Iterator[Session]:  # pragma: no cover - thin wrapper
        with session_scope() as session:
            yield session

