FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    POETRY_VERSION=2.2.1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_PREFER_BINARY=1

WORKDIR /app

# Dependencias del sistema necesarias para audio, compilación y ffmpeg
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        ffmpeg \
        git \
        libavcodec-dev \
        libavdevice-dev \
        libavfilter-dev \
        libavformat-dev \
        libavutil-dev \
        libpq-dev \
        libsndfile1 \
        libswresample-dev \
        libswscale-dev \
        pkg-config \
    && rm -rf /var/lib/apt/lists/*

# Copiamos solo el archivo de dependencias para cachear instalación
COPY pyproject.toml /app/

# Instalamos Poetry y dependencias base (sin entorno virtual)
RUN pip install --no-cache-dir --prefer-binary "Cython<3" "poetry==${POETRY_VERSION}" \
    && poetry config virtualenvs.create false \
    && poetry install --without dev --no-root

# 🚀 Instalamos PyTorch con soporte CUDA 12.1 (válido para tu RTX 3060 Ti)
RUN pip install --no-cache-dir "torch==2.3.1" --index-url https://download.pytorch.org/whl/cu121


# Luego instalamos faster-whisper (detectará torch CUDA automáticamente)
RUN pip install --no-cache-dir faster-whisper

# Copiamos el resto del código
COPY . /app

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
