"""
schemas/diagnosis.py — DiagnosisResult
Output del Agente 3 (Diagnostic Reasoner): causa raíz con hipótesis ordenadas por probabilidad.
"""
from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel, Field


class RootCauseHypothesis(BaseModel):
    """Una hipótesis de causa raíz con su probabilidad y evidencias."""
    hypothesis: str = Field(description="Descripción de la causa raíz propuesta")
    probability: float = Field(ge=0.0, le=1.0, description="Confianza estimada [0-1]")
    evidence: list[str] = Field(description="Señales de logs/métricas que soportan esta hipótesis")
    related_runbooks: list[str] = Field(
        default_factory=list,
        description="IDs o títulos de runbooks relevantes recuperados del RAG"
    )


class DiagnosisResult(BaseModel):
    """
    Output estructurado del Diagnostic Reasoner.
    Contiene hipótesis ordenadas por probabilidad descendente.
    """
    alert_id: str
    hypotheses: list[RootCauseHypothesis] = Field(
        description="Hipótesis ordenadas por probabilidad desc"
    )
    top_hypothesis: RootCauseHypothesis = Field(
        description="Hipótesis más probable — usado por Agente 4"
    )
    overall_confidence: float = Field(ge=0.0, le=1.0)
    data_sources_used: list[str] = Field(
        description="Fuentes consultadas: loki, prometheus, github, k8s"
    )
    reasoning_chain: str = Field(description="Chain-of-thought completo del LLM")
    requires_more_data: bool = Field(
        default=False,
        description="True -> el grafo vuelve al Agente 2 para recopilar más datos"
    )
    diagnosed_at: datetime = Field(default_factory=datetime.utcnow)
