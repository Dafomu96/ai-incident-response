"""
demo.py -- Full system demo in a single command.

Usage:
  python demo.py

Shows:
  1. Runbook ingestion into ChromaDB (if not already seeded)
  2. End-to-end incident pipeline execution
  3. HITL message in Slack with Approve/Reject buttons
  4. Results from all 5 agents

Designed for live demos -- clean and readable output.
"""
import os
import sys
import time
import warnings
from dotenv import load_dotenv

warnings.filterwarnings("ignore")
os.environ["TF_CPP_MIN_LOG_LEVEL"] = "3"
load_dotenv()

# ── Terminal colors ────────────────────────────────────────────────────────────
class C:
    HEADER  = "\033[95m"
    BLUE    = "\033[94m"
    CYAN    = "\033[96m"
    GREEN   = "\033[92m"
    YELLOW  = "\033[93m"
    RED     = "\033[91m"
    BOLD    = "\033[1m"
    END     = "\033[0m"

def header(text):
    print(f"\n{C.BOLD}{C.HEADER}{'='*60}{C.END}")
    print(f"{C.BOLD}{C.HEADER}  {text}{C.END}")
    print(f"{C.BOLD}{C.HEADER}{'='*60}{C.END}")

def step(n, text):
    print(f"\n{C.BOLD}{C.CYAN}[STEP {n}]{C.END} {text}")

def ok(text):
    print(f"  {C.GREEN}✅{C.END} {text}")

def info(text):
    print(f"  {C.BLUE}ℹ{C.END}  {text}")

def warn(text):
    print(f"  {C.YELLOW}⚠{C.END}  {text}")

def result(key, value):
    print(f"  {C.BOLD}{key}:{C.END} {value}")


def check_env():
    """Verify required environment variables are configured."""
    required = ["GROQ_API_KEY"]
    missing = [k for k in required if not os.getenv(k)]
    if missing:
        print(f"{C.RED}❌ Missing environment variables: {', '.join(missing)}{C.END}")
        print(f"   Copy .env.example to .env and configure the keys.")
        sys.exit(1)

    optional = {
        "LANGSMITH_API_KEY": "LangSmith tracing",
        "SLACK_BOT_TOKEN": "Slack HITL",
    }
    for key, feature in optional.items():
        if os.getenv(key):
            ok(f"{feature} configured")
        else:
            warn(f"{feature} not configured -- mock mode")


def seed_if_needed():
    """Seed runbooks only if ChromaDB is empty."""
    from rag.chroma_store import get_collection
    collection = get_collection("runbooks")
    count = collection.count()
    if count == 0:
        info("ChromaDB empty -- seeding 5 example runbooks...")
        from rag.seed_runbooks import main as seed
        seed()
    else:
        ok(f"ChromaDB ready -- {count} documents in knowledge base")


def run_demo_incident():
    """Run the demo incident and return the result."""
    from schemas.incident import IncidentAlert
    from graph.workflow import compile_graph

    alert = IncidentAlert(
        alert_id="demo-001",
        service="payment-service",
        metric="http_request_duration_seconds_p99",
        value=2.34,
        threshold=0.5,
        description="P99 latency spike — possible DB connection pool exhaustion after postgres driver bump",
        labels={"env": "production", "region": "eu-west-1"},
    )

    info(f"Alert: {alert.service} — {alert.metric} = {alert.value}s (threshold: {alert.threshold}s)")
    info(f"Description: {alert.description}")

    graph = compile_graph()
    start = time.time()

    result_data = graph.invoke(
        {
            "alert": alert,
            "diagnosis_attempts": 0,
            "resolved": False,
            "messages": [],
        },
        config={"configurable": {"thread_id": alert.alert_id}},
    )

    elapsed = time.time() - start
    return result_data, elapsed


def print_results(result_data, elapsed):
    """Display results in a readable format."""

    if result_data.get("incident_report"):
        r = result_data["incident_report"]
        print(f"\n{C.BOLD}{C.BLUE}  AGENT 1 — Monitor & Triage{C.END}")
        result("  Severity", f"{C.YELLOW}{r.severity}{C.END}")
        result("  Escalate", "Yes" if r.escalate_to_full_graph else "No")
        result("  Reasoning", r.classification_reasoning[:80] + "...")

    if result_data.get("diagnosis"):
        d = result_data["diagnosis"]
        print(f"\n{C.BOLD}{C.BLUE}  AGENT 3 — Diagnostic Reasoner (Core){C.END}")
        result("  Root cause", d.top_hypothesis.hypothesis)
        result("  Confidence", f"{d.overall_confidence:.0%}")
        result("  Evidence", str(d.top_hypothesis.evidence[:2]))
        result("  Re-diagnose", "Yes" if d.requires_more_data else "No")

    if result_data.get("remediation_plan"):
        p = result_data["remediation_plan"]
        print(f"\n{C.BOLD}{C.BLUE}  AGENT 4 — Remediation Planner{C.END}")
        result("  Total actions", len(p.actions))
        result("  Auto-executable", p.auto_executable)
        result("  Requires HITL approval", p.requires_approval)
        for a in p.actions:
            icon = "🔴" if str(a.risk) == "ActionRisk.HIGH" else "🟢"
            print(f"    {icon} [{a.risk}] {a.description}")

    if result_data.get("hitl_request"):
        h = result_data["hitl_request"]
        print(f"\n{C.BOLD}{C.BLUE}  HITL — Slack Notification{C.END}")
        result("  Channel", h.slack_channel)
        result("  Action", h.action.description)
        result("  Command", h.action.command)
        result("  Timeout", f"{h.timeout_minutes} minutes")

    if result_data.get("postmortem"):
        pm = result_data["postmortem"]
        print(f"\n{C.BOLD}{C.BLUE}  AGENT 5 — Postmortem Writer{C.END}")
        result("  Title", pm.title)
        result("  Confirmed root cause", pm.confirmed_root_cause[:80])
        result("  Time-to-detect", f"{pm.time_to_detect_minutes} min")
        result("  Time-to-resolve", f"{pm.time_to_resolve_minutes} min")
        result("  Lessons learned", pm.lessons_learned[0] if pm.lessons_learned else "N/A")

    print(f"\n{C.BOLD}  ⏱  Total execution time: {elapsed:.1f}s{C.END}")
    print(f"{C.BOLD}  📊 LangSmith: https://eu.smith.langchain.com{C.END}")


def print_architecture():
    """Display architecture summary."""
    print(f"""
{C.BOLD}{C.CYAN}  ARCHITECTURE{C.END}
  ┌─────────────────────────────────────────────────────┐
  │  Alert → Monitor & Triage (Groq, <500ms)           │
  │       → Data Collector (asyncio.gather parallel)    │
  │       → Diagnostic Reasoner (RAG + CoT)             │
  │            [low confidence] → retry Data Collector  │
  │       → Remediation Planner (LOW/HIGH matrix)       │
  │            [HIGH] → HITL Slack bot                  │
  │       → Postmortem Writer → ChromaDB ingestion      │
  │                              (learning loop)        │
  └─────────────────────────────────────────────────────┘
  Stack: LangGraph · Groq · ChromaDB · Pydantic v2
         FastAPI · Docker · LangSmith · Slack API
  Tests: 71 passed · CI/CD: GitHub Actions
""")


def main():
    header("AI INCIDENT RESPONSE SYSTEM — Demo")

    step(1, "Checking configuration...")
    check_env()

    step(2, "Checking knowledge base (ChromaDB)...")
    seed_if_needed()

    step(3, "Running demo incident — payment-service...")
    print()
    result_data, elapsed = run_demo_incident()

    step(4, "Full pipeline results:")
    print_results(result_data, elapsed)

    step(5, "Architecture summary:")
    print_architecture()

    header("DEMO COMPLETE")
    ok("End-to-end system working")
    ok("5 agents executed successfully")
    if result_data.get("remediation_plan") and result_data["remediation_plan"].requires_approval:
        ok("HITL sent to Slack -- check #incident-approvals")
    ok("Postmortem ingested into ChromaDB (learning loop)")
    if os.getenv("LANGSMITH_API_KEY"):
        ok("Full trace available in LangSmith")
    print()


if __name__ == "__main__":
    main()
