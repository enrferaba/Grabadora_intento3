"""Herramienta de diagnóstico para comprobar dependencias y tooling.

Ejecuta comprobaciones rápidas sobre dependencias de Python, utilidades de
terminal y estado del frontend. Opcionalmente puede instalar paquetes que
falten mediante pip y lanzar `npm install` en la carpeta `frontend/`.
"""

from __future__ import annotations

import argparse
import importlib.util
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List


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
}


CLI_REQUIREMENTS = {
    "docker": "Instala Docker Desktop o el motor de Docker.",
    "docker compose": "Activa Docker Compose V2 (incluido en Docker Desktop >= 3.4).",
    "npm": "Instala Node.js LTS desde https://nodejs.org/.",
}


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
    print("Instalando dependencias de frontend (npm install)...")
    subprocess.run(["npm", "install"], cwd=Path("frontend"), check=False)


def run_checks(install_missing: bool = False, fix_frontend: bool = False) -> int:
    print("🔍 Comprobando entorno...")
    results: List[CheckResult] = []
    python_results = check_python_packages()
    results.extend(python_results)
    results.extend(check_cli_tools())
    frontend_result = check_frontend_ready()
    results.append(frontend_result)

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
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    return run_checks(install_missing=args.install_missing, fix_frontend=args.fix_frontend)


if __name__ == "__main__":  # pragma: no cover - ejecución directa
    sys.exit(main())
