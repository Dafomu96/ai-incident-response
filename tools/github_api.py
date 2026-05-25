"""
tools/github_api.py — Tool-calling a GitHub API para commits y PRs recientes.
Los mocks son específicos por servicio para diagnósticos más precisos.
"""
from __future__ import annotations
import os, httpx

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")
GITHUB_ORG = os.getenv("GITHUB_ORG", "my-org")

# Mocks específicos por servicio — reflejan el tipo de incidente probable
_SERVICE_MOCKS = {
    "payment-service": (
        "[MOCK] Recent commits for payment-service (last 4h):\n"
        "  [a3f1c2d] chore: bump postgres-driver from 14.1 to 14.3 — deploy-bot\n"
        "  [b91e4f7] feat: increase connection pool size to 150 — john.doe\n"
        "  NOTE: postgres-driver bump deployed 47min ago (coincides with incident start)"
    ),
    "auth-service": (
        "[MOCK] Recent commits for auth-service (last 4h):\n"
        "  [c82d1f9] feat: add JWT token caching for performance — jane.smith\n"
        "  [d71e4a2] refactor: remove cache TTL limit for tokens — jane.smith\n"
        "  NOTE: cache TTL removal deployed 2h ago — unbounded cache growth possible"
    ),
    "order-service": (
        "[MOCK] Recent commits for order-service (last 4h):\n"
        "  [e91b3c7] feat: add bulk order processing with nested transactions — dev-bot\n"
        "  [f82d1a4] fix: retry failed transactions without rollback — john.doe\n"
        "  NOTE: nested transaction logic deployed 1h ago — deadlock risk detected"
    ),
    "notification-service": (
        "[MOCK] Recent commits for notification-service (last 4h):\n"
        "  [g71c2b8] No recent deploys in last 4h\n"
        "  NOTE: External email provider (SendGrid) reporting degraded service since 10:30"
    ),
    "api-gateway": (
        "[MOCK] Recent commits for api-gateway (last 4h):\n"
        "  [h62d3a9] No recent deploys in last 4h\n"
        "  NOTE: No code changes — infrastructure issue likely"
    ),
    "inventory-service": (
        "[MOCK] Recent commits for inventory-service (last 4h):\n"
        "  [i53e4b1] feat: add product relationship loading in listing endpoint — dev-bot\n"
        "  [j44f5c2] perf: remove eager loading to reduce memory — jane.smith\n"
        "  NOTE: eager loading removed in last deploy — N+1 query risk on product relationships"
    ),
    "search-service": (
        "[MOCK] Recent commits for search-service (last 4h):\n"
        "  [k35g6d3] No recent deploys in last 4h\n"
        "  NOTE: Elasticsearch node es-node-2 went offline 30min ago — cluster health RED"
    ),
}


async def fetch_recent_commits(service: str, hours: int = 4) -> str:
    if not GITHUB_TOKEN:
        return _mock_commits(service)
    headers = {"Authorization": f"Bearer {GITHUB_TOKEN}", "Accept": "application/vnd.github+json"}
    async with httpx.AsyncClient(headers=headers) as client:
        resp = await client.get(
            f"https://api.github.com/repos/{GITHUB_ORG}/{service}/commits",
            params={"per_page": 10},
        )
        commits = resp.json()
        return "\n".join(
            f"  [{c['sha'][:7]}] {c['commit']['message'][:80]} — {c['commit']['author']['name']}"
            for c in commits[:5]
        )


def _mock_commits(service: str) -> str:
    return _SERVICE_MOCKS.get(service, (
        f"[MOCK] Recent commits for {service} (last 4h):\n"
        f"  No recent significant changes detected"
    ))
