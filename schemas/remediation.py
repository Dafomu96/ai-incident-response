"""
schemas/remediation.py — RemediationPlan y HITLRequest
Output del Agente 4 (Remediation Planner).
"""
from __future__ import annotations

from enum import Enum
from datetime import datetime
from pydantic import BaseModel, Field


class ActionRisk(str, Enum):
    LOW = "low"       # auto-ejecutable (restart pod, clear cache)
    HIGH = "high"     # requiere aprobación humana (rollback deploy, escalar infra)


class RemediationAction(BaseModel):
    action_id: str
    description: str
    command: str = Field(description="Comando o llamada a API a ejecutar")
    risk: ActionRisk
    reversible: bool
    estimated_impact: str


class RemediationPlan(BaseModel):
    """Plan de remediación completo generado por el Agente 4."""
    alert_id: str
    actions: list[RemediationAction]
    auto_executable: list[str] = Field(description="action_ids ejecutables sin aprobación")
    requires_approval: list[str] = Field(description="action_ids que necesitan HITL")
    execution_order: list[str] = Field(description="Orden recomendado de action_ids")
    created_at: datetime = Field(default_factory=datetime.utcnow)


class HITLRequest(BaseModel):
    """Request enviado a Slack para aprobación humana."""
    alert_id: str
    action: RemediationAction
    diagnosis_summary: str
    timeout_minutes: int = Field(default=10, description="Escalado automático si no hay respuesta")
    slack_channel: str
    requested_at: datetime = Field(default_factory=datetime.utcnow)
    approved: bool | None = Field(default=None, description="None=pendiente, True=aprobado, False=rechazado")
