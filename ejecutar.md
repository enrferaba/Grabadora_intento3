# ejecutar.py y guías de arranque

Este documento explica cómo verificar el entorno, arrancar la plataforma y resolver los fallos más habituales en Windows PowerShell y en shells POSIX.

## 1. Preparar el entorno

### 1.1 Requisitos previos
- Python 3.11 o superior instalado y accesible como `python`/`python3` (Linux/macOS) o `py -3.11` (Windows).
- Node.js >= 20 LTS y `npm` disponibles en PATH.
- FFmpeg instalado (`ffmpeg -version`).
- (Opcional) Docker + Docker Compose v2 para levantar la pila completa.

### 1.2 Crear y activar el entorno virtual

| Sistema | Comando |
|---------|---------|
| Linux/macOS | `python3.11 -m venv .venv && source .venv/bin/activate` |
| Windows PowerShell | `py -3.11 -m venv .venv; .\.venv\Scripts\Activate.ps1` |

> Si PowerShell bloquea la activación, ejecuta `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` con permisos de administrador.

### 1.3 Instalar dependencias

```bash
pip install -r requirements.txt  # stack completa con modelos
# Si solo quieres probar la API sin dependencias pesadas:
# pip install -r requirements/base.txt
# o con Poetry
poetry install
```

Luego instala el frontend si vas a recompilar la SPA:

```bash
cd frontend
npm install
cd ..
```

> Si dejas `GRABADORA_JWT_SECRET_KEY` con el placeholder en `.env` o `.env.local`, `python ejecutar.py` generará un secreto aleatorio y lo guardará automáticamente para los siguientes arranques.

## 2. Uso de `doctor.py`

`python doctor.py` realiza comprobaciones previas al arranque del stack.

Parámetros útiles:
- `--install-missing`: intenta instalar paquetes de Python ausentes dentro del entorno activo.
- `--fix-frontend`: ejecuta `npm install` en `frontend/` si faltan dependencias.
- `--mode local|stack`: habilita las comprobaciones de Redis/MinIO/DB cuando usas Docker Compose.

Salida esperada (resumida):

```
✅ Intérprete de Python compatible
✅ Node.js >= 20 LTS
✅ FFmpeg disponible
✅ Dependencias de frontend instaladas
✅ Build de frontend generado
✅ nvidia-smi disponible
✅ Puertos disponibles
```

Si aparece ❌, sigue la sugerencia mostrada. Casos comunes:
- **Python 3.9 detectado**: revisa `where python`/`Get-Command python` y ajusta la ruta al `.venv`.
- **npm no encontrado (Windows)**: reinstala Node.js y vuelve a abrir PowerShell.
- **Redis/DB/S3 inaccesibles**: revisa que Docker Compose esté corriendo o cambia a `--mode local` para usar los fallbacks.

## 3. Ejecutar la API y la SPA

### 3.1 Modo local (sin Docker)

1. Activa el entorno virtual (`source .venv/bin/activate`).
2. Arranca la API en modo recarga: `uvicorn app.main:app --reload --host 0.0.0.0 --port 8000`.
3. En otra terminal, levanta la SPA: `cd frontend && npm run dev -- --host 0.0.0.0 --port 5173`.
4. Opcional: usa `python ejecutar.py` si prefieres un comando único que ejecuta `doctor.py` y uvicorn con las banderas adecuadas.

URLs locales:
```
SPA           http://localhost:5173/
Docs API      http://localhost:8000/docs
Healthcheck   http://localhost:8000/healthz
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
# Para añadir el worker en segundo plano:
docker compose --profile queue up --build
```

> Nota: El repositorio trae un `.env` básico que apunta a `.env.example`, así que `docker compose up --build` funciona sin pasos previos. Para credenciales propias crea `.env.local` (git lo ignora), ajústalo y cambia `GRABADORA_ENV_FILE=.env.local` en `.env` o exporta `GRABADORA_ENV_FILE=.env.local` antes de levantar los contenedores.

El perfil por defecto levanta API (8000), frontend en Vite (5173), Redis, PostgreSQL y MinIO. Comprueba los healthchecks con `docker compose ps` y espera a ver `healthy` antes de probar.

## 4. Pruebas rápidas

1. Abre `http://localhost:5173/` y verifica que la SPA cargue (en producción puede servirse desde la API).
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

## 6. Auditoría rápida del repositorio

Ejecuta `python scripts/revisa_repo.py` desde la raíz para generar `RepoAudit.md` con un checklist de `.env`, Docker Compose y migraciones. Repasa las advertencias antes de abrir un PR o desplegar.

Mantén este archivo actualizado cuando cambien parámetros o banderas de `ejecutar.py`.
