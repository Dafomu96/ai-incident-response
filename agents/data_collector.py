"""
agents/data_collector.py — Agente 2: Data Collector
Recopila en paralelo: logs Loki, métricas Prometheus, commits GitHub, estado K8s.
"""
from __future__ import annotations

import asyncio
from graph.state import IncidentState
from tools.loki import fetch_logs
from tools.prometheus import fetch_metrics
from tools.github_api import fetch_recent_commits
from tools.kubernetes_api import fetch_pod_status


async def _collect_all(state: IncidentState) -> dict:
    report = state.get("incident_report")
    window = report.time_window_minutes if report else 120
    service = report.service if report else state["alert"].service

    logs, metrics, commits, pods = await asyncio.gather(
        fetch_logs(service=service, minutes=window),
        fetch_metrics(service=service, minutes=window),
        fetch_recent_commits(service=service),
        fetch_pod_status(service=service),
    )
    return {
        "collected_logs": logs,
        "collected_metrics": metrics,
        "recent_commits": commits,
        "k8s_pod_status": pods,
    }


def data_collector_node(state: IncidentState) -> dict:
    """
    Usa get_event_loop para ser compatible tanto con FastAPI (loop existente)
    como con ejecución directa desde script.
    """
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # FastAPI context: crear una tarea en el loop existente
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(asyncio.run, _collect_all(state))
                return future.result()
        else:
            return loop.run_until_complete(_collect_all(state))
    except RuntimeError:
        return asyncio.run(_collect_all(state))
