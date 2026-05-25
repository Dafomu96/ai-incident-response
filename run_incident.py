"""
run_incident.py — Test end-to-end del sistema completo.
Simula una alerta de DB connection pool exhaustion y ejecuta los 5 agentes.

Uso:
  python run_incident.py
"""
import os
from dotenv import load_dotenv
load_dotenv()

from schemas.incident import IncidentAlert
from graph.workflow import compile_graph


def main():
    print("=" * 60)
    print("AI INCIDENT RESPONSE SYSTEM — Test end-to-end")
    print("=" * 60)

    # Alerta simulada: DB connection pool exhaustion en payment-service
    alert = IncidentAlert(
        alert_id="inc-test-001",
        service="payment-service",
        metric="http_request_duration_seconds_p99",
        value=2.34,
        threshold=0.5,
        description="P99 latency spike — possible DB connection pool exhaustion",
        labels={"env": "production", "region": "eu-west-1"},
    )

    print(f"\n[ALERT] {alert.service} — {alert.metric} = {alert.value}s (umbral: {alert.threshold}s)")
    print(f"[ALERT] {alert.description}\n")

    # Compilar y ejecutar el grafo
    graph = compile_graph()

    print("[GRAPH] Iniciando grafo LangGraph...")
    result = graph.invoke(
        {
            "alert": alert,
            "diagnosis_attempts": 0,
            "resolved": False,
            "messages": [],
        },
        config={"configurable": {"thread_id": alert.alert_id}},
    )

    # Resultados
    print("\n" + "=" * 60)
    print("RESULTADOS")
    print("=" * 60)

    if result.get("incident_report"):
        r = result["incident_report"]
        print(f"\n[AGENTE 1 — Triage]")
        print(f"  Severidad: {r.severity}")
        print(f"  Escalar: {r.escalate_to_full_graph}")
        print(f"  Componentes: {r.affected_components}")
        print(f"  Razonamiento: {r.classification_reasoning[:120]}...")

    if result.get("diagnosis"):
        d = result["diagnosis"]
        print(f"\n[AGENTE 3 — Diagnóstico]")
        print(f"  Causa raíz: {d.top_hypothesis.hypothesis}")
        print(f"  Confianza: {d.overall_confidence:.0%}")
        print(f"  Evidencias: {d.top_hypothesis.evidence[:2]}")
        print(f"  Rediagnosticar: {d.requires_more_data}")

    if result.get("remediation_plan"):
        p = result["remediation_plan"]
        print(f"\n[AGENTE 4 — Remediación]")
        print(f"  Acciones totales: {len(p.actions)}")
        print(f"  Auto-ejecutables: {p.auto_executable}")
        print(f"  Requieren aprobación: {p.requires_approval}")
        for a in p.actions[:3]:
            print(f"  [{a.risk}] {a.description}")

    if result.get("postmortem"):
        pm = result["postmortem"]
        print(f"\n[AGENTE 5 — Postmortem]")
        print(f"  Título: {pm.title}")
        print(f"  Causa confirmada: {pm.confirmed_root_cause[:100]}")
        print(f"  Lecciones: {pm.lessons_learned[:2]}")
        print(f"  Time-to-detect: {pm.time_to_detect_minutes} min")
        print(f"  Time-to-resolve: {pm.time_to_resolve_minutes} min")

    print(f"\n[GRAPH] Resuelto: {result.get('resolved', False)}")
    print("=" * 60)


if __name__ == "__main__":
    main()
