#!/usr/bin/env python3
"""Auditoría offline del repositorio para generar RepoAudit.md."""
from __future__ import annotations

import codecs
import re
from datetime import datetime
from pathlib import Path

ROOT = Path.cwd()


def read_bytes_safe(path: Path) -> bytes:
    try:
        return path.read_bytes()
    except Exception:
        return b""


def read_text_guess(path: Path) -> str:
    data = read_bytes_safe(path)
    if not data:
        return ""
    for encoding in ("utf-8", "latin-1"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return ""


def has_bom(path: Path) -> str | None:
    sample = read_bytes_safe(path)[:4]
    if sample.startswith(codecs.BOM_UTF8):
        return "UTF-8 BOM"
    if sample.startswith(codecs.BOM_UTF16_LE):
        return "UTF-16 LE BOM"
    if sample.startswith(codecs.BOM_UTF16_BE):
        return "UTF-16 BE BOM"
    return None


def bullet(text: str) -> str:
    return f"- {text}\n"


def section(title: str) -> str:
    return f"\n\n## {title}\n\n"


def audit_repo(repo: Path) -> str:
    out: list[str] = []
    ts = datetime.now().isoformat(timespec="seconds")
    out.append(f"# RepoAudit — {ts}\n")
    out.append(
        "> Informe generado por scripts/revisa_repo.py. Revisa cada advertencia antes de desplegar.\n"
    )

    env_path = repo / ".env"
    env_text = read_text_guess(env_path) if env_path.exists() else ""
    out.append(section(".env"))
    if env_path.exists():
        out.append(bullet(f"Existe `.env`: {env_path}"))
        bom = has_bom(env_path)
        if bom:
            out.append(bullet(f"ADVERTENCIA: `.env` tiene BOM ({bom}). Debe ser UTF-8 sin BOM."))
        else:
            out.append(bullet("Codificación aparente: OK (sin BOM)"))
        env_txt_path = repo / ".env.txt"
        if env_txt_path.exists():
            out.append(bullet("OJO: existe `.env.txt`. Renómbralo a `.env`."))
        required_keys = {"JWT_SECRET", "JWT_SECRET_KEY", "GRABADORA_JWT_SECRET_KEY"}
        if not any(key in env_text for key in required_keys):
            out.append(bullet("Falta GRABADORA_JWT_SECRET_KEY (o alias) en `.env`."))
    else:
        out.append(bullet("No existe `.env`. Créalo en UTF-8 sin BOM con los secretos mínimos."))

    dc_candidates = ("docker-compose.yml", "docker-compose.yaml")
    dc_path = next(
        (repo / name for name in dc_candidates if (repo / name).exists()),
        None,
    )
    out.append(section("docker-compose"))
    if dc_path:
        dc_text = read_text_guess(dc_path)
        out.append(bullet(f"Encontrado: `{dc_path.name}`"))
        if re.search(r"^\s*version\s*:", dc_text, re.M):
            out.append(bullet("La clave `version:` está presente. En Compose v2 es obsoleta; elimínala."))
        if "env_file" in dc_text and ".env" in dc_text:
            out.append(bullet("Se usa `.env` como env_file; asegúrate de que existe."))
    else:
        out.append(bullet("No se encontró docker-compose.yml. Añade uno si necesitas contenedores."))

    alembic_ini = repo / "alembic.ini"
    alembic_env = repo / "alembic" / "env.py"
    out.append(section("Alembic"))
    if alembic_ini.exists():
        ini_text = read_text_guess(alembic_ini)
        out.append(bullet("Encontrado `alembic.ini`"))
        match = re.search(r"^\s*sqlalchemy\.url\s*=\s*(.+)$", ini_text, re.M)
        if match:
            url = match.group(1).strip()
            out.append(bullet(f"sqlalchemy.url actual: `{url}`"))
        else:
            out.append(bullet("No hay sqlalchemy.url en alembic.ini. Usa variable de entorno o añade la clave."))
    else:
        out.append(bullet("No existe `alembic.ini`. Ejecuta `alembic init` si necesitas migraciones."))

    if alembic_env.exists():
        env_text = read_text_guess(alembic_env)
        if "sys.path.append" in env_text:
            out.append(bullet("`alembic/env.py` ya agrega rutas al sys.path."))
        else:
            out.append(bullet("Añade sys.path.append(...) en alembic/env.py para resolver el paquete app."))
    else:
        out.append(bullet("No existe `alembic/env.py`."))

    db_module = repo / "app" / "database.py"
    out.append(section("app/database.py"))
    if db_module.exists():
        db_text = read_text_guess(db_module)
        out.append(bullet("Encontrado app/database.py"))
        if "def get_engine" not in db_text:
            out.append(bullet("No se detecta get_engine(). Añade la función para reutilizar el engine."))
        if "SessionLocal" not in db_text:
            out.append(bullet("No se detecta SessionLocal en app/database.py."))
    else:
        out.append(bullet("No existe app/database.py."))

    main_py = repo / "app" / "main.py"
    out.append(section("FastAPI"))
    if main_py.exists():
        text = read_text_guess(main_py)
        routes = re.findall(r"@app\.(get|post|put|patch|delete)\(\s*['\"]([^'\"]+)['\"]", text)
        out.append(bullet(f"Rutas detectadas: {len(routes)}"))
    else:
        out.append(bullet("No existe app/main.py."))

    frontend_pkg = repo / "frontend" / "package.json"
    out.append(section("Frontend"))
    if frontend_pkg.exists():
        pkg_text = read_text_guess(frontend_pkg)
        out.append(bullet("Encontrado frontend/package.json"))
        if "Authorization" not in pkg_text:
            auth_refs = 0
            src_dir = repo / "frontend" / "src"
            if src_dir.exists():
                for candidate in src_dir.rglob("*.*"):
                    if candidate.suffix.lower() not in {".ts", ".tsx", ".js", ".jsx"}:
                        continue
                    if "Authorization" in read_text_guess(candidate):
                        auth_refs += 1
            out.append(bullet(f"Archivos con cabecera Authorization detectados: {auth_refs}"))
    else:
        out.append(bullet("No existe frontend/package.json."))

    out.append(section("Acciones sugeridas"))
    suggestions = [
        "Asegura `.env` en UTF-8 sin BOM y con GRABADORA_JWT_SECRET_KEY definido.",
        "Ejecuta `python ejecutar.py` en modo local tras instalar dependencias.",
        "Revisa docker-compose.yml para eliminar la clave version: y mantener healthchecks.",
        "Verifica que app/database.py exporta Base, get_engine() y SessionLocal.",
    ]
    for suggestion in suggestions:
        out.append(bullet(suggestion))

    return "".join(out)


def main() -> None:
    repo = ROOT
    report = audit_repo(repo)
    output_path = repo / "RepoAudit.md"
    output_path.write_text(report, encoding="utf-8")
    print(output_path)


if __name__ == "__main__":
    main()
