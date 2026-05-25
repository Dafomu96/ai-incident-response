"""
graph/state.py — IncidentState
Estado tipado del grafo LangGraph. Persiste en cada paso (checkpointing).
Si el sistema cae a mitad de un incidente, retoma exactamente donde lo dejó.
"""
from __future__ import annotations

from typing import Annotated, Optional
from typing_extensions import TypedDict

from langgraph.graph.message import add_messages

from schemas.incident import IncidentAlert, IncidentReport
from schemas.diagnosis import DiagnosisResult
from schemas.remediation import RemediationPlan, HITLRequest
from schemas.postmortem import PostmortemDraft


class IncidentState(TypedDict):
    """
    Estado completo del grafo. Cada agente lee lo que necesita y escribe su output.
    LangGraph persiste este estado en cada nodo — permite recuperación ante fallos.
    """

    # ── Input ──────────────────────────────────────────────────────────────────
    alert: IncidentAlert                          # Alerta raw de entrada

    # ── Agente 1: Monitor & Triage ─────────────────────────────────────────────
    incident_report: Optional[IncidentReport]     # Clasificación P1/P2/P3

    # ── Agente 2: Data Collector ───────────────────────────────────────────────
    collected_logs: Optional[str]                 # Logs de Loki (últimas 2h)
    collected_metrics: Optional[str]              # Métricas históricas Prometheus
    recent_commits: Optional[str]                 # Commits/PRs recientes GitHub
    k8s_pod_status: Optional[str]                 # Estado de pods Kubernetes

    # ── Agente 3: Diagnostic Reasoner ─────────────────────────────────────────
    diagnosis: Optional[DiagnosisResult]          # Causa raíz + hipótesis
    diagnosis_attempts: int                       # Contador para evitar loops infinitos

    # ── Agente 4: Remediation Planner ─────────────────────────────────────────
    remediation_plan: Optional[RemediationPlan]
    hitl_request: Optional[HITLRequest]           # Pendiente de aprobación humana
    hitl_approved: Optional[bool]                 # None=pendiente

    # ── Agente 5: Postmortem Writer ────────────────────────────────────────────
    postmortem: Optional[PostmortemDraft]

    # ── Control de flujo ──────────────────────────────────────────────────────
    messages: Annotated[list, add_messages]       # Historial de mensajes LangChain
    error: Optional[str]                          # Error capturado para manejo
    resolved: bool                                # True cuando el incidente está cerrado
