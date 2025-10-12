# Deployment Guide

1. Copy `.env.example` to `.env` and update secrets.
2. Run `docker compose up --build` to start API, worker, Redis, Postgres, MinIO, Prometheus, and Grafana.
3. Initialize the database schema: `docker compose exec api alembic upgrade head`.
4. Create MinIO buckets automatically at startup or via `mc mb minio/audio`.
5. Configure Grafana data source to point at Prometheus (`http://prometheus:9090`). Import dashboards from `deploy/grafana/dashboards/`.
6. Scale workers with `docker compose up --scale worker=3` to handle higher throughput.

For production deployments use managed PostgreSQL/Redis services, attach persistent volumes to MinIO, and configure HTTPS via a reverse proxy (e.g., Traefik or Nginx).
