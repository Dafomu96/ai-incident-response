"""
agents/diagnostic_reasoner.py — Agente 3: Diagnostic Reasoner
Core del proyecto. Razona sobre el contexto recopilado + RAG de runbooks.

Modelo desarrollo: Groq Llama 3.3 70B (gratuito)
Modelo producción: Claude Sonnet (razonamiento más profundo, structured output más fiable)
"""
from __future__ import annotations

from langchain_core.messages import SystemMessage, HumanMessage
from graph.state import IncidentState
from schemas.diagnosis import DiagnosisResult
from rag.retriever import retrieve_runbooks

_SYSTEM = """You are an expert SRE diagnostic agent with deep knowledge of distributed systems.

Given:
1. Collected logs, metrics, recent commits, and pod status
2. Relevant runbooks and historical postmortems from the knowledge base

Your task:
- Generate root cause hypotheses ordered by probability (highest first)
- For each hypothesis: provide evidence from the data and related runbooks
- Set requires_more_data=True ONLY if critical data is missing and a retry makes sense
- Provide a complete chain-of-thought reasoning

Be precise. Prioritize hypotheses with strongest data evidence.

IMPORTANT: Respond with valid JSON matching the DiagnosisResult schema exactly."""


def _get_llm():
    from langchain_groq import ChatGroq
    return ChatGroq(
        model="llama-3.3-70b-versatile",
        temperature=0,
        max_tokens=2048,
    ).with_structured_output(DiagnosisResult)


def diagnostic_reasoner_node(state: IncidentState) -> dict:
    alert = state["alert"]
    report = state.get("incident_report")
    attempts = state.get("diagnosis_attempts", 0)

    runbook_context = retrieve_runbooks(
        query=f"{alert.service} {alert.metric} {alert.description}",
        top_k=5,
    )

    prompt = (
        f"=== INCIDENT ===\n"
        f"Service: {alert.service} | Severity: {report.severity if report else 'unknown'}\n"
        f"Metric: {alert.metric} = {alert.value} (threshold: {alert.threshold})\n\n"
        f"=== COLLECTED DATA ===\n"
        f"Logs (last 2h):\n{state.get('collected_logs', 'N/A')}\n\n"
        f"Metrics history:\n{state.get('collected_metrics', 'N/A')}\n\n"
        f"Recent commits/PRs:\n{state.get('recent_commits', 'N/A')}\n\n"
        f"K8s pod status:\n{state.get('k8s_pod_status', 'N/A')}\n\n"
        f"=== RELEVANT RUNBOOKS (RAG) ===\n{runbook_context}\n\n"
        f"Diagnosis attempt: {attempts + 1}/3\n"
        "Generate root cause hypotheses with evidence."
    )

    diagnosis: DiagnosisResult = _get_llm().invoke([
        SystemMessage(content=_SYSTEM),
        HumanMessage(content=prompt),
    ])
    diagnosis.alert_id = alert.alert_id
    return {"diagnosis": diagnosis, "diagnosis_attempts": attempts + 1}
