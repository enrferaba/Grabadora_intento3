# Guía de feria: puesta en marcha rápida

Esta guía resume los pasos de validación y arranque que usamos durante las demos de feria. Está pensada para un entorno local con SQLite y almacenamiento en disco, pero también señala qué cambiar para pasar a la pila completa (Postgres + Redis + MinIO).

## 1. Preparar el entorno

1. Crea un entorno virtual de Python 3.11+ y activa el intérprete.
2. Instala dependencias base y de ML cuando quieras transcribir de verdad:
   ```bash
   pip install -r requirements/base.txt
   pip install -r requirements/ml.txt
   ```
3. Instala las dependencias del frontend:
   ```bash
   cd frontend
   npm install
   cd -
   ```
4. Copia `.env.example` a `.env` (UTF-8 sin BOM) y revisa al menos `GRABADORA_JWT_SECRET_KEY` y los buckets de S3. Para demos sin MinIO no tienes que tocar los valores: el backend caerá automáticamente a almacenamiento local.

## 2. Inicializar SQLite sin Alembic

1. Asegúrate de que el proyecto está en el `PYTHONPATH` (equivalente a `export PYTHONPATH=$(pwd)` en Linux/macOS o `setx PYTHONPATH %CD%` en PowerShell).
2. Ejecuta el bloque de inicialización para crear la base de datos y las tablas:
   ```bash
   python - <<'PY'
   from app.database import Base, get_engine
   engine = get_engine()
   Base.metadata.create_all(bind=engine)
   print("SQLite: tablas creadas OK")
   PY
   ```
3. Si prefieres usar Alembic, ajusta `GRABADORA_DATABASE_URL` (o `alembic.ini`) al URL de SQLite y lanza `alembic upgrade head` con el `PYTHONPATH` configurado.

## 3. Arrancar la plataforma

1. Usa el asistente para modo local (cola en memoria + SQLite):
   ```bash
   python ejecutar.py --mode local
   ```
   El script ejecutará el `doctor`, configurará las variables de entorno y asegurará que SQLite tenga las tablas listas.
2. En otra terminal, levanta el frontend:
   ```bash
   cd frontend
   npm run dev
   ```
3. Abre `http://localhost:8000/docs` para probar la API o `http://localhost:5173` para la SPA.

## 4. Registrar un usuario y autenticar desde Swagger

1. `POST /auth/signup` con cuerpo JSON:
   ```json
   {"email": "admin@local.com", "password": "admin123"}
   ```
2. `POST /auth/token` con `grant_type=password`, `username=admin@local.com` y `password=admin123` (form-data o x-www-form-urlencoded).
3. Pulsa el candado "Authorize", pega `Bearer <access_token>` y confirma. A partir de ahí el resto de endpoints autenticados funcionarán.

El frontend utiliza el header `Authorization: Bearer <token>` en todas las llamadas cuando guardas el token en la sesión.

> Truco rápido: `python scripts/seed_dev.py` crea automáticamente el usuario `admin@local.com / admin123` y evita repetir estos pasos tras cada reinicio de la base de datos.

## 5. Alternativa stack completa

Cuando quieras usar Postgres/Redis/MinIO (por ejemplo con Docker Compose):

1. Ajusta `.env` con las credenciales reales o las del `docker-compose.yml`.
2. Lanza `docker compose up -d` para tener `api`, `frontend`, `minio`, `redis` y `db`.
3. Ejecuta `alembic upgrade head` contra Postgres (`GRABADORA_DATABASE_URL=postgresql+psycopg2://...`).
4. Arranca un worker: `python -m taskqueue.worker`.

## 6. Solución de problemas frecuentes

- **Error `Could not import module "main"`**: asegura que arrancas con `uvicorn app.main:app` o usa `python ejecutar.py`.
- **CORS desde la SPA**: define `GRABADORA_FRONTEND_ORIGIN=http://localhost:5173` en `.env` (el modo local lo hace por ti).
- **MinIO no responde**: el cliente conmutará a disco local y mostrará una advertencia en los logs.
- **SQLite vacío**: vuelve a ejecutar el bloque de inicialización del paso 2 o borra `grabadora.db` para recrearlo.

## 7. Comandos rápidos (copiar/pegar)

```bash
# Crear .env base
cat <<'ENV' > .env
GRABADORA_JWT_SECRET_KEY=pon-aqui-un-secreto-fuerte
GRABADORA_FRONTEND_ORIGIN=http://localhost:5173
ENV

# Inicializar SQLite
PYTHONPATH=$(pwd) python - <<'PY'
from app.database import Base, get_engine
engine = get_engine()
Base.metadata.create_all(bind=engine)
print("SQLite: tablas creadas OK")
PY

# Arrancar todo en modo local
python ejecutar.py --mode local
```

¡Lista para transcribir y demo en minutos! Si algo falla, ejecuta `python doctor.py` para revisar dependencias y puertos.
