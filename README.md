# AI Incident Response System

> Multi-agent system for automated detection, diagnosis, and remediation of infrastructure incidents. 5 specialized agents orchestrated with LangGraph, RAG over internal runbooks with Contextual Retrieval, Human-in-the-Loop via Slack, and continuous evaluation with LangSmith.

---

## Table of Contents

1. [Motivation](#1-motivation)
2. [Architecture](#2-architecture)
3. [The 5 Agents](#3-the-5-agents)
4. [Technical Stack](#4-technical-stack)
5. [Architecture Decision Records (ADRs)](#5-architecture-decision-records-adrs)
6. [Evaluation Results](#6-evaluation-results)
7. [Repository Structure](#7-repository-structure)
8. [Setup](#8-setup)
9. [Usage](#9-usage)
10. [Observability](#10-observability)

---

## 1. Motivation

SRE teams spend an average of 40-60 minutes identifying the root cause of a P1 incident. During that time, a production system can generate losses of tens of thousands of euros and affect thousands of users. The manual process has three structural problems:

**Context fragmentation.** Logs are in Loki, metrics in Prometheus, recent commits in GitHub, and pod status in Kubernetes. The on-call SRE must correlate these sources manually under pressure.

**Non-persistent knowledge.** Runbooks and historical postmortems exist but are not consulted systematically. Each incident is resolved from scratch without leveraging accumulated knowledge.

**High-risk decisions without full context.** The engineer approving a rollback at 3am does not always have access to the complete diagnosis that led to that recommendation.

This system addresses all three: it collects context in parallel, automatically queries the historical knowledge base, and presents high-risk decisions with all the context needed for an informed approval.

---

## 2. Architecture

### Full flow

```
Prometheus/PagerDuty Alert
         |
         v
+-----------------+
|  Agent 1        |  Groq Llama 3.3 70B -- P1/P2/P3 classification
|  Monitor &      |  Target latency: <500ms
|  Triage         |
+--------+--------+
         | [P1/P2: escalate] ----------- [P3 trivial: auto-resolve]
         v
+-----------------+
|  Agent 2        |  asyncio.gather -- parallel collection
|  Data           |  Loki (logs) + Prometheus (metrics) +
|  Collector      |  GitHub API (commits) + K8s API (pods)
+--------+--------+
         |
         v
+-----------------+
|  Agent 3        |  Groq Llama 3.3 70B (dev) / Claude Sonnet (prod)
|  Diagnostic     |  RAG over runbooks + historical postmortems
|  Reasoner  -----+--[low confidence]--> Agent 2 (retry, wider window)
|  (Core)         |  Chain-of-thought + Pydantic structured output
+--------+--------+
         | [confidence >= threshold]
         v
+-----------------+
|  Agent 4        |  Classifies actions by risk (LOW/HIGH)
|  Remediation    |  LOW: auto-executable
|  Planner        |  HIGH: generates HITLRequest for Slack approval
+--------+--------+
         |
    +----+----+
    |         |
    v         v
 [HIGH]    [LOW / auto]
 HITL       Auto
 Slack -->  execution
 approval   |
    +--------+
         |
         v
+-----------------+
|  Agent 5        |  Generates structured postmortem
|  Postmortem     |  Ingests into ChromaDB <-- Learning loop
|  Writer         |
+-----------------+
```

### LangGraph graph properties

**Persistent state.** `IncidentState` (typed TypedDict) is persisted at each node via checkpointing. If the system crashes mid-incident, it resumes exactly where it left off.

**Native cyclic loop.** If the Diagnostic Reasoner determines it needs more data (`requires_more_data=True`), the graph automatically returns to the Data Collector with an expanded time window. Maximum 2 retries to prevent infinite loops.

**Conditional edges.** Three explicit decision points in the graph: escalate or auto-resolve (after triage), re-diagnose or plan (after diagnosis), HITL or execute (after planning).

**Error recovery.** Dedicated `error` node that captures exceptions, logs them to LangSmith, and prevents the graph from entering an inconsistent state.

---

## 3. The 5 Agents

### Agent 1 -- Monitor & Triage (`agents/monitor_triage.py`)

**Role:** System entry point. First contact with the alert.

**Model:** Groq Llama 3.3 70B -- chosen for latency (<500ms), not reasoning capability.

**Responsibilities:** receives `IncidentAlert` from Prometheus or PagerDuty, classifies severity P1/P2/P3, extracts affected components and time window, decides whether to escalate to the full graph.

**Output:** `IncidentReport` -- severity, affected components, escalation flag, classification reasoning.

---

### Agent 2 -- Data Collector (`agents/data_collector.py`)

**Role:** Investigator. Collects full context in parallel.

**Model:** No LLM -- direct tool-calling to APIs only.

**Responsibilities:** Loki logs (last N hours), Prometheus metrics (error rate, p99 latency, CPU, memory), GitHub commits and PRs, Kubernetes pod status.

**Parallelism:** `asyncio.gather` -- all 4 sources queried simultaneously. All tools have automatic mock fallback when URL/token is not configured.

---

### Agent 3 -- Diagnostic Reasoner (`agents/diagnostic_reasoner.py`)

**Role:** Core of the project. The most complex agent in the system.

**Model:** Groq Llama 3.3 70B (dev) / Claude Sonnet (prod).

**Responsibilities:** reasons over the full collected context, queries the RAG knowledge base of runbooks and historical postmortems, generates root cause hypotheses ordered by probability with evidence, sets `requires_more_data=True` if confidence is low.

**Output:** `DiagnosisResult` with hypotheses, `overall_confidence`, full `reasoning_chain`.

---

### Agent 4 -- Remediation Planner (`agents/remediation_planner.py`)

**Role:** Translates the diagnosis into concrete actions.

**Model:** Groq Llama 3.3 70B (dev) / Claude Sonnet (prod).

**Permission matrix:**
- **LOW (auto-executable):** restart pod, clear cache, reload config, scale replicas
- **HIGH (requires approval):** rollback deployment, delete data, modify firewall

**Output:** `RemediationPlan` with classified actions + `HITLRequest` for high-risk actions.

---

### Agent 5 -- Postmortem Writer (`agents/postmortem_writer.py`)

**Role:** Closes the loop. Generates the postmortem and feeds back into the system.

**Model:** Groq Llama 3.3 70B (dev) / Claude Sonnet (prod).

**Key differentiator:** ingests the generated postmortem into ChromaDB so future diagnoses benefit from accumulated knowledge. Closed learning loop.

**Output:** `PostmortemDraft` + automatic ingestion into the RAG knowledge base.

---

## 4. Technical Stack

### Agent orchestration

| Component | Technology | Decision |
|---|---|---|
| Agent framework | LangGraph | Cyclic state, checkpointing, conditional edges |
| Graph state | Typed TypedDict | Static typing, mypy compatible |
| Checkpointing dev | MemorySaver | In-memory, no dependencies |
| Checkpointing prod | SqliteSaver | Persistence across restarts |

### LLM Models

| Agent | Model (dev) | Model (prod) | Criterion |
|---|---|---|---|
| Agent 1 (Triage) | Groq Llama 3.3 70B | Groq Llama 3.3 70B | Latency <500ms |
| Agents 3/4/5 | Groq Llama 3.3 70B | Claude Sonnet | Deep reasoning |
| RAG contextualization | Groq Llama 3.3 70B | Claude Haiku | Minimum cost per chunk |
| Global fallback | GPT-4o | GPT-4o | Resilience |

### RAG -- Knowledge Base

| Component | Technology | Decision |
|---|---|---|
| Vector store | ChromaDB | Local persistence, easy setup |
| Embeddings | sentence-transformers (all-MiniLM-L6-v2) | Open source, no per-call cost |
| Chunking | RecursiveCharacterTextSplitter | 512 tokens, 50 overlap |
| Contextualization | Contextual Retrieval (Anthropic) | +50-100 context tokens per chunk |
| Reranking | Cohere Rerank v3 | Improved retrieval precision (optional) |

### Schemas and validation

All implemented with **Pydantic v2** -- strict validation, native JSON Schema, retry logic on parsing errors: `IncidentAlert`, `IncidentReport`, `DiagnosisResult`, `RemediationPlan`, `HITLRequest`, `PostmortemDraft`.

### Infrastructure

| Component | Technology |
|---|---|
| API backend | FastAPI + WebSockets |
| Containerization | Docker + docker-compose |
| CI/CD | GitHub Actions |
| Observability | LangSmith |
| HITL | Slack bot with interactive buttons |

---

## 5. Architecture Decision Records (ADRs)

### ADR-001 -- LangGraph over crewAI

**Context:** LangGraph, crewAI and AutoGen were evaluated as orchestration frameworks.

**Decision:** LangGraph.

**Reasons:** Incidents have complex, non-linear state. The Diagnostic Reasoner may need to return to the Data Collector if diagnosis confidence is low. crewAI is optimized for linear pipelines with fixed roles and does not natively support conditional loops. LangGraph provides exactly the pattern this system needs: cyclic graph with typed state, checkpointing for fault recovery, and conditional edges for explicit, testable decision logic.

**Trade-off:** More verbose code and steeper learning curve than crewAI. Acceptable in exchange for granular flow control.

---

### ADR-002 -- Three models with task-specific criteria

**Context:** A single model could be used for all agents.

**Decision:** Different models per task type.

**Reasons:** Agent 1 needs latency below 500ms -- Groq with Llama 3.3 70B responds in ~300ms. Agents 3, 4 and 5 need deep reasoning and reliable structured outputs -- Claude Sonnet in production. Claude Haiku for RAG chunk contextualization where hundreds of small calls are generated. GPT-4o as global fallback.

**Trade-off:** Higher operational complexity (multiple API keys). Offset by cost-latency-quality optimization per task.

---

### ADR-003 -- Contextual Retrieval over classic RAG

**Context:** Classic RAG (chunk -> embedding -> retrieval) was initially implemented.

**Decision:** Contextual Retrieval (Anthropic, September 2024).

**Reasons:** Operational runbooks lose meaning when split into 512-token chunks. Contextual Retrieval adds 50-100 LLM-generated context tokens to each chunk before embedding. According to Anthropic benchmarks, this reduces retrieval errors by up to 67% vs classic RAG.

**Trade-off:** Additional ingestion cost (one-time per document, not per retrieval). Offset by improved diagnostic precision.

---

### ADR-004 -- HITL by action risk, not incident severity

**Context:** Whether to implement HITL for all incidents or only some.

**Decision:** Permission matrix by action type, independent of incident severity.

**Reasons:** Severity describes incident impact. Action risk describes remediation impact. They are orthogonal dimensions. A reversible action (restart pod) is safe to auto-execute even in a P1. A destructive action (rollback deployment) requires human approval even in a P2.

**Trade-off:** Agent 4's LOW/HIGH classification may be wrong in edge cases. The immutable audit log of all decisions allows identifying and correcting these cases.

---

### ADR-005 -- Custom evaluation over RAGAS

**Context:** RAGAS is the standard framework for RAG system evaluation.

**Decision:** Direct evaluation against ground truth with LangSmith and custom metrics.

**Reasons:** RAGAS has dependency conflicts with LangGraph 0.2+ in Python 3.11 and adds LLM cost per evaluation. Direct evaluation against a dataset of 8 historical incidents with real root causes is more relevant than abstract faithfulness metrics. Metrics implemented: top-1 accuracy, top-3 accuracy, keyword overlap score, severity accuracy, HITL rate, time-to-diagnose.

---

## 6. Evaluation Results

Evaluation over **8 historical incidents** with real ground truth (root cause, severity, correct actions). Model: Groq Llama 3.3 70B (development).

| Metric | Result | Production target |
|---|---|---|
| Severity accuracy | 62% | >85% |
| Top-1 diagnostic accuracy | 38% | >70% |
| Top-3 diagnostic accuracy | 62% | >90% |
| Avg keyword score | 23% | >50% |
| Avg confidence | 84% | -- |
| HITL trigger rate | 100% | -- |
| Postmortem rate | 100% | -- |
| Avg diagnosis attempts | 1.0 | -- |
| Time-to-diagnose (avg) | ~7s | <30s |

**Analysis:** The system correctly diagnoses incidents with clear signals in logs and commits (DB connection pool, N+1 queries, Elasticsearch). It struggles with infrastructure incidents without code signals (expired SSL, full disk) where the GitHub mock provides no differential context. The dev/prod gap closes with Claude Sonnet, which has better reasoning over ambiguous signals.

**LangSmith observability:** Each execution generates a full trace with input/output per node, token usage, and latency. Typical execution: ~5.5s, ~5.1K tokens.

---

## 7. Repository Structure

```
ai-incident-response/
|-- agents/                     # The 5 LangGraph agents
|   |-- monitor_triage.py       # Agent 1: P1/P2/P3 classification with Groq
|   |-- data_collector.py       # Agent 2: parallel collection with asyncio
|   |-- diagnostic_reasoner.py  # Agent 3: RAG + chain-of-thought (core)
|   |-- remediation_planner.py  # Agent 4: remediation plan + HITL trigger
|   `-- postmortem_writer.py    # Agent 5: postmortem + RAG ingestion
|
|-- graph/                      # LangGraph orchestration
|   |-- state.py                # IncidentState -- typed TypedDict
|   |-- workflow.py             # StateGraph + conditional edges
|   `-- checkpointer.py         # MemorySaver (dev) / SqliteSaver (prod)
|
|-- tools/                      # Tool-calling to external APIs
|   |-- prometheus.py           # Historical metrics (service-specific mock)
|   |-- loki.py                 # Logs for last N hours (service-specific mock)
|   |-- github_api.py           # Recent commits and PRs (service-specific mock)
|   |-- kubernetes_api.py       # Pod status (with mock)
|   `-- slack_hitl.py           # Slack bot HITL with Approve/Reject buttons
|
|-- rag/                        # RAG pipeline with Contextual Retrieval
|   |-- ingestion.py            # Chunking + contextualization + embedding
|   |-- retriever.py            # Dense search + optional Cohere reranker
|   |-- chroma_store.py         # ChromaDB singleton
|   `-- seed_runbooks.py        # 5 example runbooks for initial ingestion
|
|-- schemas/                    # Pydantic v2 -- typed structured outputs
|   |-- incident.py             # IncidentAlert + IncidentReport
|   |-- diagnosis.py            # DiagnosisResult + RootCauseHypothesis
|   |-- remediation.py          # RemediationPlan + HITLRequest
|   `-- postmortem.py           # PostmortemDraft + to_rag_document()
|
|-- evals/                      # Evaluation with LangSmith + ground truth
|   |-- datasets/
|   |   `-- historical_incidents.json   # 8 incidents with real root causes
|   |-- run_evals.py            # Evaluation runner
|   |-- metrics.py              # Top-1/3 accuracy, keyword score, severity accuracy
|   `-- results_latest.json     # Latest evaluation results
|
|-- api/                        # FastAPI backend
|   `-- main.py                 # REST + WebSocket + /slack/actions callback
|
|-- frontend/                   # React + Vite dashboard
|   `-- src/App.jsx             # Live pipeline log, HITL queue, eval metrics
|
|-- infra/                      # Infrastructure
|   |-- Dockerfile
|   `-- docker-compose.yml
|
|-- .github/workflows/
|   `-- ci.yml                  # Tests + lint + Docker build on each push
|
|-- docs/                       # Architecture Decision Records
|   |-- ADR-001-langgraph.md
|   |-- ADR-002-models.md
|   |-- ADR-003-contextual-retrieval.md
|   |-- ADR-004-hitl.md
|   `-- ADR-005-evaluation.md
|
|-- tests/                      # 71 tests -- schemas, routing, tools, HITL, API, integration
|   |-- test_schemas.py
|   |-- test_state.py
|   |-- test_tools_mock.py
|   |-- test_hitl.py
|   `-- test_data_collector.py
|
|-- demo.py                     # Single-command demo script
|-- run_incident.py             # End-to-end test script
|-- pyproject.toml
|-- .env.example
`-- README.md
```

---

## 8. Setup

### Requirements

- Python 3.11+
- Docker Desktop (for containerized execution)
- Node.js 18+ (for frontend dashboard)

### Installation

```bash
# 1. Clone the repository
git clone https://github.com/Dafomu96/ai-incident-response.git
cd ai-incident-response

# 2. Virtual environment and dependencies
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
pip install langchain-text-splitters python-multipart

# 3. Environment variables
cp .env.example .env
# Edit .env -- minimum: GROQ_API_KEY

# 4. Seed runbooks into ChromaDB
python -m rag.seed_runbooks

# 5. Run the demo
python demo.py
```

### Minimum environment variables for development

```bash
GROQ_API_KEY=gsk_...              # Required -- all agents
LANGSMITH_API_KEY=lsv2_pt_...     # Recommended -- observability
LANGCHAIN_TRACING_V2=true
LANGCHAIN_ENDPOINT=https://eu.api.smith.langchain.com
LANGCHAIN_PROJECT=ai-incident-response
SLACK_BOT_TOKEN=xoxb-...          # Optional -- real HITL
SLACK_HITL_CHANNEL=#incident-approvals
```

> All external tools (Prometheus, Loki, GitHub, K8s) have automatic service-specific mocks when URL/token is not configured. The system runs end-to-end with only `GROQ_API_KEY`.

### Docker

```bash
docker-compose -f infra/docker-compose.yml up --build
# API available at http://localhost:8000
```

### Frontend dashboard

```bash
cd frontend
npm install
npm run dev
# Dashboard at http://localhost:3000
```

---

## 9. Usage

### Single-command demo

```bash
python demo.py
```

Runs the full pipeline with a sample P2 incident, shows all 5 agents executing, sends HITL to Slack if applicable, and displays results with colored output.

### End-to-end test

```python
from schemas.incident import IncidentAlert
from graph.workflow import compile_graph

alert = IncidentAlert(
    alert_id="inc-001",
    service="payment-service",
    metric="http_request_duration_seconds_p99",
    value=2.34,
    threshold=0.5,
    description="P99 latency spike -- possible DB connection pool exhaustion",
    labels={"env": "production", "region": "eu-west-1"},
)

graph = compile_graph()
result = graph.invoke(
    {"alert": alert, "diagnosis_attempts": 0, "resolved": False, "messages": []},
    config={"configurable": {"thread_id": alert.alert_id}},
)

print(result["incident_report"].severity)            # P2
print(result["diagnosis"].top_hypothesis.hypothesis) # root cause
print(result["diagnosis"].overall_confidence)        # 0.90
print(result["remediation_plan"].requires_approval)  # HIGH risk actions
```

### REST API

```bash
# Trigger incident
curl -X POST http://localhost:8000/incident \
  -H "Content-Type: application/json" \
  -d '{"alert_id": "inc-001", "service": "payment-service",
       "metric": "error_rate", "value": 0.45, "threshold": 0.05,
       "description": "Critical error rate spike"}'

# Get incident status
curl http://localhost:8000/incident/inc-001

# Health check
curl http://localhost:8000/health
```

### Evaluation

```bash
# Evaluate single incident
python -m evals.run_evals --incident hist-001

# Evaluate all 8 incidents
python -m evals.run_evals

# Results saved to evals/results_latest.json
```

### Tests

```bash
pytest tests/ -v           # 71 tests
pytest tests/ --cov=.      # with coverage
```

---

## 10. Observability

### LangSmith

Every graph execution generates a full trace with input/output per node, token usage per agent, latency, and errors. Set `LANGCHAIN_TRACING_V2=true` and `LANGSMITH_API_KEY` to enable.

Typical trace metrics:

- Total: ~5.5s, ~5.1K tokens
- monitor_triage: 0.82s, 643 tokens
- diagnostic_reasoner: 1.77s, 2.3K tokens
- remediation_planner: 1.02s, 879 tokens
- postmortem_writer: 1.51s, 1.3K tokens

### HITL -- Slack bot

When Agent 4 generates a HIGH risk action, the bot sends to `#incident-approvals`:

- Action description and risk level
- Diagnosis summary with confidence score
- Exact command to execute
- **Approve** / **Reject** buttons
- Auto-escalation after 10 minutes with no response

---

## Author

**David Font Munoz** -- AI/ML Engineer
[GitHub](https://github.com/Dafomu96) · [GitLab](https://gitlab.com/Dafomu96) · [LinkedIn](https://linkedin.com/in/davidfontmunoz)

---


