"""
schemas/postmortem.py — PostmortemDraft
Output del Agente 5 (Postmortem Writer).
Se ingesta en la base RAG para mejorar diagnósticos futuros (loop de aprendizaje).
"""
from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel, Field


class TimelineEvent(BaseModel):
    timestamp: datetime
    event: str
    actor: str = Field(description="Sistema o persona que realizó la acción")


class PostmortemDraft(BaseModel):
    """
    Postmortem generado automáticamente tras resolver el incidente.
    Cierre del loop de aprendizaje: se ingesta en ChromaDB para RAG futuro.
    """
    alert_id: str
    title: str
    severity: str
    service: str
    timeline: list[TimelineEvent]
    confirmed_root_cause: str
    contributing_factors: list[str]
    actions_taken: list[str]
    lessons_learned: list[str]
    preventive_measures: list[str]
    time_to_detect_minutes: float
    time_to_resolve_minutes: float
    generated_at: datetime = Field(default_factory=datetime.utcnow)

    def to_rag_document(self) -> str:
        """Serializa el postmortem como texto para ingestar en ChromaDB."""
        return (
            f"POSTMORTEM: {self.title}\n"
            f"Service: {self.service} | Severity: {self.severity}\n"
            f"Root cause: {self.confirmed_root_cause}\n"
            f"Contributing factors: {', '.join(self.contributing_factors)}\n"
            f"Lessons learned: {', '.join(self.lessons_learned)}\n"
            f"Preventive measures: {', '.join(self.preventive_measures)}"
        )
