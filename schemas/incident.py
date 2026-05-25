"""
schemas/incident.py — IncidentAlert y IncidentReport
Entrada al sistema: alerta de Prometheus/PagerDuty procesada por Agente 1.
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class Severity(str, Enum):
    P1 = "P1"  # crítico — HITL obligatorio
    P2 = "P2"  # alto — HITL para acciones destructivas
    P3 = "P3"  # medio — auto-ejecutable


class IncidentAlert(BaseModel):
    """Alerta raw de Prometheus o PagerDuty."""
    alert_id: str = Field(description="ID único de la alerta")
    service: str = Field(description="Servicio afectado")
    metric: str = Field(description="Métrica que disparó la alerta")
    value: float = Field(description="Valor actual de la métrica")
    threshold: float = Field(description="Umbral que fue superado")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    labels: dict[str, str] = Field(default_factory=dict)
    description: str = Field(default="")


class IncidentReport(BaseModel):
    """Output del Agente 1 (Monitor & Triage)."""
    alert_id: str
    severity: Severity = Field(description="P1/P2/P3 clasificado por Groq Llama 3.3")
    service: str
    affected_components: list[str] = Field(default_factory=list)
    time_window_minutes: int = Field(default=120)
    escalate_to_full_graph: bool = Field(
        description="True -> lanzar agentes 2-5. False -> auto-resolve P3 trivial."
    )
    classification_reasoning: str
    created_at: datetime = Field(default_factory=datetime.utcnow)

    @property
    def requires_hitl(self) -> bool:
        return self.severity in (Severity.P1, Severity.P2)
