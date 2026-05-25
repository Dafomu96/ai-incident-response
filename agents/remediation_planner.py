"""
agents/remediation_planner.py — Agente 4: Remediation Planner

Modelo desarrollo: Groq Llama 3.3 70B
Modelo producción: Claude Sonnet
"""
from __future__ import annotations

import os
from langchain_core.messages import SystemMessage, HumanMessage
from graph.state import IncidentState
from schemas.remediation import RemediationPlan, HITLRequest

_SYSTEM = """You are an SRE remediation expert. Generate a step-by-step remediation plan.

Risk classification:
- LOW (auto-executable): restart pod, clear cache, scale replicas, reload config
- HIGH (requires human approval): rollback deployment, delete data, modify firewall, scale infra

Always prefer reversible actions first. Order actions to minimize blast radius.

IMPORTANT: Respond with valid JSON matching the RemediationPlan schema exactly."""


def _get_llm():
    from langchain_groq import ChatGroq
    return ChatGroq(
        model="llama-3.3-70b-versatile",
        temperature=0,
        max_tokens=2048,
    ).with_structured_output(RemediationPlan)


def remediation_planner_node(state: IncidentState) -> dict:
    diagnosis = state["diagnosis"]
    alert = state["alert"]
    report = state.get("incident_report")

    prompt = (
        f"=== CONFIRMED DIAGNOSIS ===\n"
        f"Root cause: {diagnosis.top_hypothesis.hypothesis}\n"
        f"Confidence: {diagnosis.overall_confidence:.0%}\n"
        f"Evidence: {', '.join(diagnosis.top_hypothesis.evidence)}\n\n"
        f"Service: {alert.service} | Severity: {report.severity if report else 'P2'}\n\n"
        "Generate a prioritized remediation plan."
    )

    plan: RemediationPlan = _get_llm().invoke([
        SystemMessage(content=_SYSTEM),
        HumanMessage(content=prompt),
    ])
    plan.alert_id = alert.alert_id

    hitl_request = None
    if plan.requires_approval:
        high_risk_actions = [a for a in plan.actions if a.action_id in plan.requires_approval]
        if high_risk_actions:
            hitl_request = HITLRequest(
                alert_id=alert.alert_id,
                action=high_risk_actions[0],
                diagnosis_summary=f"{diagnosis.top_hypothesis.hypothesis} (confianza: {diagnosis.overall_confidence:.0%})",
                slack_channel=os.getenv("SLACK_HITL_CHANNEL", "#incident-approvals"),
            )

    return {"remediation_plan": plan, "hitl_request": hitl_request}
