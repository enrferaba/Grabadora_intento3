# Grabadora · Guía de mantenimiento

> Objetivo inmediato: dejar la plataforma lista para que cualquier persona suba un audio desde la web, siga el progreso en vivo, consulte la biblioteca de transcripciones y descargue TXT/SRT sin toparse con 404/405 ni dependencias rotas.

## 1. Visión general del sistema

| Componente | Responsabilidad | Implementación actual |
|------------|-----------------|------------------------|
| API FastAPI | Autenticación JWT, subida `POST /transcribe` (multipart), progreso por SSE `GET /transcribe/{job_id}`, gestión de biblioteca (`GET /transcripts*`) y descargas. | `app/main.py`, `app/auth.py`, `app/schemas.py`, `models/`. |
| Worker/cola | Procesa jobs `transcribe_job`, genera tokens SSE y persiste segmentos/duración. | `taskqueue/tasks.py`, fallback en memoria en `taskqueue/fallback.py`, Redis/RQ opcional. |
| Storage | Guarda audio/transcripciones en S3/MinIO con fallback a disco local (`storage/`). | `storage/s3.py`, configurado desde `GRABADORA_*`. |
| Frontend SPA | Rutas `/`, `/transcribir`, `/biblioteca`, manejo de fullscreen, subida multipart, consumo SSE. | `frontend/src/` (React/Vite) con build en `frontend/dist/`. |
| Observabilidad | Métricas Prometheus opcionales en `/metrics`, healthcheck `/healthz`, logging estructurado. | `app/main.py`, `deploy/prometheus.yml`. |

### Flujo resumido
1. Usuario se autentica (`/auth/signup`, `/auth/token`).
2. SPA sirve `/` y controla rutas internas; las navegaciones directas deben resolverse vía fallback del backend a `frontend/dist/index.html`.
3. La subida `POST /transcribe` recibe `multipart/form-data` con `file` y metadatos; responde `{job_id}`.
4. El frontend abre `GET /transcribe/{job_id}` como SSE. Se esperan eventos `delta`, `progress`, `completed` y `error`.
5. Al finalizar, `GET /transcripts` y `GET /transcripts/{id}` muestran detalle; `/download` y `/export` permiten exportar.
6. Descargas deben emitirse como archivos (`Content-Disposition`) y reflejar los perfiles configurados.

### Endpoints principales

| Ruta | Método | Descripción | Parámetros |
|------|--------|-------------|------------|
| `/auth/signup` | POST | Registra un usuario y crea el perfil "Default". | JSON: `email`, `password`. |
| `/auth/token` | POST | Devuelve `access_token` (OAuth2 password flow). | Form URL-encoded: `username`, `password`, `grant_type=password`. |
| `/transcribe` | POST | Sube un audio y encola la transcripción. | `multipart/form-data`: `file` (obligatorio), `language?`, `profile?`, `title?`, `tags?`, `diarization?`, `word_timestamps?`. |
| `/transcribe/{job_id}` | GET (SSE) | Stream en tiempo real de `delta`, `snapshot`, `heartbeat` y `completed`. | Header `Authorization: Bearer <token>`; path `job_id`. |
| `/jobs/{job_id}` | GET | Consulta estado del job y metadatos (progreso, URL firmada). | Header `Authorization`; path `job_id`. |
| `/transcripts` | GET | Lista de transcripciones del usuario autenticado. | Query opcionales: `search`, `status`. |
| `/transcripts/{id}` | GET | Detalle completo con segmentos, metadatos y URL. | Path `id`; header `Authorization`. |
| `/transcripts/{id}` | PATCH | Actualiza título, notas, etiquetas o perfil de calidad. | JSON parcial con `title`, `notes`, `tags`, `quality_profile`. |
| `/transcripts/{id}` | DELETE | Elimina transcripción y blobs asociados. | Path `id`; header `Authorization`. |
| `/transcripts/{id}/download` | GET | Descarga en TXT/MD/SRT con `Content-Disposition`. | Query `format` (`txt`, `md`, `srt`). |
| `/transcripts/{id}/export` | POST | Encola exportación a Notion/Trello/Webhook. | JSON: `destination`, `format`, `note?`. |
| `/profiles` | GET | Devuelve perfiles de calidad disponibles y personalizados. | Header `Authorization`. |
| `/config` | GET | Config general de la SPA (SSE, colas, storage). | — |
| `/healthz` | GET | Healthcheck rápido para despliegues. | — |

## 2. Requisitos y compatibilidad

| Dependencia | Versión mínima recomendada | Motivo |
|-------------|----------------------------|--------|
| Python | 3.11.0 (ideal 3.12) | Evita bugs de `datetime.UTC` ausente en Python 3.9 y alinea con dependencias modernas. |
| typing-extensions | ≥ 4.14.1 | Pydantic ≥ 2.12 falla con 4.11.0; fija compatibilidad. |
| python-multipart | ≥ 0.0.20 | Requerido para aceptar formularios multipart en FastAPI (`POST /transcribe`). |
| sse-starlette | ≥ 3.0.0 | Necesario para `EventSourceResponse` estable. |
| Node.js | ≥ 20 LTS | Compilación de la SPA con Vite y compatibilidad con la API global `fetch`. |
| FFmpeg | Binario disponible en PATH | Normaliza audio previo a transcripción (`app/utils/storage.py`). |
| Docker + Compose | Opcional | Levantar stack completo (API, worker, Redis, PostgreSQL, MinIO, Prometheus). |

**Compatibilidad de almacenamiento**
- Local: fallback automático a disco documentado en `storage/s3.py`. Asegurarse de que la ruta `storage/local/` exista y tenga permisos de escritura.
- Stack: MinIO con credenciales `GRABADORA_S3_*`. Las descargas deben usar URLs firmadas o streaming directo.

## 3. Checklist técnico previo a merge

1. **Rutas frontend/backend alineadas**
   - Mantener `/` sirviendo la SPA. Configurar fallback que responda `index.html` a toda ruta no-API.
   - Evitar llamar a endpoints inexistentes (`/transcribir`, `/transcripts`) desde la SPA; la lógica de cliente debe manejar esas rutas internamente y usar los endpoints REST documentados (ver [routes.md](routes.md)).

2. **Formulario multipart**
   - Confirmar que `POST /transcribe` se consume con `multipart/form-data` y campo `file` obligatorio.
   - Añadir pruebas manuales/automatizadas con `curl -F` o formulario real para evitar 405/422.

3. **SSE robusto**
   - Implementar heartbeat (`event: ping\ndata: {"ts": ...}` cada ≤15s) y reconexión automática al reiniciar backend.
   - Controlar `ClientDisconnect` para liberar recursos y registrar métricas.
   - Documentar reconexión del frontend (retry exponencial, reanudar desde último token).

4. **Endpoints complementarios (recomendados)**
   - `PATCH /transcripts/{id}` para título/notas.
   - `DELETE /transcripts/{id}` para eliminar audio + transcript + registros.
   - `GET /profiles` para listar perfiles disponibles desde BD.
   - `GET /config` para exponer límites (tamaño máximo, SSE habilitado, storage activo).

5. **Métricas y salud**
   - Decidir si `/metrics` estará disponible en local. Si no, retirarlo de documentación.
   - Healthcheck `/healthz` debe incluir chequeos de almacenamiento/cola básicos.

6. **Fullscreen UX**
   - Botón visible de “Salir de pantalla completa”.
   - Mensaje recordatorio de Esc/F11.

7. **Dependencias coherentes**
   - Congelar versiones en `pyproject.toml`/`package.json` tras validar.
   - Documentar en `doctor.py` la exigencia de Python 3.11+, Node 20 LTS, puertos libres y fallback cuando falte Redis/MinIO.

8. **Persistencia**
   - Confirmar migraciones (`alembic upgrade head`).
   - Verificar que la biblioteca persiste tras reiniciar (usar SQLite en local, PostgreSQL en stack).

9. **Calidad automatizada**
   - Ejecutar `ruff check .`, `black --check .` y `pytest` antes de subir cambios.

## 4. Puesta en marcha

### 4.1 Arranque rápido con Docker Compose
1. Copiar variables: `cp .env.example .env` y rellenar credenciales **antes** de arrancar (el backend falla si detecta secretos de ejemplo).
2. Preparar entorno local (opcional pero recomendado): `python3.11 -m venv .venv && source .venv/bin/activate` (Linux/macOS) o `py -3.11 -m venv .venv` (Windows), luego `python doctor.py --mode stack` para validar Python ≥3.11, Node ≥20, puertos libres y acceso a MinIO.
3. Si el frontend cambió, instala dependencias: `cd frontend && npm install && cd ..`.
4. Levantar servicios principales: `docker compose up --build`. Usa `docker compose --profile queue up --build` si quieres incluir el worker de RQ.
5. URLs esperadas: `http://localhost:5173/` (SPA en Vite), `http://localhost:8000/docs`, `http://localhost:8000/healthz`, `http://localhost:9001/` (MinIO console).

### 4.2 Ejecución local sin Docker
1. Crear entorno virtual con Python 3.11+: `python3.11 -m venv .venv && source .venv/bin/activate`.
2. Instalar dependencias backend: `pip install -r requirements.txt` (o `poetry install`).
3. Validar entorno y puertos libres: `python doctor.py --mode local --install-missing --fix-frontend`.
4. Ejecutar migraciones si usas PostgreSQL: `alembic upgrade head`. En modo local sin DB externa se usará SQLite automáticamente.
5. Arrancar el backend: `uvicorn app.main:app --reload --host 0.0.0.0 --port 8000`.
6. En otra terminal, servir la SPA: `cd frontend && npm install && npm run dev -- --host 0.0.0.0 --port 5173`.
7. (Opcional) Worker dedicado: `rq worker transcription --url $GRABADORA_REDIS_URL` o deja que el backend use la cola en memoria.

## 5. Verificación manual recomendada

| Caso | Pasos | Resultado esperado |
|------|-------|--------------------|
| Smoke test | Abrir `/`, subir audio de 10–20 s, observar estados `queued → started → completed`. | UI muestra progreso en vivo; al terminar, biblioteca actualiza registro y ofrece descarga TXT/SRT. |
| Rutas SPA | Navegar directamente a `/transcribir` y `/biblioteca`. | Backend sirve `index.html` sin 404; router de SPA muestra vista correcta. |
| SSE resiliente | Iniciar transcripción y reiniciar backend (Ctrl+C + relanzar). | SSE se reconecta sin perder texto mostrado. |
| API contract | Usar `/docs` para probar `POST /transcribe` (multipart), `GET /transcribe/{job_id}` (SSE), `GET /transcripts`, `GET /transcripts/{id}/download`. | Respuestas 200/201/204 según corresponda, sin 404/405. |
| Entorno | Ejecutar `ffmpeg -version`, `python -V`, `where python`/`which python`, `npm -v`. | Versiones correctas y apuntando al entorno del proyecto. |

## 6. Documentación complementaria

- [ejecutar.md](ejecutar.md): comandos detallados (Windows/Linux), opciones de `ejecutar.py`, diagnóstico de errores comunes.
- [explicacion.md](explicacion.md): narrativa técnica del flujo completo (Frontend → API → Worker → Storage/DB → Biblioteca/Export).
- [routes.md](routes.md): tabla de rutas frontend vs backend, métodos, Content-Type y estado.
- [errors.md](errors.md): incidentes reales, causa raíz e instrucciones de mitigación.
- `docs/configuration.md`, `docs/deployment.md`: profundizan en despliegue avanzado.

## 7. Próximos entregables sugeridos

1. Implementar y documentar `PATCH/DELETE /transcripts/{id}`, `GET /profiles`, `GET /config`.
2. Añadir pruebas automatizadas para multipart, SSE y fallback SPA.
3. Integrar `make doctor` en CI para validar entorno mínimo.
4. Producir dashboard básico para Prometheus/Grafana con métricas clave (jobs activos, latencia SSE, tamaño de cola).

Mantén este README sincronizado con la realidad del proyecto tras cada iteración.
