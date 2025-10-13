"""Atajo para lanzar la API tras verificar dependencias."""

from __future__ import annotations

import argparse
import os
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
    else:
        os.environ.setdefault("GRABADORA_QUEUE_BACKEND", "redis")
    _refresh_settings_cache()
    if mode == "stack":
        _validate_stack_runtime()


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
