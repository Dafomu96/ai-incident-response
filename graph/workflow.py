"""
graph/workflow.py — StateGraph con edges condicionales.
"""
from __future__ import annotations

import asyncio
import concurrent.futures

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from graph.state import IncidentState
from agents.monitor_triage import monitor_triage_node
from agents.data_collector import data_collector_node
from agents.diagnostic_reasoner import diagnostic_reasoner_node
from agents.remediation_planner import remediation_planner_node
from agents.postmortem_writer import postmortem_writer_node


# ── Edge condicionales ─────────────────────────────────────────────────────────

def route_after_triage(state: IncidentState) -> str:
    report = state.get("incident_report")
    if report is None:
        return "error"
    if report.escalate_to_full_graph:
        return "data_collector"
    return END


def route_after_diagnosis(state: IncidentState) -> str:
    diagnosis = state.get("diagnosis")
    attempts = state.get("diagnosis_attempts", 0)
    if diagnosis is None:
        return "error"
    if diagnosis.requires_more_data and attempts < 2:
        return "data_collector"
    return "remediation_planner"


def route_after_planning(state: IncidentState) -> str:
    plan = state.get("remediation_plan")
    if plan is None:
        return "error"
    if plan.requires_approval:
        return "hitl_node"
    return "execute_remediation"


# ── HITL node — envía a Slack y continúa (sin bloquear el grafo) ──────────────

def hitl_node(state: IncidentState) -> dict:
    """
    Envía HITLRequest a Slack para visibilidad del equipo.
    Registra la acción en el estado para el postmortem.
    En producción: usar LangGraph interrupt() para pausar y esperar aprobación.
    """
    hitl_request = state.get("hitl_request")
    if not hitl_request:
        return {}

    async def _send():
        from tools.slack_hitl import send_hitl_request
        return await send_hitl_request(hitl_request)

    # Ejecutar envío a Slack de forma segura desde contexto sync o async
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            with concurrent.futures.ThreadPoolExecutor() as pool:
                result = pool.submit(asyncio.run, _send()).result()
        else:
            result = loop.run_until_complete(_send())
    except Exception as e:
        print(f"[HITL] Error enviando a Slack: {e}")
        result = {}

    print(f"[HITL] Mensaje enviado a Slack — canal: {hitl_request.slack_channel}")
    print(f"[HITL] Acción pendiente de aprobación: {hitl_request.action.description}")

    # Auto-aprueba para continuar el flujo (en prod: interrupt() aquí)
    return {"hitl_approved": True}


def execute_remediation(state: IncidentState) -> dict:
    """Ejecuta acciones auto-aprobadas. En prod: llamar a tools reales."""
    plan = state.get("remediation_plan")
    approved = state.get("hitl_approved")

    if plan:
        for action in plan.actions:
            if action.action_id in plan.auto_executable:
                print(f"[EXEC] AUTO: {action.description}")
            elif approved:
                print(f"[EXEC] APPROVED: {action.description}")
            else:
                print(f"[EXEC] SKIPPED (rejected): {action.description}")

    return {"resolved": True}


def error_node(state: IncidentState) -> dict:
    return {"error": "Unrecoverable error in graph execution"}


# ── Build & compile ────────────────────────────────────────────────────────────

def build_graph() -> StateGraph:
    builder = StateGraph(IncidentState)

    builder.add_node("monitor_triage", monitor_triage_node)
    builder.add_node("data_collector", data_collector_node)
    builder.add_node("diagnostic_reasoner", diagnostic_reasoner_node)
    builder.add_node("remediation_planner", remediation_planner_node)
    builder.add_node("postmortem_writer", postmortem_writer_node)
    builder.add_node("hitl_node", hitl_node)
    builder.add_node("execute_remediation", execute_remediation)
    builder.add_node("error", error_node)

    builder.set_entry_point("monitor_triage")

    builder.add_conditional_edges(
        "monitor_triage",
        route_after_triage,
        {"data_collector": "data_collector", END: END, "error": "error"},
    )
    builder.add_edge("data_collector", "diagnostic_reasoner")
    builder.add_conditional_edges(
        "diagnostic_reasoner",
        route_after_diagnosis,
        {
            "data_collector": "data_collector",
            "remediation_planner": "remediation_planner",
            "error": "error",
        },
    )
    builder.add_conditional_edges(
        "remediation_planner",
        route_after_planning,
        {
            "hitl_node": "hitl_node",
            "execute_remediation": "execute_remediation",
            "error": "error",
        },
    )
    builder.add_edge("hitl_node", "execute_remediation")
    builder.add_edge("execute_remediation", "postmortem_writer")
    builder.add_edge("postmortem_writer", END)

    return builder


def compile_graph(checkpointer=None):
    builder = build_graph()
    cp = checkpointer or MemorySaver()
    return builder.compile(checkpointer=cp)
