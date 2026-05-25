"""
evals/metrics.py — Métricas de evaluación del sistema.
Sin RAGAS — evaluación directa contra ground truth con LangSmith.
"""
from __future__ import annotations


def keyword_overlap_score(hypothesis: str, keywords: list[str]) -> float:
    """
    Mide qué fracción de las keywords del ground truth aparecen en la hipótesis.
    Simple pero efectivo para evaluar precisión diagnóstica sin LLM adicional.
    """
    if not keywords:
        return 0.0
    hypothesis_lower = hypothesis.lower()
    matches = sum(1 for kw in keywords if kw.lower() in hypothesis_lower)
    return matches / len(keywords)


def top1_accuracy(hypothesis: str, keywords: list[str], threshold: float = 0.25) -> bool:
    """La hipótesis top-1 contiene al menos threshold de las keywords del ground truth."""
    return keyword_overlap_score(hypothesis, keywords) >= threshold


def top3_accuracy(hypotheses: list[str], keywords: list[str], threshold: float = 0.25) -> bool:
    """Al menos una de las 3 primeras hipótesis supera el threshold."""
    return any(
        keyword_overlap_score(h, keywords) >= threshold
        for h in hypotheses[:3]
    )


def severity_accuracy(predicted: str, ground_truth: str) -> bool:
    """La severidad clasificada coincide con el ground truth."""
    return predicted.upper().replace("SEVERITY.", "") == ground_truth.upper()


def compute_metrics(result: dict, ground_truth: dict) -> dict:
    """
    Calcula todas las métricas para un incidente dado.
    
    Args:
        result: Output del grafo LangGraph
        ground_truth: Datos del dataset histórico
    
    Returns:
        Dict con todas las métricas del incidente
    """
    metrics = {
        "alert_id": ground_truth.get("alert_id"),
        "severity_correct": False,
        "top1_correct": False,
        "top3_correct": False,
        "keyword_score": 0.0,
        "overall_confidence": 0.0,
        "requires_more_data": False,
        "diagnosis_attempts": 0,
        "has_remediation": False,
        "has_postmortem": False,
        "hitl_triggered": False,
    }

    gt = ground_truth.get("ground_truth", {})
    keywords = gt.get("root_cause_keywords", [])
    gt_severity = gt.get("severity", "")

    # Severidad
    if result.get("incident_report"):
        predicted_severity = str(result["incident_report"].severity).replace("Severity.", "")
        metrics["severity_correct"] = severity_accuracy(predicted_severity, gt_severity)

    # Diagnóstico
    if result.get("diagnosis"):
        diagnosis = result["diagnosis"]
        top_hypothesis = diagnosis.top_hypothesis.hypothesis
        all_hypotheses = [h.hypothesis for h in diagnosis.hypotheses]

        metrics["top1_correct"] = top1_accuracy(top_hypothesis, keywords)
        metrics["top3_correct"] = top3_accuracy(all_hypotheses, keywords)
        metrics["keyword_score"] = keyword_overlap_score(top_hypothesis, keywords)
        metrics["overall_confidence"] = diagnosis.overall_confidence
        metrics["requires_more_data"] = diagnosis.requires_more_data
        metrics["diagnosis_attempts"] = result.get("diagnosis_attempts", 1)

    # Remediación
    if result.get("remediation_plan"):
        plan = result["remediation_plan"]
        metrics["has_remediation"] = True
        metrics["hitl_triggered"] = bool(plan.requires_approval)
        metrics["auto_actions"] = len(plan.auto_executable)
        metrics["approval_actions"] = len(plan.requires_approval)

    # Postmortem
    metrics["has_postmortem"] = result.get("postmortem") is not None

    return metrics


def aggregate_metrics(all_metrics: list[dict]) -> dict:
    """Agrega métricas de múltiples incidentes en un resumen."""
    if not all_metrics:
        return {}

    n = len(all_metrics)
    return {
        "total_incidents": n,
        "severity_accuracy": sum(m["severity_correct"] for m in all_metrics) / n,
        "top1_accuracy": sum(m["top1_correct"] for m in all_metrics) / n,
        "top3_accuracy": sum(m["top3_correct"] for m in all_metrics) / n,
        "avg_keyword_score": sum(m["keyword_score"] for m in all_metrics) / n,
        "avg_confidence": sum(m["overall_confidence"] for m in all_metrics) / n,
        "hitl_rate": sum(m["hitl_triggered"] for m in all_metrics) / n,
        "postmortem_rate": sum(m["has_postmortem"] for m in all_metrics) / n,
        "avg_diagnosis_attempts": sum(m["diagnosis_attempts"] for m in all_metrics) / n,
    }
