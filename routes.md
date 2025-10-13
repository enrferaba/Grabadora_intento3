# Mapa de rutas Grabadora

| Vista frontend | Path frontend | Endpoint backend | Método | Content-Type esperado | Estado | Observaciones |
|----------------|---------------|------------------|--------|-----------------------|--------|---------------|
| Inicio | `/` | Sirve `frontend/dist/index.html` | GET | `text/html` | OK | Debe cargarse siempre; fallback para rutas internas. |
| Transcribir | `/transcribir` | `POST /transcribe` (creación de job) | POST | `multipart/form-data` | Cambiar | La SPA debe manejar la ruta en cliente; al hacer submit enviar multipart con `file`. Evitar navegar a `/transcribe` como ruta HTML. |
| Progreso SSE | (uso interno) | `GET /transcribe/{job_id}` | GET | `text/event-stream` | OK | Debe incluir heartbeat y manejar reconexión. |
| Estado puntual | (uso interno) | `GET /jobs/{job_id}` | GET | `application/json` | OK | Útil para polling/reintentos. |
| Biblioteca | `/biblioteca` | `GET /transcripts` | GET | `application/json` | OK | SPA debe pedir datos tras cargar `index.html`. |
| Detalle transcript | `/biblioteca/:id` | `GET /transcripts/{id}` | GET | `application/json` | OK | Proteger con JWT. |
| Descarga TXT | Botón en tarjeta | `GET /transcripts/{id}/download?format=txt` | GET | `text/plain` con `Content-Disposition` | OK | SPA debe abrir en nueva pestaña o forzar descarga. |
| Descarga SRT | Botón en tarjeta | `GET /transcripts/{id}/download?format=srt` | GET | `application/x-subrip` | OK | Validar contenido generado en backend. |
| Exportar | Acción avanzada | `POST /transcripts/{id}/export` | POST | `application/json` | OK | Cuerpo `{ "destination": "notion|trello|webhook", "format": "txt|md|srt" }`. |
| Perfiles (pendiente) | Ajustes | `GET /profiles` | GET | `application/json` | Añadir | Responder lista de perfiles para poblar selector en SPA. |
| Configuración (pendiente) | Ajustes | `GET /config` | GET | `application/json` | Añadir | Devolver límites (MB, SSE, storage). |
| Editar transcript (pendiente) | Modal biblioteca | `PATCH /transcripts/{id}` | PATCH | `application/json` | Añadir | Actualizar título/notas. Responder 200 con entidad actualizada. |
| Borrar transcript (pendiente) | Acción destructiva | `DELETE /transcripts/{id}` | DELETE | `application/json` | Añadir | Eliminar registro y blobs. Responder 204 sin contenido. |
| Salud | (oculta) | `GET /healthz` | GET | `application/json` | OK | Debe incluir comprobaciones básicas. |
| Métricas | (Prometheus) | `GET /metrics` | GET | `text/plain` | Cambiar | Decidir si se expone siempre; si no, eliminar del build y docs. |
| Auth signup | `/registro` (SPA) | `POST /auth/signup` | POST | `application/json` | OK | Responde 201; manejar errores 400. |
| Auth login | `/login` (SPA) | `POST /auth/token` | POST | `application/x-www-form-urlencoded` | OK | Requiere `username/password`. |

## Notas de implementación
- Toda ruta frontend debe resolverse en el cliente; FastAPI sólo debe devolver `index.html` salvo que el path comience por endpoints API reales.
- Añadir pruebas end-to-end que confirmen que refrescar `/transcribir` devuelve la SPA y que `POST /transcribe` con JSON devuelve 415/422 controlado.
- Documentar en Swagger los `Content-Type` esperados y códigos de respuesta (200/201/204/400/401/404/413/429/500).
