# Informe de diagnóstico y corrección

Este documento resume el estado del proyecto tras la revisión técnica, las correcciones aplicadas y los pasos que garantizan una instalación limpia tanto en entornos locales como en despliegues con Docker.

## Qué estaba roto

- Las dependencias declaradas en `requirements/base.txt` y `pyproject.toml` incluían librerías no utilizadas (pandas, numpy, langdetect, python-jose, passlib, httpx), lo que generaba instalaciones innecesariamente pesadas y discrepancias con el código real.
- El script `doctor.py` validaba la presencia de módulos de ML obligatorios incluso en modo local, provocando falsos negativos cuando solo se instalaban los requisitos básicos.
- La configuración de CORS reconstruía manualmente la pila de middlewares de FastAPI, impidiendo que Prometheus pudiera instrumentar la aplicación durante el arranque (`Cannot add middleware after an application has started`).
- La imagen de Docker intentaba instalar WhisperX dentro de la capa base, lo que disparaba la compilación de PyAV y fallaba en entornos sin toolchain completo.
- `doctor.py` evaluaba el modo de ejecución antes de normalizarlo, por lo que en algunos escenarios lanzaba excepciones y marcaba como críticas dependencias opcionales.
- La documentación mezclaba comandos con el alias `py`, instrucciones obsoletas y no ofrecía un diagnóstico claro de fallback para Redis, MinIO o el worker.

## Qué se corrigió

- Se sincronizaron `pyproject.toml` y `requirements/base.txt` con las dependencias realmente usadas, eliminando librerías superfluas y añadiendo `structlog`. Las dependencias de ML se movieron a un grupo opcional (`requirements/ml.txt`) y WhisperX quedó documentado como instalación manual con wheel binario de PyAV.
- `doctor.py` ahora exige Python 3.11, normaliza el modo antes de comprobar dependencias, diferencia entre requisitos obligatorios y opcionales (advertencias para ML en modo local) e instala solo los paquetes necesarios cuando se usa `--install-missing`.
- La configuración CORS dejó de mutar `app.user_middleware`, por lo que Prometheus puede instrumentar la aplicación antes de que FastAPI construya la pila. Con ello desaparece el error de middleware en caliente.
- El Dockerfile exporta `PIP_PREFER_BINARY`, evita instalar la pila ML en la imagen base y usa `pip --prefer-binary` para Poetry y Cython, impidiendo que PyAV se compile en builds estándar.
- `ejecutar.md` y `README.md` se actualizaron para usar siempre el comando `python`, documentar el fallback de Redis/S3, explicar la instalación opcional de WhisperX y detallar el flujo de diagnóstico, incluida la recomendación de exportar `PIP_PREFER_BINARY=1` antes de instalar la pila de ML para evitar compilaciones de PyAV.
- `Feria.md` se reescribió con este informe y referencias claras a los pasos de instalación.

## Pasos necesarios para una instalación limpia

1. Clona el repositorio y sitúate en la raíz del proyecto.
2. Crea un entorno virtual con Python 3.11 (`python -m venv .venv`) y actívalo.
3. Instala las dependencias base mediante `pip install -r requirements/base.txt`. Solo instala `requirements/ml.txt` si necesitas transcripción real con GPU/CPU avanzada.
4. Copia `.env.example` a `.env.local`, revisa el secreto JWT y ajusta `GRABADORA_DATABASE_URL` si vas a usar PostgreSQL. Define `GRABADORA_ENV_FILE=.env.local` si quieres que ejecutar.py cargue ese archivo automáticamente.
5. Ejecuta `python doctor.py --mode local --install-missing --fix-frontend` para validar Python, Node, FFmpeg, puertos libres y la presencia de dependencias opcionales.
6. Arranca el backend con `python ejecutar.py` y levanta el frontend con `npm install` seguido de `npm run dev` dentro de `frontend`.
7. Si necesitas un worker real, inicia Redis (por ejemplo con `docker compose up redis`) y lanza `rq worker transcription --url redis://localhost:6379/0`. Sin Redis se utiliza la cola en memoria.
8. Para la pila completa utiliza `docker compose up --build` (añade `--profile queue` si quieres un worker dedicado). Prometheus y Grafana quedan disponibles en los puertos 9090 y 3000 respectivamente.
9. Comprueba la demo rápida ejecutando `python scripts/seed_dev.py`, autenticándote en `/docs`, subiendo un audio y verificando que la transcripción se almacena correctamente aunque MinIO no esté disponible (fallback a disco local).

## Referencias

- `ejecutar.md`: pasos detallados sin bloques de código para Windows y Linux/WSL.
- `README.md`: visión general del proyecto, despliegue con Docker y recomendaciones de pruebas manuales.
- `doctor.py`: asistente de validación de entorno con banderas `--mode`, `--install-missing` y `--fix-frontend`.

Actualiza este informe cada vez que se modifique la cadena de dependencias o el procedimiento de despliegue.
