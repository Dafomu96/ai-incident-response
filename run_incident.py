"""
run_incident.py -- End-to-end test of the complete system.
Simulates a DB connection pool exhaustion alert and runs all 5 agents.

Usage:
  python run_incident.py
"""
import os
import warnings
warnings.filterwarnings("ignore")
os.environ["TF_CPP_MIN_LOG_LEVEL"] = "3"

from dotenv import load_dotenv
load_dotenv()

from schemas.incident import IncidentAlert
from graph.workflow import compile_graph


def main():
    print("=" * 60)
    print("AI INCIDENT RESPONSE SYSTEM -- End-to-end test")
    print("=" * 60)

    alert = IncidentAlert(
        alert_id="inc-test-001",
        service="payment-service",
        metric="http_request_duration_seconds_p99",
        value=2.34,
        threshold=0.5,
        description="P99 latency spike — possible DB connection pool exhaustion",
        labels={"env": "production", "region": "eu-west-1"},
    )

    print(f"\n[ALERT] {alert.service} — {alert.metric} = {alert.value}s (threshold: {alert.threshold}s)")
    print(f"[ALERT] {alert.description}\n")

    graph = compile_graph()

    print("[GRAPH] Starting LangGraph pipeline...")
    result = graph.invoke(
        {
            "alert": alert,
            "diagnosis_attempts": 0,
            "resolved": False,
            "messages": [],
        },
        config={"configurable": {"thread_id": alert.alert_id}},
    )

    print("\n" + "=" * 60)
    print("RESULTS")
    print("=" * 60)

    if result.get("incident_report"):
        r = result["incident_report"]
        print(f"\n[AGENT 1 -- Triage]")
        print(f"  Severity: {r.severity}")
        print(f"  Escalate: {r.escalate_to_full_graph}")
        print(f"  Components: {r.affected_components}")
        print(f"  Reasoning: {r.classification_reasoning[:120]}...")

    if result.get("diagnosis"):
        d = result["diagnosis"]
        print(f"\n[AGENT 3 -- Diagnosis]")
        print(f"  Root cause: {d.top_hypothesis.hypothesis}")
        print(f"  Confidence: {d.overall_confidence:.0%}")
        print(f"  Evidence: {d.top_hypothesis.evidence[:2]}")
        print(f"  Re-diagnose: {d.requires_more_data}")

    if result.get("remediation_plan"):
        p = result["remediation_plan"]
        print(f"\n[AGENT 4 -- Remediation]")
        print(f"  Total actions: {len(p.actions)}")
        print(f"  Auto-executable: {p.auto_executable}")
        print(f"  Requires approval: {p.requires_approval}")
        for a in p.actions[:3]:
            print(f"  [{a.risk}] {a.description}")

    if result.get("postmortem"):
        pm = result["postmortem"]
        print(f"\n[AGENT 5 -- Postmortem]")
        print(f"  Title: {pm.title}")
        print(f"  Confirmed root cause: {pm.confirmed_root_cause[:100]}")
        print(f"  Lessons learned: {pm.lessons_learned[:2]}")
        print(f"  Time-to-detect: {pm.time_to_detect_minutes} min")
        print(f"  Time-to-resolve: {pm.time_to_resolve_minutes} min")

    print(f"\n[GRAPH] Resolved: {result.get('resolved', False)}")
    print("=" * 60)


if __name__ == "__main__":
    main()
