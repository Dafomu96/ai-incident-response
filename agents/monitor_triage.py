"""
agents/monitor_triage.py — Agente 1: Monitor & Triage
Entry point del grafo. Clasifica severidad con Groq Llama 3.3 (latencia <500ms).
"""
from __future__ import annotations

from langchain_core.messages import SystemMessage, HumanMessage
from graph.state import IncidentState
from schemas.incident import IncidentReport, Severity

_SYSTEM = """You are an SRE triage agent. Classify the incident severity and decide whether to escalate.

Severity rules:
- P1: service completely down, data loss risk, revenue impact > 10k€/min
- P2: degraded performance, partial outage, or high error rate (>5%)
- P3: minor anomaly, single non-critical component, auto-recoverable

Respond with a structured IncidentReport. Be fast and decisive."""


def _get_llm():
    """LLM instanciado lazy — evita error en import si no hay API key."""
    from langchain_groq import ChatGroq
    return ChatGroq(
        model="llama-3.3-70b-versatile",
        temperature=0,
        max_tokens=512,
    ).with_structured_output(IncidentReport)


def monitor_triage_node(state: IncidentState) -> dict:
    alert = state["alert"]
    prompt = (
        f"Alert: {alert.metric} = {alert.value} (threshold: {alert.threshold})\n"
        f"Service: {alert.service}\n"
        f"Labels: {alert.labels}\n"
        f"Description: {alert.description}\n\n"
        "Classify severity (P1/P2/P3) and decide whether to escalate."
    )
    report: IncidentReport = _get_llm().invoke([
        SystemMessage(content=_SYSTEM),
        HumanMessage(content=prompt),
    ])
    report.alert_id = alert.alert_id
    report.service = alert.service
    return {"incident_report": report}
