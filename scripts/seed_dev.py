#!/usr/bin/env python3
"""Crea o actualiza un usuario administrador para entornos de desarrollo.

El script es idempotente: si el usuario ya existe puedes conservar la
contraseña actual, añadir un perfil o regenerar la contraseña con
``--reset-password``. Está pensado para acelerar las demos donde se
reinicia la base de datos SQLite.
"""
from __future__ import annotations

import argparse
from typing import Optional

try:
    from app.auth import get_password_hash
    from app.config import get_settings
    from app.database import Base, get_engine, session_scope
    from models.user import Profile, User
except Exception as exc:  # pragma: no cover - defensivo para instalaciones incompletas
    raise SystemExit(
        "No se pudieron importar los módulos necesarios. Ejecuta este script desde la raíz del "
        "proyecto con las dependencias instaladas."
    ) from exc


def _ensure_tables() -> None:
    engine = get_engine()
    Base.metadata.create_all(bind=engine)


def _create_or_update_user(email: str, password: str, profile_name: str, force_reset: bool) -> str:
    hashed_password = get_password_hash(password)
    with session_scope() as session:
        user: Optional[User] = session.query(User).filter(User.email == email).one_or_none()
        if user is None:
            user = User(email=email, hashed_password=hashed_password, is_active=True)
            session.add(user)
            session.flush()
            session.add(
                Profile(
                    user_id=user.id,
                    name=profile_name,
                    description="Perfil creado automáticamente por seed_dev.py",
                )
            )
            return "created"

        status = "skipped"
        if force_reset:
            user.hashed_password = hashed_password
            status = "password-reset"

        existing_names = {p.name for p in getattr(user, "profiles", []) or []}
        if profile_name and profile_name not in existing_names:
            session.add(Profile(user_id=user.id, name=profile_name))
            status = "updated" if status == "skipped" else status

        return status


def main() -> None:
    parser = argparse.ArgumentParser(description="Crea un usuario admin de desarrollo si no existe")
    parser.add_argument("--email", default="admin@local.com", help="Correo electrónico a registrar")
    parser.add_argument("--password", default="admin123", help="Contraseña para el usuario")
    parser.add_argument(
        "--profile",
        default="Default",
        help="Nombre del perfil inicial (se crea si no existe)",
    )
    parser.add_argument(
        "--reset-password",
        action="store_true",
        help="Regenera la contraseña incluso si el usuario ya existe",
    )
    args = parser.parse_args()

    settings = get_settings()
    print(f"Usando base de datos: {settings.database_url}")
    _ensure_tables()
    result = _create_or_update_user(args.email, args.password, args.profile, args.reset_password)

    messages = {
        "created": "✅ Usuario creado",
        "password-reset": "✅ Usuario existente actualizado y contraseña reseteada",
        "updated": "✅ Usuario existente actualizado",
        "skipped": "ℹ️  Usuario ya existente, sin cambios",
    }
    print(messages.get(result, result))
    print("Email:", args.email)
    if args.reset_password or result in {"created", "password-reset"}:
        print("Contraseña:", args.password)
    else:
        print("Contraseña: (sin cambios)")


if __name__ == "__main__":
    main()
