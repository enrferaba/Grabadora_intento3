# Grafana Dashboards

Import the dashboards located in `dashboards/` to visualize API latency, GPU utilization, queue depth, and error rates.

* **API Overview** – Panels for request duration (Prometheus histogram), health check uptime, and throughput.
* **GPU + Queue** – Uses the `gpu_memory_usage_bytes` and `queue_length` metrics to show live GPU memory and queued jobs.
* **Errors** – Tracks `api_errors_total` and worker failure counts via Prometheus.

Provision Grafana by mounting this directory inside the container as shown in `docker-compose.yml`.
