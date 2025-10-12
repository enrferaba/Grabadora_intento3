"""Herramienta de diagnóstico para comprobar dependencias y tooling.

Ejecuta comprobaciones rápidas sobre dependencias de Python, utilidades de
terminal y estado del frontend. Opcionalmente puede instalar paquetes que
falten mediante pip y lanzar `npm install` en la carpeta `frontend/`.
"""

from __future__ import annotations

import argparse
import importlib.util
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List

MIN_PYTHON = (3, 11)


@dataclass
class CheckResult:
    """Representa el resultado de una comprobación."""

    name: str
    ok: bool
    remedy: str
    details: str | None = None

    def render(self) -> str:
        prefix = "✅" if self.ok else "❌"
        line = f"{prefix} {self.name}"
        if not self.ok:
            line += f"\n   Sugerencia: {self.remedy}"
            if self.details:
                line += f"\n   Detalle: {self.details}"
        return line


PYTHON_REQUIREMENTS = {
    "fastapi": "fastapi[standard]",
    "uvicorn": "uvicorn[standard]",
    "sqlalchemy": "sqlalchemy",
    "alembic": "alembic",
    "redis": "redis",
    "rq": "rq",
    "boto3": "boto3",
    "faster_whisper": "faster-whisper",
    "sse_starlette": "sse-starlette",
    "prometheus_client": "prometheus-client",
    "structlog": "structlog",
    "jose": "python-jose[cryptography]",
    "multipart": "python-multipart",
}


CLI_REQUIREMENTS = {
    "docker": "Instala Docker Desktop o el motor de Docker.",
    "docker compose": "Activa Docker Compose V2 (incluido en Docker Desktop >= 3.4).",
    "npm": "Instala Node.js LTS desde https://nodejs.org/.",
}

FFMPEG_REMEDY = "Instala FFmpeg y asegúrate de que 'ffmpeg' esté en el PATH."


def check_python_packages() -> List[CheckResult]:
    results: List[CheckResult] = []
    for module, requirement in PYTHON_REQUIREMENTS.items():
        spec = importlib.util.find_spec(module)
        results.append(
            CheckResult(
                name=f"Módulo de Python '{module}'",
                ok=spec is not None,
                remedy=f"pip install {requirement}",
            )
        )
    return results


def check_python_runtime() -> CheckResult:
    version = sys.version_info
    interpreter = Path(sys.executable)
    ok = version >= MIN_PYTHON
    details: str | None = None
    if not ok:
        details = f"Se detectó Python {version.major}.{version.minor}.{version.micro}."
    elif "WindowsApps" in interpreter.parts:
        ok = False
        details = f"El intérprete activo es {interpreter}."
    remedy = (
        "Activa el entorno virtual del proyecto con Python 3.11+ y desactiva los alias de la Microsoft Store."
    )
    return CheckResult(
        name="Intérprete de Python compatible",
        ok=ok,
        remedy=remedy,
        details=details,
    )


def check_cli_tools() -> List[CheckResult]:
    results: List[CheckResult] = []
    for command, remedy in CLI_REQUIREMENTS.items():
        if command == "docker compose":
            has_compose = shutil.which("docker") is not None and _has_docker_compose()
            results.append(CheckResult(name="docker compose", ok=has_compose, remedy=remedy))
            continue
        results.append(CheckResult(name=command, ok=shutil.which(command) is not None, remedy=remedy))
    return results


def check_frontend_ready() -> CheckResult:
    node_modules = Path("frontend/node_modules")
    lock_file = Path("frontend/package-lock.json")
    ok = node_modules.exists() and lock_file.exists()
    return CheckResult(
        name="Dependencias de frontend instaladas",
        ok=ok,
        remedy="Ejecuta 'npm install' dentro de la carpeta frontend/",
        details=None if ok else "No se encontró 'frontend/node_modules/'.",
    )


def check_ffmpeg_available() -> CheckResult:
    ok = shutil.which("ffmpeg") is not None
    return CheckResult(
        name="FFmpeg disponible",
        ok=ok,
        remedy=FFMPEG_REMEDY,
        details=None if ok else "Añade el ejecutable 'ffmpeg' al PATH del sistema.",
    )


def check_frontend_build() -> CheckResult:
    dist_dir = Path("frontend/dist")
    index_file = dist_dir / "index.html"
    ok = dist_dir.exists() and index_file.exists()
    return CheckResult(
        name="Build de frontend generado",
        ok=ok,
        remedy="Ejecuta 'npm run build' dentro de frontend/ para crear la carpeta dist/.",
        details=None if ok else "No se encontró 'frontend/dist/index.html'.",
    )


def _load_settings():
    try:
        from app.config import get_settings  # type: ignore

        return get_settings()
    except Exception:
        return None


def check_redis_connection(url: str) -> CheckResult:
    try:
        from redis import Redis  # type: ignore
    except ImportError:
        return CheckResult(
            name="Redis accesible",
            ok=False,
            remedy="Instala la dependencia 'redis' y asegúrate de que el servicio esté levantado.",
            details="No se pudo importar la librería redis.",
        )
    try:
        client = Redis.from_url(url)
        client.ping()
        return CheckResult(name="Redis accesible", ok=True, remedy="Redis responde al ping.")
    except Exception as exc:  # pragma: no cover - depende del entorno
        return CheckResult(
            name="Redis accesible",
            ok=False,
            remedy="Arranca Redis o ajusta GRABADORA_REDIS_URL.",
            details=str(exc),
        )


def check_database_connection(url: str) -> CheckResult:
    try:
        from sqlalchemy import create_engine  # type: ignore
    except ImportError:
        return CheckResult(
            name="Base de datos disponible",
            ok=False,
            remedy="Instala SQLAlchemy para validar la conexión a la base de datos.",
            details="No se pudo importar SQLAlchemy.",
        )
    engine = create_engine(url, future=True)
    try:
        with engine.connect():
            pass
        return CheckResult(name="Base de datos disponible", ok=True, remedy="Conexión establecida correctamente.")
    except Exception as exc:  # pragma: no cover - depende del entorno
        return CheckResult(
            name="Base de datos disponible",
            ok=False,
            remedy="Arranca la base de datos o corrige la cadena DATABASE_URL.",
            details=str(exc),
        )


def check_s3_connection(endpoint_url: str, access_key: str, secret_key: str, region: str) -> CheckResult:
    try:
        import boto3  # type: ignore
    except ImportError:
        return CheckResult(
            name="S3/MinIO accesible",
            ok=False,
            remedy="Instala boto3 para verificar el almacenamiento.",
            details="No se pudo importar boto3.",
        )
    try:
        client = boto3.client(
            "s3",
            endpoint_url=endpoint_url,
            region_name=region,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
        )
        client.list_buckets()
        return CheckResult(name="S3/MinIO accesible", ok=True, remedy="El endpoint respondió correctamente.")
    except Exception as exc:  # pragma: no cover - depende del entorno
        return CheckResult(
            name="S3/MinIO accesible",
            ok=False,
            remedy="Arranca MinIO o ajusta las credenciales de S3.",
            details=str(exc),
        )


def _has_docker_compose() -> bool:
    try:
        result = subprocess.run(
            ["docker", "compose", "version"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        return result.returncode == 0
    except FileNotFoundError:
        return False


def install_missing_python(packages: Iterable[str]) -> None:
    missing = [pkg for pkg in packages if importlib.util.find_spec(pkg) is None]
    if not missing:
        print("Todas las dependencias de Python ya están instaladas.")
        return
    print("Instalando dependencias de Python que faltan...")
    for module in missing:
        requirement = PYTHON_REQUIREMENTS[module]
        print(f"  -> {requirement}")
        subprocess.run([sys.executable, "-m", "pip", "install", requirement], check=False)


def ensure_frontend_dependencies() -> None:
    npm_path = shutil.which("npm")
    if npm_path is None:
        print("No se pudo ejecutar 'npm install' porque 'npm' no está disponible en PATH.")
        print("Instala Node.js o añade 'npm' al PATH y vuelve a intentarlo.")
        return

    print("Instalando dependencias de frontend (npm install)...")
    subprocess.run([npm_path, "install"], cwd=Path("frontend"), check=False)


def run_checks(install_missing: bool = False, fix_frontend: bool = False, *, mode: str = "auto") -> int:
    print("🔍 Comprobando entorno...")
    results: List[CheckResult] = []
    results.append(check_python_runtime())
    python_results = check_python_packages()
    results.extend(python_results)
    results.extend(check_cli_tools())
    frontend_result = check_frontend_ready()
    results.append(frontend_result)
    results.append(check_ffmpeg_available())
    results.append(check_frontend_build())

    settings = _load_settings()
    normalized_mode = mode
    if normalized_mode not in {"local", "stack"}:
        requested = os.getenv("GRABADORA_QUEUE_BACKEND", "auto").lower()
        if requested == "redis":
            normalized_mode = "stack"
        elif requested == "memory":
            normalized_mode = "local"
        else:
            normalized_mode = "local"

    if normalized_mode == "stack" and settings is not None:
        results.append(check_redis_connection(settings.redis_url))
        results.append(check_database_connection(settings.database_url))
        results.append(
            check_s3_connection(
                settings.s3_endpoint_url,
                settings.s3_access_key,
                settings.s3_secret_key,
                settings.s3_region_name,
            )
        )

    for item in results:
        print(item.render())

    if install_missing:
        install_missing_python(PYTHON_REQUIREMENTS.keys())
    if fix_frontend and not frontend_result.ok:
        ensure_frontend_dependencies()

    failures = sum(1 for item in results if not item.ok)
    if failures:
        print(f"\n❌ {failures} comprobación(es) no superadas. Consulta las sugerencias anteriores.")
    else:
        print("\n✅ Todo listo. Puedes ejecutar la plataforma.")
    return 0 if failures == 0 else 1


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verifica dependencias del proyecto.")
    parser.add_argument(
        "--install-missing",
        action="store_true",
        help="Intenta instalar las dependencias de Python ausentes usando pip.",
    )
    parser.add_argument(
        "--fix-frontend",
        action="store_true",
        help="Ejecuta 'npm install' en frontend/ si faltan dependencias de la SPA.",
    )
    parser.add_argument(
        "--mode",
        choices=["auto", "local", "stack"],
        default="auto",
        help="Determina si se deben comprobar servicios externos (stack) o solo dependencias locales.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    return run_checks(
        install_missing=args.install_missing,
        fix_frontend=args.fix_frontend,
        mode=args.mode,
    )


if __name__ == "__main__":  # pragma: no cover - ejecución directa
    sys.exit(main())
