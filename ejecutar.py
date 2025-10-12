"""Atajo para levantar la API de desarrollo sin recordar el comando completo."""
from __future__ import annotations

try:
    import uvicorn
except ImportError as exc:  # pragma: no cover
    raise SystemExit(
        "uvicorn no está instalado. Ejecuta 'pip install uvicorn[standard]' o usa docker compose up --build."
    ) from exc


def main() -> None:
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)


if __name__ == "__main__":
    main()
