# Guía rápida de ejecución

Elige el bloque que corresponda a tu sistema operativo. Todos los comandos asumen que estás en la raíz del repositorio.

## Windows (PowerShell)

1. **Preparar Python y dependencias**
   ```powershell
   py -3.11 -m venv .venv
   .\.venv\Scripts\Activate.ps1
   pip install -r requirements/base.txt
   # Para transcribir con modelos grandes usa también (requiere CUDA o CPU potente):
   # pip install -r requirements/ml.txt
   ```

   > Si quieres la pila completa (Redis, MinIO, PostgreSQL) usa Docker más abajo; no necesitas instalar `ml.txt` para probar la API básica.

2. **Frontend**
   ```powershell
   cd frontend
   npm install
   cd ..
   ```

3. **Variables de entorno**
   Copia `.env.example` a `.env.local` y ajusta lo necesario (por defecto usa SQLite y cola en memoria). El lanzador rellenará un secreto JWT si encuentra el placeholder.

4. **Arrancar en modo desarrollador**
   ```powershell
   python ejecutar.py
   ```
   Este comando ejecuta el doctor, crea la base SQLite y lanza `uvicorn` con autoreload. La SPA queda disponible en `http://localhost:5173` si levantas Vite en otra consola:
   ```powershell
   cd frontend
   npm run dev
   ```

5. **Cola de trabajos (opcional)**
   Solo si usas Redis: 
   ```powershell
   $env:GRABADORA_REDIS_URL="redis://localhost:6379/0"
   rq worker transcription --url $env:GRABADORA_REDIS_URL
   ```
   Si no defines Redis, la aplicación usa una cola en memoria y no necesitas worker.

6. **Docker en Windows**
   Para evitar compilar dependencias como PyAV en Windows, es recomendable usar Docker (requiere WSL2):
   ```powershell
   docker compose up --build
   ```
   El compose levanta API, frontend, Redis, PostgreSQL y MinIO. El acceso sigue siendo `http://localhost:8000` (API) y `http://localhost:5173` (frontend).

## Linux / WSL / macOS (bash/zsh)

1. **Entorno virtual e instalación**
   ```bash
   python3.11 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements/base.txt
   # Para transcribir con modelos completos:
   # pip install -r requirements/ml.txt
   ```

2. **Frontend**
   ```bash
   cd frontend
   npm install
   cd ..
   ```

3. **Variables de entorno**
   ```bash
   cp .env.example .env.local  # edita si necesitas cambiar rutas o credenciales
   ```

4. **Arranque local**
   ```bash
   python ejecutar.py
   # En otra terminal (opcional) para la SPA:
   cd frontend && npm run dev -- --host 0.0.0.0 --port 5173
   ```

5. **Worker opcional (Redis)**
   ```bash
   export GRABADORA_REDIS_URL=redis://localhost:6379/0
   rq worker transcription --url "$GRABADORA_REDIS_URL"
   ```

6. **Docker Compose**
   ```bash
   docker compose up --build
   ```
   Usa `docker compose --profile queue up --build` si quieres añadir el worker RQ como contenedor adicional.

## Flujo de prueba

1. Abre `http://localhost:8000/docs`.
2. Crea un usuario (`POST /auth/signup`).
3. Obtén un token (`POST /auth/token`) y pulsa **Authorize** → `Bearer <token>`.
4. Desde la SPA (o Swagger) sube un audio y verifica que llega la transcripción. Si S3/MinIO no está disponible, el backend guardará los archivos en `./data/`.
5. Ejecuta `python scripts/seed_dev.py` para crear un usuario demo rápidamente si lo prefieres.

## Problemas habituales

- **`rq worker` dice que falta `--url`**: en PowerShell usa `$env:VARIABLE`, no `$VARIABLE`.
- **Error compilando PyAV en Windows**: usa Docker o WSL; la imagen oficial ya incluye FFmpeg y las cabeceras necesarias.
- **`docker compose up` pide `.env`**: el repositorio incluye un `.env` mínimo que apunta a `.env.example`. Crea `.env.local` para credenciales reales y exporta `GRABADORA_ENV_FILE=.env.local` si quieres que Compose lo cargue.

Mantén este archivo a mano y actualízalo cuando cambie el proceso de arranque.
