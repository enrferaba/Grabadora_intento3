# Grabadora

Grabadora es una plataforma de transcripción en streaming pensada para uso real: backend productivo con FastAPI + Redis/RQ + faster-whisper y un frontend SPA en React/Vite que ofrece tres experiencias clave (Transcribir, Grabar y Biblioteca). El sistema acepta audio subido o grabado desde el navegador, emite tokens delta vía SSE, guarda los resultados en S3/MinIO y permite exportar a TXT/MD/SRT o compartir con herramientas externas como Notion o Trello.

## ¿Qué hay de nuevo en este intento?

- **SPA lista para usuarios**: la carpeta `frontend/` incluye la SPA empaquetada en `dist/` (sin dependencias de Node) y el código fuente React/Vite (`src/`) por si quieres personalizarla. Transcribir, Grabar y Biblioteca funcionan con autenticación JWT, drag & drop, monitor de micro, SSE y exportaciones.
- **Biblioteca con base de datos**: se introdujo el modelo `Transcript` y endpoints REST (`GET /transcripts`, `GET /transcripts/{id}`, `GET /transcripts/{id}/download`, `POST /transcripts/{id}/export`) para listar, buscar y descargar transcripciones finales.
- **Streaming enriquecido**: los eventos `delta` del SSE son JSON con `{text, t0, t1}`; el evento `completed` añade duración, idioma y perfil de calidad. Las pruebas se actualizaron para validar el nuevo contrato.
- **Worker con metadatos persistentes**: cada job registra progreso, perfil de calidad y segmentos en la base de datos, de modo que la Biblioteca pueda mostrar estado, duración y exportaciones aunque el worker se ejecute en otra máquina.
- **Frontend servido desde FastAPI**: el build de Vite se expone desde `/` y se monta `/assets` como estático. Si no se ha compilado la SPA, FastAPI cae en la landing básica para debugging.

## Arquitectura rápida

| Componente | Descripción |
|------------|-------------|
| **FastAPI** | Endpoints de autenticación, subida `POST /transcribe`, streaming `GET /transcribe/{job_id}`, biblioteca de transcripciones y descargas. Maneja JWT, métricas Prometheus, logging estructurado y fallback para dependencias opcionales. |
| **Redis + RQ** | Las peticiones de la API encolan trabajos GPU. El worker (`taskqueue/worker.py`) ejecuta `TranscriptionService` y va actualizando `job.meta` para alimentar el SSE y la base de datos. |
| **faster-whisper** | `services/transcription.py` encapsula la carga del modelo y emite tokens con metadatos de tiempo. Soporta cuantizaciones `float32`, `float16` e `int8`. |
| **S3/MinIO** | `storage/s3.py` guarda audios y transcripts, lista objetos y genera URLs firmadas. Incluye modo memoria para pruebas. |
| **PostgreSQL (SQLAlchemy + Alembic)** | Modelos `User`, `Profile`, `UsageMeter` y `Transcript`. Nueva migración `20240605_02_transcripts` crea la tabla de biblioteca. |
| **Frontend Vite** | SPA con React/Vite, autenticación en `localStorage`, uploader drag & drop, grabador con `MediaRecorder` y biblioteca con búsqueda. Se distribuye un build estático en `frontend/dist/` para que `/` funcione sin pasos extra. |
| **Observabilidad** | Métricas expuestas con `prometheus-fastapi-instrumentator`, dashboards de Grafana y logging JSON via `structlog`. |

## Requisitos previos

- Python 3.11+
- Node.js ≥ 18 (para compilar la SPA)
- Docker y Docker Compose (recomendado para el stack completo)
- NVIDIA Container Toolkit si necesitas GPU

## Configuración de variables

Todas las variables usan el prefijo `GRABADORA_`. Las más relevantes:

- `GRABADORA_REDIS_URL`: URL de Redis (ej. `redis://redis:6379/0`).
- `GRABADORA_DATABASE_URL`: conexión SQLAlchemy (por defecto el PostgreSQL del compose).
- `GRABADORA_S3_ENDPOINT_URL`, `GRABADORA_S3_ACCESS_KEY`, `GRABADORA_S3_SECRET_KEY`: credenciales MinIO/S3.
- `GRABADORA_JWT_SECRET_KEY`: secreto HMAC usado para firmar JWT.
- `GRABADORA_TRANSCRIPTION_QUANTIZATION`: cuantización por defecto de faster-whisper.

Consulta `app/config.py` y `.env.example` para la lista completa.

## Puesta en marcha recomendada (Docker Compose)

1. Copia las variables de ejemplo: `cp .env.example .env` y ajusta credenciales S3/JWT si es necesario.
2. (Opcional) Recompila la SPA si hiciste cambios en `frontend/src`: `cd frontend && npm install && npm run build && cd ..`.
3. Levanta toda la plataforma: `docker compose up --build`.
4. Abre `http://localhost:8000/` para acceder a la SPA. La API, worker, Redis, PostgreSQL, MinIO, Prometheus y Grafana se montan automáticamente.

> Si prefieres ejecutar sin Docker, instala dependencias con Poetry, levanta PostgreSQL/Redis/MinIO manualmente, ejecuta `alembic upgrade head`, genera el build de Vite y arranca `uvicorn app.main:app --reload`. El worker se lanza con `rq worker transcription --url $GRABADORA_REDIS_URL`.

## Cómo usar la interfaz web

- **Transcribir**: arrastra un archivo o selecciona desde el explorador. Elige idioma, perfil de calidad (Rápido/Balanced/Preciso), activa diarización y observa los tokens en vivo. Guarda en biblioteca automáticamente.
- **Grabar**: usa el micro del navegador con visualizador de nivel y reconexión automática. Al detener la grabación se lanza la transcripción y se muestra el stream SSE.
- **Biblioteca**: lista tus transcripciones con búsqueda en vivo, chips de estado, exportaciones a TXT/MD/SRT y acciones "Enviar a Notion/Trello". Cada tarjeta muestra título, etiquetas, calidad y estado.

## Endpoints principales

- `POST /auth/signup` → crea usuario (JSON `{email, password}`).
- `POST /auth/token` → devuelve JWT (`form-data` con `username`, `password`).
- `POST /transcribe` → `multipart/form-data` con `file`, `language`, `profile`, `title`, `tags`, `diarization`, `word_timestamps`. Responde `{job_id, status, quality_profile}`.
- `GET /transcribe/{job_id}` → SSE con eventos:
  - `delta`: `{text, t0, t1}` por token.
  - `completed`: `{job_id, transcript_key, language, duration, quality_profile}`.
  - `error`: `{job_id, detail}`.
- `GET /transcripts` → lista de transcripciones filtrable por `search` y `status`.
- `GET /transcripts/{id}` → detalle completo (segmentos, URL firmada, metadatos).
- `GET /transcripts/{id}/download?format=txt|md|srt` → descarga lista para compartir.
- `POST /transcripts/{id}/export` → encola exportación (`destination` = `notion|trello|webhook`).

La documentación interactiva está disponible en `/docs` (Swagger UI) y `/redoc`.

## Flujo de trabajo del worker

1. La API sube el audio a MinIO/S3 y crea un registro en `transcripts` con estado `queued`.
2. El worker descarga el audio, ejecuta faster-whisper según el perfil de calidad (`fast=int8`, `balanced=float16`, `precise=float32`).
3. Por cada token invoca `_update_job_meta` con el delta JSON, actualizando GPU y longitud de cola para Prometheus.
4. Al finalizar sube el transcript, actualiza la tabla `transcripts` con claves, duración, segmentos y marca `completed`.

## Pruebas

Ejecuta `pytest` en la raíz del proyecto. Los tests cubren:

- `TranscriptionService` (emisión de tokens con tiempos y validación de cuantización).
- Lógica de colas (`taskqueue/tasks.py`) y metadatos guardados.
- Streaming SSE (`app/main._stream_job`).
- Autenticación y utilidades JWT.
- Almacenamiento S3 en modo memoria.

Las implementaciones fallback permiten que las pruebas funcionen incluso si faltan dependencias opcionales (FastAPI, SQLAlchemy, boto3, etc.), pero para la aplicación real se recomienda usar Docker Compose.

## Observabilidad

- Métricas Prometheus expuestas en `/metrics`.
- Configuración del scraper en `deploy/prometheus.yml` y dashboards de ejemplo en `deploy/grafana/dashboards/`.
- Logging JSON vía `structlog` para ingestión en ELK/Loki.

## Estructura del repositorio

```
app/                # Aplicación FastAPI y routers
frontend/           # SPA React/Vite (src/, build en dist/)
services/           # Servicio de transcripción
taskqueue/          # Worker y tareas RQ
storage/            # Cliente S3/MinIO
models/, alembic/   # Modelado y migraciones SQLAlchemy/Alembic
docs/, branding/    # Documentación y material de marketing
deploy/             # Prometheus, Grafana y utilidades
```

## Comando rápido

Si ya tienes Node y Docker instalados, el flujo más corto es:

```bash
docker compose up --build
```

Consulta `ejecutar.md` para una versión abreviada (un único comando) y sugerencias de despliegue.
