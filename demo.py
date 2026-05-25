"""
demo.py — Demo del sistema completo en un solo comando.

Uso:
  python demo.py

Muestra:
  1. Ingesta de runbooks en ChromaDB (si no están ya)
  2. Ejecución end-to-end de un incidente P1
  3. Mensaje HITL en Slack con botones Approve/Reject
  4. Resultados de evaluación del último run

Pensado para demos en entrevistas — output limpio y legible.
"""
import os
import sys
import time
from dotenv import load_dotenv
load_dotenv()
import warnings, os
warnings.filterwarnings("ignore")
os.environ["TF_CPP_MIN_LOG_LEVEL"] = "3"

# ── Colores para terminal ──────────────────────────────────────────────────────
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
    """Verifica que las variables de entorno necesarias están configuradas."""
    required = ["GROQ_API_KEY"]
    missing = [k for k in required if not os.getenv(k)]
    if missing:
        print(f"{C.RED}❌ Faltan variables de entorno: {', '.join(missing)}{C.END}")
        print(f"   Copia .env.example a .env y configura las keys.")
        sys.exit(1)

    optional = {
        "LANGSMITH_API_KEY": "LangSmith tracing",
        "SLACK_BOT_TOKEN": "HITL Slack real",
    }
    for key, feature in optional.items():
        if os.getenv(key):
            ok(f"{feature} configurado")
        else:
            warn(f"{feature} no configurado — modo mock")


def seed_if_needed():
    """Ingesta runbooks solo si ChromaDB está vacío."""
    from rag.chroma_store import get_collection
    collection = get_collection("runbooks")
    count = collection.count()
    if count == 0:
        info("ChromaDB vacío — ingestando 5 runbooks de ejemplo...")
        from rag.seed_runbooks import main as seed
        seed()
    else:
        ok(f"ChromaDB listo — {count} documentos en knowledge base")


def run_demo_incident():
    """Ejecuta el incidente de demo y retorna el resultado."""
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

    info(f"Alerta: {alert.service} — {alert.metric} = {alert.value}s (umbral: {alert.threshold}s)")
    info(f"Descripción: {alert.description}")

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
    """Muestra los resultados de forma legible."""

    if result_data.get("incident_report"):
        r = result_data["incident_report"]
        print(f"\n{C.BOLD}{C.BLUE}  AGENTE 1 — Monitor & Triage{C.END}")
        result("  Severidad", f"{C.YELLOW}{r.severity}{C.END}")
        result("  Escalar", "Sí" if r.escalate_to_full_graph else "No")
        result("  Razonamiento", r.classification_reasoning[:80] + "...")

    if result_data.get("diagnosis"):
        d = result_data["diagnosis"]
        print(f"\n{C.BOLD}{C.BLUE}  AGENTE 3 — Diagnostic Reasoner (Core){C.END}")
        result("  Causa raíz", d.top_hypothesis.hypothesis)
        result("  Confianza", f"{d.overall_confidence:.0%}")
        result("  Evidencias", str(d.top_hypothesis.evidence[:2]))
        result("  Rediagnosticar", "Sí" if d.requires_more_data else "No")

    if result_data.get("remediation_plan"):
        p = result_data["remediation_plan"]
        print(f"\n{C.BOLD}{C.BLUE}  AGENTE 4 — Remediation Planner{C.END}")
        result("  Acciones totales", len(p.actions))
        result("  Auto-ejecutables", p.auto_executable)
        result("  Requieren aprobación HITL", p.requires_approval)
        for a in p.actions:
            icon = "🔴" if str(a.risk) == "ActionRisk.HIGH" else "🟢"
            print(f"    {icon} [{a.risk}] {a.description}")

    if result_data.get("hitl_request"):
        h = result_data["hitl_request"]
        print(f"\n{C.BOLD}{C.BLUE}  HITL — Slack Notification{C.END}")
        result("  Canal", h.slack_channel)
        result("  Acción", h.action.description)
        result("  Comando", h.action.command)
        result("  Timeout", f"{h.timeout_minutes} minutos")

    if result_data.get("postmortem"):
        pm = result_data["postmortem"]
        print(f"\n{C.BOLD}{C.BLUE}  AGENTE 5 — Postmortem Writer{C.END}")
        result("  Título", pm.title)
        result("  Causa confirmada", pm.confirmed_root_cause[:80])
        result("  Time-to-detect", f"{pm.time_to_detect_minutes} min")
        result("  Time-to-resolve", f"{pm.time_to_resolve_minutes} min")
        result("  Lecciones", pm.lessons_learned[0] if pm.lessons_learned else "N/A")

    print(f"\n{C.BOLD}  ⏱  Tiempo total de ejecución: {elapsed:.1f}s{C.END}")
    print(f"{C.BOLD}  📊 LangSmith: https://eu.smith.langchain.com{C.END}")


def print_architecture():
    """Muestra el resumen de arquitectura al final."""
    print(f"""
{C.BOLD}{C.CYAN}  ARQUITECTURA{C.END}
  ┌─────────────────────────────────────────────────────┐
  │  Alerta → Monitor & Triage (Groq, <500ms)          │
  │       → Data Collector (asyncio.gather paralelo)    │
  │       → Diagnostic Reasoner (RAG + CoT)             │
  │            [confianza baja] → retry Data Collector  │
  │       → Remediation Planner (matriz LOW/HIGH)       │
  │            [HIGH] → HITL Slack bot                  │
  │       → Postmortem Writer → ingesta ChromaDB        │
  │                              (loop de aprendizaje)  │
  └─────────────────────────────────────────────────────┘
  Stack: LangGraph · Groq · ChromaDB · Pydantic v2
         FastAPI · Docker · LangSmith · Slack API
  Tests: 52 passed · CI/CD: GitHub Actions
""")


def main():
    header("AI INCIDENT RESPONSE SYSTEM — Demo")

    step(1, "Verificando configuración...")
    check_env()

    step(2, "Verificando knowledge base (ChromaDB)...")
    seed_if_needed()

    step(3, "Ejecutando incidente de demo — payment-service P1...")
    print()
    result_data, elapsed = run_demo_incident()

    step(4, "Resultados del pipeline completo:")
    print_results(result_data, elapsed)

    step(5, "Resumen de arquitectura:")
    print_architecture()

    header("DEMO COMPLETADA")
    ok("Sistema end-to-end funcionando")
    ok("5 agentes ejecutados correctamente")
    if result_data.get("remediation_plan") and result_data["remediation_plan"].requires_approval:
        ok("HITL enviado a Slack — revisa #incident-approvals")
    ok("Postmortem ingestado en ChromaDB (loop de aprendizaje)")
    if os.getenv("LANGSMITH_API_KEY"):
        ok("Traza completa disponible en LangSmith")
    print()


if __name__ == "__main__":
    main()
