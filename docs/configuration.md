# Configuration Reference

| Variable | Description | Default |
| --- | --- | --- |
| `GRABADORA_REDIS_URL` | Redis connection string for RQ workers. | `redis://redis:6379/0` |
| `GRABADORA_RQ_DEFAULT_QUEUE` | Queue name for transcription jobs. | `transcription` |
| `GRABADORA_DATABASE_URL` | SQLAlchemy database URL for PostgreSQL/MariaDB. | `postgresql+psycopg2://postgres:postgres@db:5432/grabadora` |
| `GRABADORA_S3_ENDPOINT_URL` | Endpoint for S3/MinIO. | `http://minio:9000` |
| `GRABADORA_S3_ACCESS_KEY` | Access key for S3-compatible storage. | `minioadmin` |
| `GRABADORA_S3_SECRET_KEY` | Secret key for S3-compatible storage. | `minioadmin` |
| `GRABADORA_S3_BUCKET_AUDIO` | Bucket for audio uploads. | `audio` |
| `GRABADORA_S3_BUCKET_TRANSCRIPTS` | Bucket for transcript blobs. | `transcripts` |
| `GRABADORA_JWT_SECRET_KEY` | Secret key used to sign JWT access tokens. | `super-secret` |
| `GRABADORA_JWT_ALGORITHM` | JWT algorithm. | `HS256` |
| `GRABADORA_JWT_EXPIRATION_MINUTES` | Token lifetime in minutes. | `30` |
| `GRABADORA_TRANSCRIPTION_QUANTIZATION` | faster-whisper quantization level. | `float16` |
| `GRABADORA_PROMETHEUS_NAMESPACE` | Namespace prefix for metrics. | `grabadora` |

Update secrets before deploying to production. For MinIO, create users via the console and update access keys accordingly. When using AWS S3, replace the endpoint with `https://s3.amazonaws.com` and ensure the bucket names already exist.
