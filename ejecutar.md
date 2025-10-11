# Guía de ejecución

Esta guía complementa al `README.md` con instrucciones paso a paso (en español) para poner en marcha la plataforma de transcripción, ya sea con Docker Compose o en un entorno local.

## 1. Preparar el entorno

1. **Clonar el repositorio**
   ```bash
   git clone <URL_DEL_REPO>
   cd Grabadora_intento3
   ```
2. **Crear archivo de entorno**
   ```bash
   cp .env.example .env
   ```
   Ajusta en `.env` las credenciales de S3/MinIO, la URL de Redis y el secreto JWT.
3. **Instalar requisitos del sistema**
   - Docker y Docker Compose
   - NVIDIA Container Toolkit (solo si se usará GPU)
   - Para ejecución local: Python 3.11+, Redis, PostgreSQL y MinIO (puedes reutilizar los servicios del compose).

## 2. Ejecutar con Docker Compose (recomendado)

1. Construir y levantar servicios:
   ```bash
   docker compose up --build
   ```
2. Verificar salud:
   - API: http://localhost:8000/docs
   - Prometheus: http://localhost:9090
   - Grafana: http://localhost:3000 (usuario/clave por defecto `admin`/`admin`)
3. Registrar un usuario y autenticar:
   - `POST http://localhost:8000/users` con JSON `{ "email": "demo@example.com", "password": "demo" }`
   - `POST http://localhost:8000/auth/token` con formulario `username=demo@example.com`, `password=demo`
4. Transcribir:
   - `POST http://localhost:8000/transcribe` (multipart con campo `file`)
   - Escuchar SSE en `GET http://localhost:8000/transcribe/<job_id>`

## 3. Ejecución local (sin Docker)

1. Crear entorno virtual e instalar dependencias:
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   pip install poetry
   poetry install
   ```
2. Ejecutar migraciones:
   ```bash
   alembic upgrade head
   ```
3. Lanzar servicios auxiliares (si no usas Docker):
   - Redis (`redis-server`)
   - PostgreSQL (crea la base `grabadora`)
   - MinIO (`minio server /data`)
4. Iniciar API y worker:
   ```bash
   uvicorn app.main:app --reload
   rq worker transcription --url $GRABADORA_REDIS_URL
   ```

## 4. Pruebas automáticas

```bash
pytest
```

> **Nota:** si el entorno no tiene acceso a PyPI, instala las dependencias dentro de un contenedor Docker (`docker compose run --rm api poetry install`).

## 5. Resolución de problemas comunes

| Problema | Solución |
|----------|----------|
| `ModuleNotFoundError` al correr `pytest` | Asegúrate de instalar las dependencias (`poetry install` o `pip install -r requirements`). |
| Error `redis package is not installed` | Instala `redis` o levanta las pruebas dentro del contenedor API/worker. |
| Los eventos SSE no llegan | Comprueba que el worker esté en ejecución y que Redis esté accesible. |
| Dependencias GPU fallan al instalar | Utiliza la imagen de Docker con soporte CUDA incluida en `docker-compose.yml` o cambia la cuantización a `float32`. |

## 6. Limpieza

Para detener y limpiar contenedores creados por Docker Compose:
```bash
docker compose down -v
```

Si ejecutaste localmente, desactiva el entorno virtual y apaga Redis/PostgreSQL/MinIO manualmente.
