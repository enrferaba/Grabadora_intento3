"""Atajo para lanzar la API tras verificar dependencias."""
from __future__ import annotations

import argparse

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
    parser.add_argument("--host", default="0.0.0.0", help="Host de escucha para uvicorn.")
    parser.add_argument("--port", type=int, default=8000, help="Puerto de escucha para uvicorn.")
    parser.add_argument(
        "--reload",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Recarga automática en desarrollo (usa --no-reload para desactivarla).",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not args.skip_checks and doctor is not None:
        exit_code = doctor.run_checks(install_missing=args.install_missing, fix_frontend=args.fix_frontend)
        if exit_code != 0:
            raise SystemExit(
                "Corrige las dependencias anteriores o vuelve a ejecutar con --skip-checks si entiendes los riesgos."
            )
    base_url = f"http://{args.host}:{args.port}"
    print("\nℹ️  Endpoints disponibles:")
    print(f"   • SPA: {base_url}/")
    print(f"   • API interactiva: {base_url}/docs")
    print(f"   • Métricas Prometheus: {base_url}/metrics")
    uvicorn.run("app.main:app", host=args.host, port=args.port, reload=args.reload)


if __name__ == "__main__":
    main()
