"""Herramienta de diagnóstico para comprobar dependencias y tooling.

Ejecuta comprobaciones rápidas sobre dependencias de Python, utilidades de
terminal y estado del frontend. Opcionalmente puede instalar paquetes que
falten mediante pip y lanzar `npm install` en la carpeta `frontend/`.
"""

from __future__ import annotations

import argparse
import importlib.util
import os
import re
import shutil
import socket
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List

MIN_PYTHON = (3, 10)
MIN_NODE = (20, 0, 0)
DEFAULT_PORTS = {
    8000: "API FastAPI",
    5173: "Frontend Vite",
    9000: "MinIO",
}


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
        elif self.details:
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


def _parse_version(raw: str) -> tuple[int, int, int]:
    match = re.search(r"(\d+)\.(\d+)\.(\d+)", raw)
    if not match:
        return (0, 0, 0)
    major, minor, patch = match.groups()
    return int(major), int(minor), int(patch)


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


def check_node_runtime() -> CheckResult:
    node = shutil.which("node")
    if node is None:
        return CheckResult(
            name="Node.js >= 20 LTS",
            ok=False,
            remedy="Instala Node.js 20 LTS desde https://nodejs.org/",
            details="No se encontró el ejecutable 'node' en PATH.",
        )
    try:
        raw = subprocess.check_output([node, "--version"], text=True).strip()
    except Exception as exc:  # pragma: no cover - depende del entorno
        return CheckResult(
            name="Node.js >= 20 LTS",
            ok=False,
            remedy="Reinstala Node.js o añade el binario correcto al PATH.",
            details=str(exc),
        )
    version = _parse_version(raw)
    ok = version >= MIN_NODE
    return CheckResult(
        name="Node.js >= 20 LTS",
        ok=ok,
        remedy="Actualiza Node.js a la versión 20 LTS o superior.",
        details=f"Versión detectada: {raw}",
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


def check_gpu_status() -> CheckResult:
    command = shutil.which("nvidia-smi")
    if command is None:
        return CheckResult(
            name="nvidia-smi disponible",
            ok=True,
            remedy="Instala los drivers de NVIDIA si deseas usar GPU (opcional).",
            details="No se detectó 'nvidia-smi'; se asumirá ejecución por CPU.",
        )
    try:
        output = subprocess.check_output(
            [command, "--query-gpu=name,memory.total", "--format=csv,noheader"],
            text=True,
        ).strip()
        details = output or "Sin GPUs listadas"
        ok = bool(output)
    except Exception as exc:  # pragma: no cover - depende del entorno
        return CheckResult(
            name="nvidia-smi disponible",
            ok=False,
            remedy="Verifica que los drivers NVIDIA estén correctamente instalados.",
            details=str(exc),
        )
    return CheckResult(
        name="nvidia-smi disponible",
        ok=ok,
        remedy="Conecta una GPU NVIDIA compatible o revisa la instalación del driver.",
        details=details,
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


def check_env_variables(settings) -> List[CheckResult]:
    results: List[CheckResult] = []
    secret_value = settings.jwt_secret
    secret_ok = secret_value not in {
        "",
        "please-change-this-secret",
        "change-me",
        "super-secret",
    }
    results.append(
        CheckResult(
            name="JWT secret configurado",
            ok=secret_ok,
            remedy="Define GRABADORA_JWT_SECRET_KEY en .env con un valor aleatorio.",
            details=None if secret_ok else "Establece un secreto distinto al de ejemplo.",
        )
    )
    db_ok = bool(settings.database_url)
    results.append(
        CheckResult(
            name="Cadena de base de datos definida",
            ok=db_ok,
            remedy="Configura GRABADORA_DATABASE_URL con SQLite, PostgreSQL u otra base soportada.",
            details=settings.database_url if db_ok else "Sin cadena de conexión.",
        )
    )
    access_ok = bool(getattr(settings, "s3_access_key", ""))
    results.append(
        CheckResult(
            name="Credenciales de acceso a S3",
            ok=access_ok,
            remedy="Establece GRABADORA_S3_ACCESS_KEY en el archivo .env.",
            details=None if access_ok else "Falta la clave de acceso a S3/MinIO.",
        )
    )
    secret_key = getattr(settings, "s3_secret_key", None)
    secret_ok = bool(getattr(secret_key, "get_secret_value", lambda: "")())
    results.append(
        CheckResult(
            name="Clave secreta de S3 definida",
            ok=secret_ok,
            remedy="Completa GRABADORA_S3_SECRET_KEY con el secreto de MinIO/S3.",
            details=None if secret_ok else "Se requiere la clave secreta de S3.",
        )
    )
    bucket_audio_ok = bool(getattr(settings, "s3_bucket_audio", ""))
    bucket_tx_ok = bool(getattr(settings, "s3_bucket_transcripts", ""))
    results.append(
        CheckResult(
            name="Buckets de S3 configurados",
            ok=bucket_audio_ok and bucket_tx_ok,
            remedy="Configura GRABADORA_S3_BUCKET_AUDIO y GRABADORA_S3_BUCKET_TRANSCRIPTS.",
            details=None if bucket_audio_ok and bucket_tx_ok else "Asegúrate de definir ambos buckets.",
        )
    )
    return results


def check_ports_available(ports: dict[int, str]) -> CheckResult:
    busy: List[str] = []
    for port, label in ports.items():
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind(("127.0.0.1", port))
        except OSError as exc:
            busy.append(f"{port} ({label}): {exc}")
        finally:
            try:
                sock.close()
            except OSError:
                pass
    ok = not busy
    details = "Todos los puertos están libres." if ok else "; ".join(busy)
    return CheckResult(
        name="Puertos disponibles",
        ok=ok,
        remedy="Libera los puertos ocupados o ajusta los puertos en el archivo .env.",
        details=details,
    )


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


def check_s3_connection(
    endpoint_url: str,
    access_key: str,
    secret_key: str,
    region: str,
    buckets: Iterable[str],
) -> CheckResult:
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
        response = client.list_buckets()
        available = {bucket.get("Name") for bucket in response.get("Buckets", [])}
        missing = [bucket for bucket in buckets if bucket not in available]
        if missing:
            return CheckResult(
                name="S3/MinIO accesible",
                ok=False,
                remedy="Crea los buckets configurados o revisa los permisos del usuario de S3.",
                details=f"Faltan los buckets: {', '.join(missing)}",
            )
        return CheckResult(
            name="S3/MinIO accesible",
            ok=True,
            remedy="El endpoint respondió correctamente.",
            details=f"Buckets disponibles: {', '.join(sorted(available))}",
        )
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
    results.append(check_node_runtime())
    python_results = check_python_packages()
    results.extend(python_results)
    results.extend(check_cli_tools())
    frontend_result = check_frontend_ready()
    results.append(frontend_result)
    results.append(check_ffmpeg_available())
    results.append(check_gpu_status())
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
                settings.s3_secret_key.get_secret_value(),
                settings.s3_region_name,
                [settings.s3_bucket_audio, settings.s3_bucket_transcripts],
            )
        )
    if settings is not None:
        results.extend(check_env_variables(settings))

    results.append(check_ports_available(DEFAULT_PORTS))

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
