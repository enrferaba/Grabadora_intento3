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

## 2. Requisitos y compatibilidad

| Dependencia | Versión mínima recomendada | Motivo |
|-------------|----------------------------|--------|
| Python | 3.12.0 | Evita bugs de `datetime.UTC` ausente en Python 3.9 (observado en reloader) y alinea con dependencias modernas. |
| typing-extensions | ≥ 4.14.1 | Pydantic ≥ 2.12 falla con 4.11.0; fija compatibilidad. |
| python-multipart | ≥ 0.0.20 | Requerido para aceptar formularios multipart en FastAPI (`POST /transcribe`). |
| sse-starlette | ≥ 3.0.0 | Necesario para `EventSourceResponse` estable. |
| Node.js | ≥ 18 LTS | Compilación de la SPA con Vite. |
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
   - Documentar en `doctor.py` la exigencia de Python 3.12, Node/npm en PATH y fallback cuando falte Redis/MinIO.

8. **Persistencia**
   - Confirmar migraciones (`alembic upgrade head`).
   - Verificar que la biblioteca persiste tras reiniciar (usar SQLite en local, PostgreSQL en stack).

## 4. Puesta en marcha

### 4.1 Arranque rápido con Docker Compose
1. Copiar variables: `cp .env.example .env` y completar credenciales S3/JWT.
2. Verificar dependencias locales: `python3.12 -m venv .venv && source .venv/bin/activate` (Linux/macOS) o `py -3.12 -m venv .venv` (Windows PowerShell), luego `python doctor.py`.
3. Compilar frontend si hiciste cambios: `cd frontend && npm install && npm run build && cd ..`.
4. Levantar stack completo: `docker compose up --build`.
5. URLs esperadas: `http://localhost:8000/` (SPA), `http://localhost:8000/docs`, `http://localhost:8000/healthz`, `http://localhost:8000/metrics` (si habilitado).

### 4.2 Ejecución local sin Docker
1. Crear entorno virtual con Python 3.12 y activar.
2. Instalar dependencias: `pip install -r requirements.txt` o `poetry install`.
3. Comprobar entorno: `python doctor.py --install-missing --fix-frontend`.
4. Inicializar base de datos: `alembic upgrade head` (usará SQLite si no hay PostgreSQL).
5. Arrancar API+SPA: `python ejecutar.py --host 0.0.0.0 --port 8000`.
6. (Opcional) Worker: `rq worker transcription --url $GRABADORA_REDIS_URL` o activar fallback en memoria.

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
