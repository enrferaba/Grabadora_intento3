# Grabadora

Grabadora is a streaming transcription platform powered by FastAPI, faster-whisper, and Redis-backed workers. API clients upload audio once, receive a job identifier, and consume a Server-Sent Events (SSE) feed of delta tokens as the GPU worker transcribes in real time.

## Features
- FastAPI service with `/transcribe` SSE endpoint delivering token deltas.
- Redis + RQ queue for GPU workers with Prometheus metrics for queue depth.
- Configurable quantization levels for faster-whisper (float32/16/int8).
- MinIO/S3 storage for uploaded audio and persisted transcripts.
- OAuth2 password flow with JWT access tokens, multi-profile accounts, and usage metering models.
- PostgreSQL database managed by SQLAlchemy and Alembic migrations.
- Structured logging via `structlog` and Prometheus metrics with Grafana dashboards.
- GPU-ready Docker Compose stack: API, worker, Redis, Postgres, MinIO, Prometheus, Grafana.

## Getting Started
1. Install dependencies with Poetry: `poetry install`.
2. Provision the database: `alembic upgrade head`.
3. Launch the stack: `docker compose up --build` (ensure NVIDIA Container Toolkit is installed for GPU access).
4. Create a user via `POST /users`, then obtain a token with `POST /auth/token`.
5. Upload audio using `POST /transcribe` (multipart form with `file` field). Listen to SSE updates at `GET /transcribe/{job_id}`.

Environment variables are documented in `app/config.py` and `docker-compose.yml`. Update S3 credentials and database URLs as needed for production.

## Monitoring
Prometheus scrapes metrics exposed at `/metrics`. Grafana dashboards located under `deploy/grafana/dashboards/` visualize API latency, GPU memory, queue length, and error counts. See `deploy/grafana/README.md` for import instructions.

## Testing
Run unit tests with `pytest`. The suite mocks GPU and external dependencies for fast local execution.
