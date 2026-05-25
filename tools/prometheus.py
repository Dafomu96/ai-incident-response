"""
tools/prometheus.py — Tool-calling a Prometheus API (con mock específico por servicio).
"""
from __future__ import annotations
import os, httpx

PROMETHEUS_URL = os.getenv("PROMETHEUS_URL", "")

_SERVICE_METRICS = {
    "payment-service": (
        "[MOCK] Prometheus metrics for payment-service:\n"
        "  error_rate: 0.127 req/s (spike started T-45min)\n"
        "  latency_p99: 2340ms (normal: 180ms)\n"
        "  db_pool_active: 100/100 (SATURATED)\n"
        "  cpu_usage: 94% | memory_usage: 87%"
    ),
    "auth-service": (
        "[MOCK] Prometheus metrics for auth-service:\n"
        "  memory_usage: 95% and growing (normal: 45%)\n"
        "  pod_restarts: 5 in last 2h (OOMKilled)\n"
        "  jwt_cache_size_mb: 891MB (growing linearly, no TTL)\n"
        "  latency_p99: 340ms (normal: 80ms)"
    ),
    "order-service": (
        "[MOCK] Prometheus metrics for order-service:\n"
        "  http_requests_total: 0 (service unresponsive)\n"
        "  db_active_transactions: 847 (normal: 12)\n"
        "  db_deadlocks_total: 234 in last hour\n"
        "  cpu_usage: 100% (db lock contention)"
    ),
    "notification-service": (
        "[MOCK] Prometheus metrics for notification-service:\n"
        "  http_5xx_rate: 23% (normal: <1%)\n"
        "  external_api_errors: 892 calls to SendGrid failing\n"
        "  queue_depth: 12847 pending notifications\n"
        "  cpu_usage: 12% (low — blocked on external API)"
    ),
    "api-gateway": (
        "[MOCK] Prometheus metrics for api-gateway:\n"
        "  disk_usage: 96% (normal: 45%)\n"
        "  disk_write_errors: 47 in last 30min\n"
        "  log_file_size_gb: 48.3GB (access.log)\n"
        "  http_requests: normal — no latency spike"
    ),
    "inventory-service": (
        "[MOCK] Prometheus metrics for inventory-service:\n"
        "  latency_p99: 8500ms (normal: 200ms)\n"
        "  db_queries_per_request: 847 (normal: 3)\n"
        "  db_pool_active: 98/100\n"
        "  error_rate: 0.18 req/s"
    ),
    "search-service": (
        "[MOCK] Prometheus metrics for search-service:\n"
        "  elasticsearch_cluster_health: RED (was GREEN)\n"
        "  unassigned_shards: 12\n"
        "  search_requests_failing: 100%\n"
        "  es_node_count: 2/3 (es-node-2 offline)"
    ),
}


async def fetch_metrics(service: str, minutes: int = 120) -> str:
    if not PROMETHEUS_URL:
        return _mock_metrics(service, minutes)
    async with httpx.AsyncClient() as client:
        queries = {
            "error_rate": f'sum(rate(http_requests_total{{service="{service}",status=~"5.."}}[5m]))',
            "latency_p99": f'histogram_quantile(0.99, rate(http_request_duration_seconds_bucket{{service="{service}"}}[5m]))',
        }
        results = {}
        for name, query in queries.items():
            resp = await client.get(f"{PROMETHEUS_URL}/api/v1/query", params={"query": query})
            results[name] = resp.json().get("data", {})
        return str(results)


def _mock_metrics(service: str, minutes: int) -> str:
    return _SERVICE_METRICS.get(service, (
        f"[MOCK] Prometheus metrics for {service} (last {minutes}min):\n"
        f"  No significant anomalies detected"
    ))
