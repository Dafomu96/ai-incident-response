"""
agents/postmortem_writer.py — Agente 5: Postmortem Writer

Modelo desarrollo: Groq Llama 3.3 70B
Modelo producción: Claude Sonnet
"""
from __future__ import annotations

from langchain_core.messages import SystemMessage, HumanMessage
from graph.state import IncidentState
from schemas.postmortem import PostmortemDraft
from rag.ingestion import ingest_postmortem

_SYSTEM = """You are an SRE postmortem specialist. Write a blameless postmortem.

Include:
- Complete timeline of events
- Confirmed root cause (from diagnosis)
- Contributing factors
- Actions taken during remediation
- Lessons learned (technical and process)
- Preventive measures to avoid recurrence

Be specific, actionable, and blameless.

IMPORTANT: Respond with valid JSON matching the PostmortemDraft schema exactly."""


def _get_llm():
    from langchain_groq import ChatGroq
    return ChatGroq(
        model="llama-3.3-70b-versatile",
        temperature=0,
        max_tokens=3000,
    ).with_structured_output(PostmortemDraft)


def postmortem_writer_node(state: IncidentState) -> dict:
    alert = state["alert"]
    diagnosis = state["diagnosis"]
    plan = state.get("remediation_plan")
    report = state.get("incident_report")

    prompt = (
        f"=== INCIDENT SUMMARY ===\n"
        f"Service: {alert.service} | Severity: {report.severity if report else 'P2'}\n"
        f"Alert: {alert.metric} = {alert.value}\n\n"
        f"=== ROOT CAUSE ===\n"
        f"{diagnosis.top_hypothesis.hypothesis}\n"
        f"Evidence: {', '.join(diagnosis.top_hypothesis.evidence)}\n\n"
        f"=== REMEDIATION ACTIONS ===\n"
        f"{[a.description for a in plan.actions] if plan else 'N/A'}\n\n"
        f"=== REASONING CHAIN ===\n{diagnosis.reasoning_chain}\n\n"
        "Write a complete blameless postmortem."
    )

    postmortem: PostmortemDraft = _get_llm().invoke([
        SystemMessage(content=_SYSTEM),
        HumanMessage(content=prompt),
    ])
    postmortem.alert_id = alert.alert_id
    ingest_postmortem(postmortem)
    return {"postmortem": postmortem, "resolved": True}
