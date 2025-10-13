"""Atajo para lanzar la API tras verificar dependencias."""

from __future__ import annotations

import argparse
import os
import secrets
import sys
from pathlib import Path

try:
    import uvicorn
except ImportError as exc:  # pragma: no cover
    raise SystemExit(
        "uvicorn no está instalado. Ejecuta 'pip install uvicorn[standard]' o usa docker compose up --build."
    ) from exc

try:
    import doctor
except ImportError:  # pragma: no cover - en teoría siempre está presente
    doctor = None  # type: ignore

MIN_PYTHON = (3, 11)


def _require_supported_python() -> None:
    if sys.version_info < MIN_PYTHON:
        raise SystemExit(
            f"Esta utilidad requiere Python {MIN_PYTHON[0]}.{MIN_PYTHON[1]} o superior. "
            f"Se detectó {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}."
        )
    interpreter = Path(sys.executable)
    if "WindowsApps" in interpreter.parts:
        raise SystemExit(
            "El intérprete activo proviene de Microsoft Store. "
            "Desactiva los alias de Python y usa el Python del entorno virtual."
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Levanta la API en modo desarrollo")
    parser.add_argument(
        "--skip-checks",
        action="store_true",
        help="Omitir la comprobación previa de dependencias.",
    )
    parser.add_argument(
        "--install-missing",
        action="store_true",
        help="Intenta instalar dependencias de Python ausentes antes de arrancar.",
    )
    parser.add_argument(
        "--fix-frontend",
        action="store_true",
        help="Ejecuta 'npm install' en frontend/ si faltan dependencias de la SPA.",
    )
    parser.add_argument(
        "--host", default="0.0.0.0", help="Host de escucha para uvicorn."
    )
    parser.add_argument(
        "--port", type=int, default=8000, help="Puerto de escucha para uvicorn."
    )
    parser.add_argument(
        "--reload",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Recarga automática en desarrollo (usa --no-reload para desactivarla).",
    )
    parser.add_argument(
        "--mode",
        choices=["auto", "local", "stack"],
        default="auto",
        help=(
            "Configura el modo de ejecución: 'local' usa SQLite y la cola en memoria; "
            "'stack' espera Redis/DB/S3 vivos."
        ),
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    _require_supported_python()

    requested_mode = args.mode

    if not args.skip_checks and doctor is not None:
        exit_code = doctor.run_checks(
            install_missing=args.install_missing,
            fix_frontend=args.fix_frontend,
            mode=requested_mode,
        )
        if exit_code != 0:
            raise SystemExit(
                "Corrige las dependencias anteriores o vuelve a ejecutar con --skip-checks si entiendes los riesgos."
            )

    resolved_mode = _resolve_mode(requested_mode)
    _apply_environment_for_mode(resolved_mode)
    _ensure_local_database(resolved_mode)
    print(f"\n🚀 Ejecutando plataforma en modo: {resolved_mode}")
    if resolved_mode == "local":
        print("   • Cola en memoria y base de datos SQLite local")
    else:
        print("   • Se espera Redis + RQ, Postgres y MinIO en ejecución")

    base_url = f"http://{args.host}:{args.port}"
    print("\nℹ️  Endpoints disponibles:")
    print(f"   • SPA: {base_url}/")
    print(f"   • API interactiva: {base_url}/docs")
    print(f"   • Métricas Prometheus: {base_url}/metrics")
    config = uvicorn.Config(
        "app.main:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        reload_dirs=["app", "taskqueue", "storage"],
        factory=False,
    )
    server = uvicorn.Server(config)
    server.run()


def _resolve_mode(mode: str) -> str:
    if mode in {"local", "stack"}:
        return mode
    backend = os.getenv("GRABADORA_QUEUE_BACKEND", "").lower()
    if backend in {"redis", "stack"}:
        return "stack"
    return "local"


def _apply_environment_for_mode(mode: str) -> None:
    if mode == "local":
        os.environ.setdefault("GRABADORA_QUEUE_BACKEND", "memory")
        sqlite_path = Path("grabadora.db").resolve()
        os.environ.setdefault("GRABADORA_DATABASE_URL", f"sqlite:///{sqlite_path}")
        os.environ.setdefault("GRABADORA_FRONTEND_ORIGIN", "http://localhost:5173")
        _ensure_jwt_secret()
    else:
        os.environ.setdefault("GRABADORA_QUEUE_BACKEND", "redis")
    _refresh_settings_cache()
    if mode == "stack":
        _validate_stack_runtime()


def _ensure_jwt_secret() -> None:
    """Guarantee a valid JWT secret for local execution."""

    placeholders = {
        "",
        "please-change-this-secret",
        "change-me",
        "super-secret",
    }
    env_candidates = [
        "GRABADORA_JWT_SECRET_KEY",
        "JWT_SECRET",
        "JWT_SECRET_KEY",
    ]
    current = None
    current_key = None
    for key in env_candidates:
        value = os.environ.get(key)
        if value is not None:
            current = value.strip()
            current_key = key
            break
    if current and current not in placeholders:
        # Already defined with a non-placeholder value.
        if current_key != "GRABADORA_JWT_SECRET_KEY":
            os.environ.setdefault("GRABADORA_JWT_SECRET_KEY", current)
        return

    # Generate a strong secret and export it via the canonical key.
    secret = secrets.token_urlsafe(48)
    os.environ["GRABADORA_JWT_SECRET_KEY"] = secret
    os.environ.setdefault("JWT_SECRET", secret)
    os.environ.setdefault("JWT_SECRET_KEY", secret)
    if current:
        print(
            "⚠️  Se detectó un GRABADORA_JWT_SECRET_KEY de ejemplo. "
            "Se generó un secreto temporal para esta sesión.",
        )
    else:
        print("ℹ️  No se encontró GRABADORA_JWT_SECRET_KEY; se generó uno temporal.")
    _persist_secret_to_env(secret)


def _persist_secret_to_env(secret: str) -> None:
    """Write the generated secret back to .env so future runs succeed."""

    env_path = Path(".env")
    try:
        if env_path.exists():
            contents = env_path.read_text(encoding="utf-8")
        else:
            contents = ""
    except UnicodeDecodeError:
        print(
            "⚠️  No se pudo actualizar .env (codificación no UTF-8). "
            "Actualiza el secreto manualmente.",
        )
        return

    updated_lines = []
    replaced = False
    for line in contents.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            updated_lines.append(line)
            continue
        key, _, value = line.partition("=")
        key_upper = key.strip().upper()
        if key_upper in {"GRABADORA_JWT_SECRET_KEY", "JWT_SECRET", "JWT_SECRET_KEY"}:
            updated_lines.append(f"GRABADORA_JWT_SECRET_KEY={secret}")
            replaced = True
        else:
            updated_lines.append(line)

    if not replaced:
        if updated_lines and updated_lines[-1] != "":
            updated_lines.append("")
        updated_lines.append(f"GRABADORA_JWT_SECRET_KEY={secret}")

    new_content = "\n".join(updated_lines).rstrip() + "\n"
    try:
        env_path.write_text(new_content, encoding="utf-8")
    except OSError as exc:
        print(
            "⚠️  No se pudo escribir el nuevo GRABADORA_JWT_SECRET_KEY en .env:",
            exc,
        )
        return
    print("   • Se guardó un nuevo GRABADORA_JWT_SECRET_KEY en .env")


def _ensure_local_database(mode: str) -> None:
    if mode != "local":
        return
    try:
        from app.database import Base, get_engine  # type: ignore
    except Exception as exc:  # pragma: no cover - defensive
        print(f"⚠️  No se pudo importar app.database para inicializar SQLite: {exc}")
        return
    try:
        engine = get_engine()
    except Exception as exc:  # pragma: no cover - defensive
        print(f"⚠️  No se pudo inicializar el engine de base de datos: {exc}")
        return
    engine_url = getattr(engine, "url", None)
    if hasattr(engine_url, "render_as_string"):
        url_str = engine_url.render_as_string(hide_password=False)
    else:
        url_str = str(engine_url)
    if not url_str.startswith("sqlite"):
        return
    Base.metadata.create_all(bind=engine)
    print(f"   • Base de datos SQLite inicializada en {url_str}")


def _refresh_settings_cache() -> None:
    try:
        from app.config import get_settings  # type: ignore
    except Exception:
        return
    cache_clear = getattr(get_settings, "cache_clear", None)
    if callable(cache_clear):
        cache_clear()


def _validate_stack_runtime() -> None:
    try:
        from app.config import get_settings  # type: ignore
    except Exception as exc:
        raise SystemExit("No se pudo cargar la configuración del proyecto.") from exc

    settings = get_settings()

    try:
        from redis import Redis  # type: ignore
    except ImportError as exc:
        raise SystemExit("Modo 'stack' requiere la librería redis instalada.") from exc

    try:
        redis_conn = Redis.from_url(settings.redis_url)
        redis_conn.ping()
    except Exception as exc:
        raise SystemExit(f"Redis no responde en {settings.redis_url}: {exc}") from exc

    try:
        from rq import Worker  # type: ignore
    except ImportError as exc:
        raise SystemExit("Modo 'stack' requiere rq y un worker en ejecución.") from exc

    try:
        workers = Worker.all(connection=redis_conn)
    except Exception as exc:
        raise SystemExit(f"No se pudieron listar los workers de RQ: {exc}") from exc

    if not workers:
        raise SystemExit(
            "No se detectaron workers de RQ activos. Arranca 'python -m taskqueue.worker' "
            "o el servicio correspondiente antes de usar --mode stack."
        )


if __name__ == "__main__":
    main()
