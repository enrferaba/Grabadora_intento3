# Grabadora

Grabadora es una plataforma de transcripción en streaming que combina FastAPI, faster-whisper y trabajadores GPU en cola para entregar tokens incrementales en tiempo real. Esta revisión incluye una limpieza completa de los artefactos heredados, documentación actualizada y comprobaciones automáticas para asegurar que cada subsistema funcione como se espera.

## Arquitectura

| Componente | Descripción |
|------------|-------------|
| **API FastAPI** | Expone `/transcribe` (SSE) y `/transcribe/{job_id}` para recibir audio y emitir tokens delta. Integra autenticación JWT, métricas Prometheus y logging estructurado. |
| **Cola Redis + RQ** | La API delega los trabajos a trabajadores GPU mediante Redis Queue. El estado del trabajo se guarda en `job.meta` para alimentar el stream SSE. |
| **Servicio faster-whisper** | `services/transcription.py` encapsula la carga del modelo con distintos niveles de cuantización (`float32`, `float16`, `int8`). Cada token emitido se reenvía al stream SSE. |
| **Almacenamiento S3/MinIO** | `storage/s3.py` persiste los audios recibidos y los textos finales. Al completarse el trabajo se devuelve la clave del transcript almacenado. |
| **Base de datos PostgreSQL** | Modelos SQLAlchemy gestionados con Alembic (`models/user.py`, `alembic/`). Soporta múltiples perfiles por usuario y metering básico. |
| **Autenticación** | Flujo OAuth2 password con JWT (`app/auth.py`). Los endpoints críticos dependen de `get_current_user`. |
| **Observabilidad** | Métricas `prometheus-client` + `prometheus-fastapi-instrumentator` y dashboards de Grafana (`deploy/grafana/`). |

## Qué se corrigió y mejoró en esta revisión

- Se normalizó el flujo SSE para enviar estructuras nativas (`event`, `data`) en lugar de cadenas JSON arbitrarias, evitando parsing innecesario en los clientes.
- Se ajustaron las pruebas de streaming para reflejar el nuevo contrato y prevenir falsos positivos.
- Se reorganizó la documentación principal, eliminando restos de proyectos previos y detallando cada componente desplegado.
- Se documentó claramente la configuración mínima y los pasos de ejecución en nuevos archivos (`README.md`, `ejecutar.md`).

## Requisitos previos

- Python 3.11+
- Docker y Docker Compose (para el stack completo)
- NVIDIA Container Toolkit si se requiere GPU
- Acceso a credenciales S3/MinIO y a una instancia de Redis/PostgreSQL (o usar las que provee `docker-compose.yml`).

## Configuración

Las variables de entorno se cargan con el prefijo `GRABADORA_`. Las más relevantes:

- `GRABADORA_REDIS_URL`: URL de Redis (por defecto `redis://redis:6379/0`).
- `GRABADORA_DATABASE_URL`: conexión SQLAlchemy (por defecto PostgreSQL dentro del compose).
- `GRABADORA_S3_ENDPOINT_URL`, `GRABADORA_S3_ACCESS_KEY`, `GRABADORA_S3_SECRET_KEY`: credenciales y endpoint para almacenamiento.
- `GRABADORA_JWT_SECRET_KEY`: secreto para firmar tokens.
- `GRABADORA_TRANSCRIPTION_QUANTIZATION`: cuantización para faster-whisper.

Consulta `app/config.py` para la lista completa y descripciones.

## Puesta en marcha rápida

### ¿Docker o entorno local?

Para aislar dependencias (Redis, PostgreSQL, MinIO, Prometheus) y evitar discrepancias en librerías GPU, la opción más estable es ejecutar todo con **Docker Compose**. Esto garantiza que tanto la API como el worker utilicen las mismas versiones de CUDA, `faster-whisper` y drivers de sistema. Si solo necesitas hacer desarrollos rápidos en CPU puedes optar por instalar las dependencias localmente, pero tendrás que provisionar los servicios externos manualmente.

### Desarrollo local con Poetry (solo si ya cuentas con los servicios externos)

1. Crea y activa un entorno virtual.
2. Instala dependencias: `poetry install`.
3. Exporta las variables de entorno necesarias o copia `.env.example`.
4. Ejecuta migraciones: `alembic upgrade head`.
5. Levanta la API: `uvicorn app.main:app --reload`.
6. Inicia el worker en otra terminal: `rq worker transcription --url $GRABADORA_REDIS_URL`.

### Stack completo con Docker Compose (recomendado)

1. Copia `.env.example` a `.env` y ajusta valores (S3, JWT, etc.).
2. Ejecuta `docker compose up --build`.
3. El compose incluye servicios para API, worker, Redis, PostgreSQL, MinIO, Prometheus y Grafana.

## Uso de la API

1. Crea un usuario vía `POST /users` (JSON: `{"email": "...", "password": "..."}`).
2. Solicita token en `POST /auth/token` (form-data `username`, `password`).
3. En `POST /transcribe` envía un archivo de audio (`multipart/form-data`, campo `file`) y opcionalmente `language`.
4. Consume `GET /transcribe/{job_id}` mediante SSE. Se recibirán eventos:
   - `delta`: tokens incrementales.
   - `completed`: JSON con `job_id`, `transcript_key`, `language`.
   - `error`: identificador del problema.
5. Recupera el transcript final directamente desde MinIO/S3 usando la clave entregada.

## Pruebas

- Ejecuta `pytest` para validar autenticación, cola, almacenamiento y lógica de streaming.
- Si faltan dependencias opcionales (por ejemplo `fastapi`, `redis`, `rq`), instálalas antes o ejecuta las pruebas dentro del contenedor Docker.

## Observabilidad

- Métricas disponibles en `/metrics` (Instrumentator expone automáticamente).
- Prometheus scrape configurado en `deploy/prometheus.yml`.
- Grafana dashboards de ejemplo en `deploy/grafana/dashboards/`.
- Logs estructurados en JSON via `structlog` para ingestión en sistemas ELK o Loki.

## Estructura del repositorio

```
app/                # Aplicación FastAPI y dependencias
services/           # Servicios de dominio (p.ej. transcripción)
queue/              # Tareas RQ y worker
storage/            # Clientes de almacenamiento
models/, alembic/   # Modelado de datos y migraciones
deploy/             # Prometheus/Grafana y utilidades de despliegue
branding/, docs/    # Activos de marketing y documentación adicional
```

## Problemas conocidos

- La instalación de dependencias GPU (`torch`, `faster-whisper`) puede tardar o requerir acceso a repositorios privados.
- El script de worker asume que Redis y MinIO están disponibles; valida conectividad antes de ejecutar en producción.
- Para entornos sin GPU se recomienda ajustar `GRABADORA_TRANSCRIPTION_QUANTIZATION=float32`.

Para instrucciones paso a paso en español, consulta `ejecutar.md`.
