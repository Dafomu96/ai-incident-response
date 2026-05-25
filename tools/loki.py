"""
tools/loki.py — Tool-calling a Loki/Grafana para logs.
Los mocks son específicos por servicio.
"""
from __future__ import annotations
import os, httpx

LOKI_URL = os.getenv("LOKI_URL", "")

_SERVICE_LOGS = {
    "payment-service": (
        "[MOCK] Loki logs for payment-service (last 2h):\n"
        "  [T-43min] ERROR ConnectionPoolExhaustedException: max pool size 100 reached\n"
        "  [T-43min] ERROR Failed to acquire DB connection after 30s timeout\n"
        "  [T-40min] WARN  Retry attempt 3/3 for DB connection\n"
        "  [T-38min] ERROR java.sql.SQLException: Connection refused to postgres:5432\n"
        "  [T-35min] ERROR Circuit breaker OPEN for postgres-primary"
    ),
    "auth-service": (
        "[MOCK] Loki logs for auth-service (last 2h):\n"
        "  [T-90min] INFO  JWT cache size: 45MB\n"
        "  [T-60min] INFO  JWT cache size: 312MB\n"
        "  [T-30min] WARN  JWT cache size: 891MB — approaching memory limit\n"
        "  [T-15min] ERROR OOMKilled: container exceeded memory limit 1024MB\n"
        "  [T-14min] INFO  Pod restarted — cache cleared\n"
        "  [T-10min] WARN  JWT cache growing again rapidly — no TTL configured"
    ),
    "order-service": (
        "[MOCK] Loki logs for order-service (last 2h):\n"
        "  [T-55min] ERROR deadlock detected on relation orders_items — process 12345\n"
        "  [T-54min] ERROR deadlock detected on relation orders_items — process 12346\n"
        "  [T-50min] ERROR ERROR: could not serialize access due to concurrent update\n"
        "  [T-45min] ERROR All database connections in use — queue full\n"
        "  [T-40min] ERROR Service health check failed — not responding"
    ),
    "notification-service": (
        "[MOCK] Loki logs for notification-service (last 2h):\n"
        "  [T-90min] INFO  Email sent via SendGrid: OK\n"
        "  [T-60min] ERROR SendGrid API returned 503 Service Unavailable\n"
        "  [T-59min] WARN  Retrying SendGrid request — attempt 2/3\n"
        "  [T-58min] ERROR SendGrid API returned 503 Service Unavailable — max retries exceeded\n"
        "  [T-45min] ERROR 5xx error rate rising: 23% of notification requests failing"
    ),
    "api-gateway": (
        "[MOCK] Loki logs for api-gateway (last 2h):\n"
        "  [T-72h]   INFO  Log rotation skipped — logrotate not configured\n"
        "  [T-24h]   WARN  Disk usage at 75%\n"
        "  [T-12h]   WARN  Disk usage at 85%\n"
        "  [T-2h]    ERROR Disk usage at 94% — access.log size: 48GB\n"
        "  [T-30min] ERROR No space left on device — cannot write logs"
    ),
    "inventory-service": (
        "[MOCK] Loki logs for inventory-service (last 2h):\n"
        "  [T-45min] WARN  Query duration: 1.2s for GET /products/listing\n"
        "  [T-40min] WARN  Query duration: 3.8s for GET /products/listing\n"
        "  [T-35min] ERROR Query duration: 8.5s for GET /products/listing — timeout approaching\n"
        "  [T-30min] ERROR SELECT N+1 detected: 847 queries for single listing request\n"
        "  [T-25min] ERROR Database connection pool exhausted by slow listing queries"
    ),
    "search-service": (
        "[MOCK] Loki logs for search-service (last 2h):\n"
        "  [T-35min] WARN  Elasticsearch cluster health: YELLOW\n"
        "  [T-30min] ERROR Elasticsearch node es-node-2 left cluster\n"
        "  [T-29min] ERROR Cluster health: RED — primary shards unassigned\n"
        "  [T-28min] ERROR Search requests failing: no primary shard available\n"
        "  [T-20min] ERROR All search endpoints returning 503"
    ),
}


async def fetch_logs(service: str, minutes: int = 120) -> str:
    if not LOKI_URL:
        return _mock_logs(service, minutes)
    async with httpx.AsyncClient() as client:
        query = f'{{service="{service}"}} |= "error" | logfmt'
        resp = await client.get(
            f"{LOKI_URL}/loki/api/v1/query_range",
            params={"query": query, "limit": 100},
        )
        return str(resp.json().get("data", {}).get("result", []))


def _mock_logs(service: str, minutes: int) -> str:
    return _SERVICE_LOGS.get(service, (
        f"[MOCK] Loki logs for {service} (last {minutes}min):\n"
        f"  No significant errors detected"
    ))
