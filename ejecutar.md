# ejecutar.py y guías de arranque

Este documento explica cómo verificar el entorno, arrancar la plataforma y resolver los fallos más habituales en Windows PowerShell y en shells POSIX.

## 1. Preparar el entorno

### 1.1 Requisitos previos
- Python 3.12 instalado y accesible como `python`/`python3` (Linux/macOS) o `py -3.12` (Windows).
- Node.js >= 18 y `npm` disponibles en PATH.
- FFmpeg instalado (`ffmpeg -version`).
- (Opcional) Docker + Docker Compose v2 para levantar la pila completa.

### 1.2 Crear y activar el entorno virtual

| Sistema | Comando |
|---------|---------|
| Linux/macOS | `python3.12 -m venv .venv && source .venv/bin/activate` |
| Windows PowerShell | `py -3.12 -m venv .venv; .\.venv\Scripts\Activate.ps1` |

> Si PowerShell bloquea la activación, ejecuta `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` con permisos de administrador.

### 1.3 Instalar dependencias

```bash
pip install -r requirements.txt
# o con Poetry
poetry install
```

Luego instala el frontend si vas a recompilar la SPA:

```bash
cd frontend
npm install
cd ..
```

## 2. Uso de `doctor.py`

`python doctor.py` realiza comprobaciones previas al arranque.

Parámetros útiles:
- `--install-missing`: intenta instalar paquetes de Python ausentes dentro del entorno activo.
- `--fix-frontend`: ejecuta `npm install` y verifica que exista `frontend/dist/`.

Salida esperada (resumida):

```
✅ Intérprete de Python compatible
✅ FFmpeg disponible
✅ Dependencias de frontend instaladas
✅ Build de frontend generado
```

Si aparece ❌, sigue la sugerencia mostrada. Casos comunes:
- **Python 3.9 detectado**: revisa `where python`/`Get-Command python` y ajusta la ruta al `.venv`.
- **npm no encontrado (Windows)**: reinstala Node.js y vuelve a abrir PowerShell.
- **Redis/DB inaccesibles**: el doctor lo marca informativo; puedes continuar si usarás los fallbacks en memoria/SQLite.

## 3. Ejecutar la API y la SPA

### 3.1 Modo local (sin Docker)

```bash
python ejecutar.py --host 0.0.0.0 --port 8000
```

Bandera útiles:
- `--mode local|stack`: fuerza el modo de entorno (afecta uso de Redis/S3 vs. fallbacks).
- `--skip-checks`: omite `doctor.py` cuando ya validaste el entorno.

La salida debe mostrar URLs como:
```
SPA disponible en http://127.0.0.1:8000/
Docs API en     http://127.0.0.1:8000/docs
Healthcheck en  http://127.0.0.1:8000/healthz
```

> Si `/docs` carga pero `POST /transcribe` devuelve 405, revisa que la solicitud sea `multipart/form-data` y que `python-multipart` esté instalado.

### 3.2 Levantar el worker

En otra terminal, con el mismo entorno activo:

```bash
rq worker transcription --url $GRABADORA_REDIS_URL
```

Si no tienes Redis, activa el backend en memoria estableciendo `GRABADORA_QUEUE_BACKEND=memory` o dejando que el código lo seleccione automáticamente (verifica logs: “Using in-memory queue backend”).

### 3.3 Docker Compose

```bash
docker compose up --build
```

Incluye API, worker, Redis, PostgreSQL, MinIO, Prometheus y Grafana. Comprueba los healthchecks con `docker compose ps`.

## 4. Pruebas rápidas

1. Abre `http://localhost:8000/` y verifica que la SPA cargue.
2. Desde `/docs`, crea un usuario (`POST /auth/signup`), inicia sesión (`POST /auth/token`) y copia el token.
3. Configura el token en Swagger (botón “Authorize” → `Bearer <token>`).
4. Lanza `POST /transcribe` subiendo un WAV/MP3 pequeño. Debe responder `job_id`.
5. Abre `GET /transcribe/{job_id}` desde la SPA o con `curl -N` para confirmar eventos SSE.
6. Comprueba `GET /transcripts` y descarga `GET /transcripts/{id}/download?format=srt`.

## 5. Solución de problemas frecuentes

| Síntoma | Causa probable | Acción sugerida |
|---------|----------------|-----------------|
| `405 Method Not Allowed` en `POST /transcribe` | Solicitud enviada como JSON o falta `python-multipart`. | Ajusta el cliente a `multipart/form-data` y reinstala `python-multipart`. |
| `404 /transcribir` al refrescar la página | Falta fallback SPA en FastAPI. | Revisa que FastAPI devuelva `frontend/dist/index.html` para rutas desconocidas. |
| `typing-extensions` conflicto con Pydantic 2.12 | Versión 4.11 instalada. | Ejecuta `pip install typing-extensions>=4.14.1`. |
| `Falling back to local disk storage...` | MinIO/S3 no disponible. | Documenta el modo local en README y confirma permisos de escritura. |
| Pantalla completa sin salida visible | UI sin botón de salida. | Añadir botón “Salir de pantalla completa” y atajos en la SPA. |
| `python doctor.py` usa Python 3.9 de Microsoft Store | Alias global invade el PATH. | Deshabilita App Installer (`winget settings`) y usa `.venv\Scripts\python.exe`. |

Mantén este archivo actualizado cuando cambien parámetros o banderas de `ejecutar.py`.
