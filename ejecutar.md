# Guía rápida de ejecución

Este documento explica el flujo recomendado para preparar el entorno, lanzar los servicios y solucionar los problemas más habituales en Windows y en entornos tipo Unix (Linux, WSL o macOS). No incluye fragmentos de código; todos los comandos se mencionan en texto.

## Requisitos previos

- Python 3.11 instalado desde python.org o mediante un gestor equivalente. Comprueba la versión con la orden "python --version".
- Node.js 20 LTS o superior (incluye npm). Valida la instalación con "node --version".
- Git para clonar el repositorio.
- Docker Desktop con soporte para Docker Compose si deseas levantar la pila completa (PostgreSQL, Redis, MinIO, Prometheus, Grafana).
- FFmpeg disponible en la variable PATH. Ejecuta "ffmpeg -version" para confirmarlo.

Si el acceso a Internet está restringido, descarga las dependencias necesarias en un equipo con conexión y expórtalas mediante un repositorio interno.

## Pasos en Windows (PowerShell)

1. Verifica que la orden "python" apunta al intérprete correcto y muestra una versión 3.11.x. Si se abre la Microsoft Store, desactiva los alias de ejecución desde Configuración → Aplicaciones → Alias de ejecución de la aplicación.
2. Crea un entorno virtual con "python -m venv .venv" y actívalo mediante "\.\.venv\Scripts\Activate.ps1".
3. Instala las dependencias base con "python -m pip install -r requirements/base.txt". Para habilitar la transcripción acelerada define temporalmente la variable "PIP_PREFER_BINARY" (`$env:PIP_PREFER_BINARY = '1'`) y a continuación ejecuta "python -m pip install -r requirements/ml.txt"; así fuerzas a pip a descargar los wheels precompilados y evitas que PyAV intente compilarse.
4. Copia ".env.example" a ".env.local" y revisa las variables mínimas: `GRABADORA_JWT_SECRET_KEY`, `GRABADORA_DATABASE_URL` (se usa SQLite por defecto) y los buckets de S3. No es necesario definir claves reales si solo trabajarás en local; el backend caerá en almacenamiento en disco automáticamente cuando MinIO no esté disponible.
5. Lanza "python doctor.py --mode local --install-missing --fix-frontend". El asistente mostrará advertencias (no errores) si faltan dependencias opcionales de ML.
6. Inicia el backend con "python ejecutar.py". El script genera un secreto JWT cuando detecta uno de ejemplo, prepara la base SQLite y expone la API en http://localhost:8000/.
7. En otra consola ve a la carpeta `frontend` y ejecuta "npm install" seguido de "npm run dev" para servir la SPA en http://localhost:5173/. Si deseas un build estático lanza "npm run build" y el doctor marcará la casilla de distribución como satisfecha.
8. Si necesitas un worker real, asegúrate de que Redis escucha en `redis://localhost:6379/0` (por ejemplo con `docker run redis:7` o con Docker Compose) y luego ejecuta "rq worker transcription --url redis://localhost:6379/0". Sin Redis la aplicación usa una cola en memoria y no se requiere worker.
9. Para reproducir la pila completa ejecuta "docker compose up --build" desde la raíz del proyecto. Este comando crea la imagen del backend sin instalar las dependencias de ML y levanta contenedores para API, frontend, Redis, PostgreSQL y MinIO. Añade el perfil `queue` si quieres un worker separado: "docker compose --profile queue up --build".

## Pasos en Linux, WSL o macOS

1. Comprueba que "python3 --version" devuelve 3.11.x. Crea y activa el entorno virtual con "python3.11 -m venv .venv" seguido de "source .venv/bin/activate".
2. Instala los requisitos base mediante "pip install -r requirements/base.txt" y, si necesitas transcribir con GPU o CPU de alto rendimiento, exporta `PIP_PREFER_BINARY=1` antes de ejecutar "pip install -r requirements/ml.txt" para priorizar wheels. Para WhisperX instala manualmente los binarios de PyAV con "pip install --prefer-binary av==11.0.0 whisperx==3.1.2" después de los requisitos ML.
3. Duplica ".env.example" en ".env.local" o exporta `GRABADORA_ENV_FILE=.env.local` para que el backend cargue un archivo alternativo. Ajusta las rutas de almacenamiento si prefieres guardar los audios fuera del repositorio.
4. Ejecuta "python doctor.py --mode local --install-missing --fix-frontend" para validar Python, Node, puertos disponibles, FFmpeg y la presencia del build de frontend. En modo "stack" el doctor exige que Redis, la base de datos y S3 respondan correctamente.
5. Arranca la API con "python ejecutar.py". El comando muestra los endpoints disponibles y confirma si la cola usa memoria o Redis. Con el entorno activado puedes invocar directamente "uvicorn app.main:app --reload" si prefieres controlar las opciones de Uvicorn manualmente.
6. Sirve la SPA con "npm install" y "npm run dev -- --host 0.0.0.0 --port 5173". Para exponerla fuera de localhost añade las direcciones necesarias a `GRABADORA_FRONTEND_ORIGIN` o `GRABADORA_FRONTEND_ORIGIN_REGEX`.
7. Ejecuta "rq worker transcription --url redis://localhost:6379/0" solo cuando Redis esté levantado. Al omitir esa variable la aplicación conserva la cola en memoria y evita errores de conexión.
8. Usa "docker compose up --build" para levantar la pila completa. El archivo de Compose exporta los servicios en los puertos 8000 (API), 5173 (SPA), 5432 (PostgreSQL), 6379 (Redis), 9000/9001 (MinIO) y 9090/3000 para Prometheus y Grafana. Asegúrate de mapear los puertos libres o modifica el archivo si chocan con otro servicio.

## Diagnóstico de incidencias habituales

- Mensaje "py no se reconoce": sustituye cualquier referencia a "py" por "python" y asegúrate de que el intérprete procede de una instalación estándar.
- Error "Unknown option: -3": la sintaxis correcta para crear entornos virtuales es "python -m venv .venv" (sin parámetros de versión). Usa "python3.11" cuando el sistema tenga varias versiones instaladas.
- Redis rechaza la conexión con "Error 10061": el servicio no está en ejecución. Elimina la variable `GRABADORA_REDIS_URL` para usar la cola en memoria o arranca Redis (por ejemplo con Docker) antes de invocar el worker.
- Docker build falla compilando PyAV: la imagen oficial ahora omite los paquetes de ML, por lo que el error solo aparece si instalas WhisperX dentro del contenedor. Define `PIP_PREFER_BINARY=1` y asegúrate de instalar un wheel binario de PyAV (`av==11.0.0` o superior) antes de `pip install whisperx==3.1.2`, o realiza la instalación en la máquina host y monta el entorno listo.
- El doctor muestra advertencias en módulos de ML: son opcionales en modo local. Cambia a `--mode stack` si necesitas que fallen como requisito (por ejemplo en preproducción).
- S3 o MinIO no están disponibles: el almacenamiento conmuta automáticamente a disco local dentro de la carpeta configurada en `GRABADORA_STORAGE_DIR`. Revisa los logs para conocer la ruta exacta y programa limpiezas periódicas si vas a trabajar así durante mucho tiempo.

## Flujo de comprobación rápida

1. Ejecuta "python scripts/seed_dev.py" para crear el usuario `admin@local.com` con contraseña `admin123`.
2. Inicia la API y la SPA según los pasos anteriores.
3. Accede a http://localhost:8000/docs, realiza el login con el usuario anterior y sube un audio corto desde `/transcriptions`.
4. Observa el progreso de la cola. Sin Redis verás los estados "queued", "started" y "completed" actualizados en la vista SSE del frontend.
5. Descarga el texto generado desde la biblioteca o mediante `/transcriptions/{id}/download` para confirmar que el almacenamiento funciona.

Mantén este documento actualizado cuando cambien los procesos de arranque, especialmente si se añaden nuevos servicios o dependencias.
