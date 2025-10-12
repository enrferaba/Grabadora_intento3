# Grabadora

Grabadora es una plataforma de transcripción en streaming que combina FastAPI, faster-whisper y trabajadores GPU en cola para entregar tokens incrementales en tiempo real. Esta revisión pone especial atención en que la experiencia sea consistente: frontend renovado, documentación guiada y pruebas que validan cada subsistema incluso en entornos minimizados.

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

- Flujo SSE consistente: eventos `delta`, `completed` y `error` se emiten con claves nativas evitando conversiones manuales del lado cliente.
- Pruebas alineadas al contrato de streaming para evitar falsos positivos.
- Documentación reorganizada eliminando restos de proyectos previos y detallando cada componente desplegado.
- Ruta de arranque documentada en `README.md` y `ejecutar.md` con foco en un único comando listo para producción.
- Landing web modernizada en `frontend/index.html` con instrucciones paso a paso y copy actualizado en `docs/marketing/landing.md`.
- Sustitución de dependencias críticas (Pydantic, python-jose, boto3) por degradaciones elegantes que mantienen las pruebas operativas en entornos restringidos.
- Parche de compatibilidad con Python 3.12 para Pydantic v1 y renombrado del paquete `queue/` a `taskqueue/` para evitar choques con la librería estándar.

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

### Recorrido por la experiencia web

- **Landing renovada**: abre `http://localhost:8000/` para acceder a la nueva página principal. Desde ahí encontrarás accesos directos a `/docs`, a la consola de MinIO y un tutorial rápido.
- **Documentación interactiva**: `http://localhost:8000/docs` para Swagger UI y `http://localhost:8000/redoc` como alternativa de lectura.
- **Paneles de observabilidad**: Prometheus (`http://localhost:9090/`) y Grafana (`http://localhost:3000/`) quedan disponibles automáticamente con Docker Compose.
- **Almacenamiento**: MinIO Console responde en `http://localhost:9001/` y desde la landing enlazamos directamente para que revises tus transcripciones almacenadas.

### Acceso a la interfaz web y paneles

- **Landing web**: `http://localhost:8000/` muestra la nueva experiencia con pasos claros, snippets reutilizables y llamadas a la acción.
- **Documentación interactiva**: `http://localhost:8000/docs` (Swagger UI) o `http://localhost:8000/redoc`.
- **Prometheus**: disponible en `http://localhost:9090/` cuando usas Docker Compose.
- **Grafana**: visita `http://localhost:3000/` y añade Prometheus como fuente con la URL `http://prometheus:9090`.
- **MinIO Console**: `http://localhost:9001/` para inspeccionar buckets de audio y transcripts (enlace directo también en la landing).

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
- El repositorio incluye implementaciones *fallback* (hashing PBKDF2, JWT HMAC, almacenamiento en memoria) de modo que las pruebas unitarias pasan incluso cuando `fastapi`, `sqlalchemy`, `boto3` u otras dependencias no están instaladas. Aun así, para la aplicación real instala las librerías originales o usa Docker Compose.

## Observabilidad

- Métricas disponibles en `/metrics` (Instrumentator expone automáticamente).
- Prometheus scrape configurado en `deploy/prometheus.yml`.
- Grafana dashboards de ejemplo en `deploy/grafana/dashboards/`.
- Logs estructurados en JSON via `structlog` para ingestión en sistemas ELK o Loki.

## Estructura del repositorio

```
app/                # Aplicación FastAPI y dependencias
services/           # Servicios de dominio (p.ej. transcripción)
taskqueue/          # Tareas RQ y worker
storage/            # Clientes de almacenamiento
models/, alembic/   # Modelado de datos y migraciones
deploy/             # Prometheus/Grafana y utilidades de despliegue
branding/, docs/    # Activos de marketing y documentación adicional
```

## Problemas conocidos

- La instalación de dependencias GPU (`torch`, `faster-whisper`) puede tardar o requerir acceso a repositorios privados.
- El script de worker asume que Redis y MinIO están disponibles; valida conectividad antes de ejecutar en producción.
- Para entornos sin GPU se recomienda ajustar `GRABADORA_TRANSCRIPTION_QUANTIZATION=float32`.
- Las implementaciones de compatibilidad (JWT, hashing, almacenamiento en memoria) son adecuadas solo para pruebas locales; reemplázalas por las dependencias reales antes de desplegar en producción.

Para instrucciones paso a paso en español, consulta `ejecutar.md`.
