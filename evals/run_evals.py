"""
evals/run_evals.py — Runner de evaluaciones contra ground truth histórico.

Uso:
  python -m evals.run_evals                    # todos los incidentes
  python -m evals.run_evals --incident hist-001 # uno específico
  python -m evals.run_evals --dry-run          # sin llamadas LLM
"""
from __future__ import annotations

import argparse
import json
import os
import time
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

from schemas.incident import IncidentAlert
from graph.workflow import compile_graph
from evals.metrics import compute_metrics, aggregate_metrics

DATASET_PATH = Path(__file__).parent / "datasets" / "historical_incidents.json"


def load_dataset(incident_id: str | None = None) -> list[dict]:
    with open(DATASET_PATH) as f:
        data = json.load(f)
    if incident_id:
        data = [d for d in data if d["alert_id"] == incident_id]
    return data


def run_single_eval(graph, incident_data: dict, verbose: bool = True) -> dict:
    """Ejecuta el grafo para un incidente y calcula métricas."""
    alert_data = incident_data["alert"]
    alert = IncidentAlert(**alert_data)
    gt = incident_data["ground_truth"]

    if verbose:
        print(f"\n{'='*55}")
        print(f"[EVAL] {alert.alert_id} — {alert.service}")
        print(f"[EVAL] Ground truth severity: {gt['severity']}")
        print(f"[EVAL] Ground truth root cause: {gt['root_cause'][:60]}...")

    start = time.time()
    try:
        result = graph.invoke(
            {
                "alert": alert,
                "diagnosis_attempts": 0,
                "resolved": False,
                "messages": [],
            },
            config={"configurable": {"thread_id": f"eval-{alert.alert_id}"}},
        )
        elapsed = time.time() - start
        metrics = compute_metrics(result, incident_data)
        metrics["elapsed_seconds"] = round(elapsed, 2)
        metrics["error"] = None

        if verbose:
            print(f"[EVAL] Predicted severity: {result.get('incident_report', {}).severity if result.get('incident_report') else 'N/A'}")
            print(f"[EVAL] Predicted root cause: {result['diagnosis'].top_hypothesis.hypothesis[:60] if result.get('diagnosis') else 'N/A'}...")
            print(f"[EVAL] Severity correct: {'✅' if metrics['severity_correct'] else '❌'}")
            print(f"[EVAL] Top-1 correct:   {'✅' if metrics['top1_correct'] else '❌'} (score: {metrics['keyword_score']:.0%})")
            print(f"[EVAL] Top-3 correct:   {'✅' if metrics['top3_correct'] else '❌'}")
            print(f"[EVAL] Confidence:      {metrics['overall_confidence']:.0%}")
            print(f"[EVAL] Time:            {elapsed:.1f}s")

    except Exception as e:
        elapsed = time.time() - start
        print(f"[EVAL] ERROR: {e}")
        metrics = {
            "alert_id": alert.alert_id,
            "error": str(e),
            "elapsed_seconds": round(elapsed, 2),
            "severity_correct": False,
            "top1_correct": False,
            "top3_correct": False,
            "keyword_score": 0.0,
            "overall_confidence": 0.0,
        }

    return metrics


def print_summary(all_metrics: list[dict], elapsed_total: float) -> None:
    agg = aggregate_metrics([m for m in all_metrics if not m.get("error")])
    errors = [m for m in all_metrics if m.get("error")]

    print(f"\n{'='*55}")
    print("EVALUATION SUMMARY")
    print(f"{'='*55}")
    print(f"Total incidents evaluated: {agg.get('total_incidents', 0)}")
    print(f"Errors:                    {len(errors)}")
    print(f"Total time:                {elapsed_total:.1f}s")
    print(f"\n--- Accuracy ---")
    print(f"Severity accuracy:         {agg.get('severity_accuracy', 0):.0%}")
    print(f"Top-1 diagnostic accuracy: {agg.get('top1_accuracy', 0):.0%}")
    print(f"Top-3 diagnostic accuracy: {agg.get('top3_accuracy', 0):.0%}")
    print(f"Avg keyword score:         {agg.get('avg_keyword_score', 0):.0%}")
    print(f"\n--- System ---")
    print(f"Avg confidence:            {agg.get('avg_confidence', 0):.0%}")
    print(f"HITL trigger rate:         {agg.get('hitl_rate', 0):.0%}")
    print(f"Postmortem rate:           {agg.get('postmortem_rate', 0):.0%}")
    print(f"Avg diagnosis attempts:    {agg.get('avg_diagnosis_attempts', 0):.1f}")

    if errors:
        print(f"\n--- Errors ---")
        for m in errors:
            print(f"  {m['alert_id']}: {m['error'][:80]}")

    # Guardar resultados
    output = {
        "timestamp": datetime.utcnow().isoformat(),
        "summary": agg,
        "individual": all_metrics,
    }
    output_path = Path(__file__).parent / "results_latest.json"
    with open(output_path, "w") as f:
        json.dump(output, f, indent=2, default=str)
    print(f"\nResultados guardados en: {output_path}")


def main():
    parser = argparse.ArgumentParser(description="Run evaluations against historical incidents")
    parser.add_argument("--incident", help="Run single incident by ID")
    parser.add_argument("--limit", type=int, help="Max incidents to evaluate")
    args = parser.parse_args()

    dataset = load_dataset(args.incident)
    if args.limit:
        dataset = dataset[:args.limit]

    print(f"Evaluando {len(dataset)} incidente(s)...")
    print("LangSmith tracing: " + ("ON" if os.getenv("LANGCHAIN_TRACING_V2") else "OFF"))

    graph = compile_graph()
    all_metrics = []
    start_total = time.time()

    for incident in dataset:
        metrics = run_single_eval(graph, incident, verbose=True)
        all_metrics.append(metrics)
        # Pausa entre llamadas para no saturar la API de Groq
        time.sleep(2)

    elapsed_total = time.time() - start_total
    print_summary(all_metrics, elapsed_total)


if __name__ == "__main__":
    main()
