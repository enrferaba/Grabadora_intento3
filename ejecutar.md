# Ejecutar la plataforma

## Ruta recomendada (Docker Compose)

```bash
docker compose up --build
```

El comando anterior construye las imágenes y levanta API, worker, Redis, PostgreSQL, MinIO, Prometheus, Grafana y la SPA en `http://localhost:8000/`.

## Diagnóstico rápido y ejecución local

1. Comprueba que tienes todas las dependencias clave:

   ```bash
   python doctor.py
   ```

   - Añade `--install-missing` para que intente instalar los paquetes de Python que falten.
   - Añade `--fix-frontend` si quieres que ejecute `npm install` en `frontend/` automáticamente.

2. Lanza la API en modo desarrollo (incluye la comprobación previa salvo que uses `--skip-checks`):

   ```bash
   python ejecutar.py
   ```

   Puedes personalizar host y puerto, por ejemplo: `python ejecutar.py --host 127.0.0.1 --port 9000`.
