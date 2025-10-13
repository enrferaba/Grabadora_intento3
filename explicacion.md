# Explicación técnica del flujo de Grabadora

Este documento describe el recorrido de una transcripción desde que el usuario interactúa con la SPA hasta que obtiene los archivos exportables. Sirve como referencia para mantener la coherencia entre componentes.

## 1. Frontend (React/Vite)

1. La SPA se sirve desde `frontend/dist/` y monta un router que gestiona rutas internas (`/`, `/transcribir`, `/biblioteca`).
2. Al iniciar una transcripción, el componente de subida crea un `FormData` con:
   - `file`: blob de audio seleccionado o grabado.
   - `language`, `profile`, `title`, `tags`, `diarization`, `word_timestamps`.
3. La petición va a `POST /transcribe` con cabecera `Authorization: Bearer <token>`.
4. Tras recibir `{job_id}`, la SPA abre un `EventSource` a `GET /transcribe/{job_id}` con reconexión automática.
5. Los eventos SSE esperados:
   - `delta`: texto incremental con posiciones `t0/t1`.
   - `progress`: porcentaje aproximado.
   - `completed`: metadatos finales (`transcript_id`, `language`, `duration`).
   - `error`: detiene la UI y muestra mensaje.
6. El usuario puede alternar modo pantalla completa; la UI debe incluir un botón “Salir de pantalla completa” y recordatorio de Esc/F11.
7. La biblioteca consulta `GET /transcripts` y muestra chips de estado (`queued`, `started`, `completed`, `failed`). Al seleccionar un elemento, invoca `GET /transcripts/{id}`.
8. Acciones adicionales: descarga `GET /transcripts/{id}/download?format=txt|srt` y exportación `POST /transcripts/{id}/export`.

## 2. API FastAPI

1. `POST /auth/signup` y `POST /auth/token` gestionan usuarios JWT (véase `app/auth.py`). Swagger debe exponer esquema Bearer.
2. `POST /transcribe` valida `multipart/form-data`, sube el audio a S3/MinIO (o disco) y encola el job con metadatos iniciales (`status=queued`).
3. `GET /transcribe/{job_id}` devuelve un `EventSourceResponse` que:
   - Lee metadatos del job (Redis/RQ o fallback en memoria).
   - Envía heartbeat periódico para mantener viva la conexión.
   - Maneja `ClientDisconnect` para limpiar watchers.
4. `GET /jobs/{job_id}` permite consultar estado actual sin SSE (útil para polling).
5. La biblioteca expone:
   - `GET /transcripts`: lista resumida.
   - `GET /transcripts/{id}`: detalle con segmentos JSON.
   - `GET /transcripts/{id}/download`: genera TXT/MD/SRT según `format`.
   - `POST /transcripts/{id}/export`: registra destino (Notion/Trello/Webhook).
6. Extensiones recomendadas:
   - `PATCH /transcripts/{id}`: actualiza título/notas; cuerpo JSON `{ "title": str | None, "notes": str | None }`.
   - `DELETE /transcripts/{id}`: elimina registros y blobs asociados.
   - `GET /profiles`: devuelve perfiles disponibles (`[{"id": int, "name": str, "description": str}]`).
   - `GET /config`: informa límites (`max_upload_mb`, `sse_enabled`, `storage_backend`, `queue_backend`).
7. `/healthz` responde estado mínimo. Si se publica `/metrics`, debe exponerse siempre o documentarse la condición de activación.

## 3. Worker y cola

1. `taskqueue/tasks.py` define `transcribe_job`, que descarga el audio, invoca `TranscriptionService` y actualiza `job.meta` con tokens/porcentaje.
2. Si Redis/RQ no están disponibles, `taskqueue/fallback.py` habilita cola en memoria. Documentar límites (ej. jobs secuenciales, no persistentes).
3. `TranscriptionService` (`services/transcription.py`) se apoya en `faster-whisper` y emite segmentos con marcas de tiempo.
4. Al finalizar, se persisten en BD (`models/transcript.py`) los campos `status`, `duration_seconds`, `segments`, `transcript_key`.

## 4. Almacenamiento y base de datos

1. `storage/s3.py` abstrae MinIO/S3 y fallback local. Debe crear buckets/carpetas al iniciar (`ensure_buckets`).
2. En modo local, se guarda en `storage/local/<user_id>/...`. Documenta tareas de limpieza y cuota.
3. En modo stack, usar MinIO (`docker-compose.yml`) con credenciales configuradas. Considera generar URLs firmadas para descargas externas.
4. BD:
   - Local: SQLite (`grabadora.db`) automática si no se configura `GRABADORA_DATABASE_URL`.
   - Stack: PostgreSQL con migraciones (`alembic upgrade head`).
5. Persistencia verificada mediante pruebas: reiniciar backend no debe borrar transcripciones existentes.

## 5. Exportaciones

1. Generador de TXT/MD/SRT reside en `app/main.py` (`_segments_to_srt` y transformaciones).
2. Exponer siempre encabezados `Content-Disposition` y `Content-Type` correctos.
3. Documentar cómo integrar exportaciones externas (Notion/Trello) cuando se implemente cola real.

## 6. Observabilidad

1. Contadores y gauges Prometheus (`API_ERRORS`, `QUEUE_LENGTH`) se incrementan en los handlers.
2. Decidir si `Instrumentator` se monta en local. Si no, retirar `include_in_schema` de `/metrics` para evitar 404.
3. Logs estructurados (`structlog`) recomendados para correlacionar SSE con jobs.
4. Añadir métricas de heartbeat SSE y latencia de subida en futuras iteraciones.

## 7. Resiliencia y pruebas

1. Simular pérdida de conexión SSE reiniciando backend y asegurarse de que la SPA reintenta con backoff.<br>
2. Probar archivos grandes para garantizar manejo de `413 Payload Too Large` con mensajes claros.
3. Confirmar que `doctor.py` detecta Node/npm ausente y Python incorrecto.
4. Automatizar pruebas contractuales (e2e o integración) que cubran:
   - Alta de usuario → token → subida → SSE → biblioteca → descarga.
   - Eliminación (`DELETE /transcripts/{id}`) cuando se implemente.

Este documento debe actualizarse cuando cambie el flujo o se añadan servicios externos.
