# Registro de errores y acciones recomendadas

| Nº | Archivo/Componente | Síntoma observado | Causa raíz | Impacto | Acción correctiva |
|----|--------------------|-------------------|------------|---------|-------------------|
| 1 | SPA (routing) | 404 al navegar a `/transcribir` o `/transcripts` | El servidor intenta resolver rutas SPA como endpoints reales; no hay fallback a `index.html`. | Usuarios quedan bloqueados y Swagger reporta 404/405 inesperados. | Implementado fallback controlado en FastAPI que devuelve `index.html` sólo para rutas no API (prefijos excluidos) y guía actualizada en README/routes.md. |
| 2 | `POST /transcribe` | 405 Method Not Allowed / 422 | Solicitudes enviadas como JSON o falta de `python-multipart`. | La subida de audio falla y no se crean jobs. | Forzar `multipart/form-data` en la SPA, validar con `curl -F`, instalar `python-multipart` (>=0.0.20) y añadir ejemplos en `/docs`. |
| 3 | Métricas | `/metrics` devuelve 404 en local | `Instrumentator` no se monta cuando faltan dependencias o configuración. | Prometheus falla y dashboards quedan vacíos. | Instrumentación ahora se monta sólo si la librería está presente; el backend devuelve 404 explícito y `/config` expone `metrics_enabled` para reflejarlo en la UI/doc. |
| 4 | UX fullscreen | Pantalla completa sin botón de salida | UI carece de control explícito y usuarios quedan atrapados. | Mala experiencia; deben conocer Esc/F11. | Añadir botón “Salir de pantalla completa” y mensajes guía. |
| 5 | Dependencias | Conflicto `typing-extensions==4.11.0` + `pydantic>=2.12` | Versionado mixto en entornos locales. | ImportError al arrancar API. | Documentar versión mínima (4.14.1) y fijarla en requirements/poetry. |
| 6 | Backend runtime | Uvicorn recarga con Python 3.9 (Microsoft Store) | PATH apunta a alias App Installer. | Falla import `datetime.UTC`. | Documentar cómo fijar Python 3.12, usar `.venv\Scripts\python.exe` y deshabilitar alias. |
| 7 | Storage | Log “Falling back to local disk storage because S3 endpoint is unavailable.” | MinIO/S3 no configurado en local. | Inquietud en usuarios; posible pérdida si no se documenta limpieza. | Explicar fallback local en README y planificar limpieza periódica. |
| 8 | Frontend build | npm PATH no detectado en Windows | Variables de entorno incorrectas. | `doctor.py` falla y no se genera `frontend/dist`. | Añadir solución en ejecutar.md (reinstalar Node, reabrir terminal). |

## Verificación tras aplicar correcciones
1. Ejecutar smoke test descrito en README (subida → SSE → Biblioteca → descarga).
2. Validar rutas SPA: refrescar `/transcribir` y `/biblioteca` sin 404.
3. Confirmar que `POST /transcribe` recibe multipart y devuelve `job_id` usando Swagger con token Bearer.
4. Medir `/metrics` (o retirar referencias) y documentar resultado en README.
5. Ejecutar `python doctor.py` para confirmar que no quedan ❌.

Actualiza esta tabla con nuevos incidentes y resoluciones.
