# Mapa de rutas Grabadora

| Vista frontend | Path frontend | Endpoint backend | Método | Content-Type esperado | Estado | Observaciones |
|----------------|---------------|------------------|--------|-----------------------|--------|---------------|
| Inicio | `/` | Sirve `frontend/dist/index.html` | GET | `text/html` | OK | Debe cargarse siempre; fallback para rutas internas. |
| Transcribir | `/transcribir` | `POST /transcribe` (creación de job) | POST | `multipart/form-data` | OK | Ruta SPA resuelta en cliente; envío multipart directo a la API al confirmar el formulario. |
| Progreso SSE | (uso interno) | `GET /transcribe/{job_id}` | GET | `text/event-stream` | OK | Debe incluir heartbeat y manejar reconexión. |
| Estado puntual | (uso interno) | `GET /jobs/{job_id}` | GET | `application/json` | OK | Útil para polling/reintentos. |
| Biblioteca | `/biblioteca` | `GET /transcripts` | GET | `application/json` | OK | SPA debe pedir datos tras cargar `index.html`. |
| Detalle transcript | `/biblioteca/:id` | `GET /transcripts/{id}` | GET | `application/json` | OK | Proteger con JWT. |
| Descarga TXT | Botón en tarjeta | `GET /transcripts/{id}/download?format=txt` | GET | `text/plain` con `Content-Disposition` | OK | SPA debe abrir en nueva pestaña o forzar descarga. |
| Descarga SRT | Botón en tarjeta | `GET /transcripts/{id}/download?format=srt` | GET | `application/x-subrip` | OK | Validar contenido generado en backend. |
| Exportar | Acción avanzada | `POST /transcripts/{id}/export` | POST | `application/json` | OK | Cuerpo `{ "destination": "notion|trello|webhook", "format": "txt|md|srt" }`. |
| Perfiles | Ajustes | `GET /profiles` | GET | `application/json` | OK | Devuelve perfiles de calidad y del usuario; pobla selector dinámicamente. |
| Configuración | Ajustes | `GET /config` | GET | `application/json` | OK | Expone límites (MB, SSE, storage) y estado de métricas. |
| Editar transcript | Modal biblioteca | `PATCH /transcripts/{id}` | PATCH | `application/json` | OK | Actualiza título/notas/etiquetas y devuelve el recurso completo. |
| Borrar transcript | Acción destructiva | `DELETE /transcripts/{id}` | DELETE | `application/json` | OK | Elimina registro y blobs asociados; responde 204. |
| Salud | (oculta) | `GET /healthz` | GET | `application/json` | OK | Debe incluir comprobaciones básicas. |
| Métricas | (Prometheus) | `GET /metrics` | GET | `text/plain` | Condicional | Sólo disponible si `prometheus_fastapi_instrumentator` está instalado; en caso contrario devolverá 404. |
| Auth signup | `/registro` (SPA) | `POST /auth/signup` | POST | `application/json` | OK | Responde 201; manejar errores 400. |
| Auth login | `/login` (SPA) | `POST /auth/token` | POST | `application/x-www-form-urlencoded` | OK | Requiere `username/password`. |

## Notas de implementación
- Toda ruta frontend debe resolverse en el cliente; FastAPI sólo debe devolver `index.html` salvo que el path comience por endpoints API reales.
- Añadir pruebas end-to-end que confirmen que refrescar `/transcribir` devuelve la SPA y que `POST /transcribe` con JSON devuelve 415/422 controlado.
- Documentar en Swagger los `Content-Type` esperados y códigos de respuesta (200/201/204/400/401/404/413/429/500).
