# ADR-001 — LangGraph over crewAI and AutoGen

**Status:** Accepted
**Date:** May 2026
**Author:** David Font Munoz

---

## Context

When designing the incident response system we needed an agent orchestration framework. The three candidates evaluated were LangGraph, crewAI and AutoGen.

The system has a fundamental non-negotiable requirement: **the flow is not linear**. The Diagnostic Reasoner may determine it needs more data before producing a diagnosis with sufficient confidence, which requires returning to the Data Collector with an expanded time window. This is a conditional loop — the agent decides at runtime whether to advance or retry.

---

## Decision

**LangGraph.**

---

## Reasons

**crewAI** is optimized for linear pipelines with fixed roles: agent A passes to agent B passes to agent C. Internally crewAI orchestrates conversations between agents with predefined roles. It does not natively support conditional loops — implementing "return to Agent 2 if confidence is low" would require custom logic that goes against the framework's mental model.

**AutoGen** has an agent-to-agent conversation model (agents "talk" to each other) that introduces unnecessary latency and conversational complexity for a system that needs deterministic responses in seconds. AutoGen is designed for collaborative reasoning tasks, not for incident response pipelines where each node has a clear responsibility and a typed output.

**LangGraph** provides exactly the pattern this system needs:

- **Cyclic graph:** the conditional edge `route_after_diagnosis` can return `data_collector` if `diagnosis.requires_more_data = True`, creating the re-diagnosis loop natively
- **Typed state:** `IncidentState` (TypedDict) persists at each node and is accessible by all agents without manually passing data between them
- **Checkpointing:** if the system crashes mid P1 incident, the graph resumes exactly where it left off using `MemorySaver` (dev) or `SqliteSaver` (prod)
- **Explicit conditional edges:** `route_after_triage`, `route_after_diagnosis`, `route_after_planning` are pure Python functions — fully testable with pytest without LLM mocks
- **Dedicated error node:** captures exceptions at any point in the graph without leaving the state inconsistent

---

## Discarded alternatives

| Framework | Reason for rejection |
|---|---|
| crewAI | Does not natively support conditional loops -- linear pipeline only |
| AutoGen | Conversational model introduces unnecessary latency and non-determinism |
| LangChain LCEL | No persistent state between nodes, no checkpointing |
| Custom implementation | Reinventing checkpointing and distributed state is non-differentiating work |

---

## Trade-offs accepted

**Verbosity.** LangGraph requires explicitly defining nodes, edges, and state. The same pipeline in crewAI would be ~30% less code. This cost is acceptable because the verbosity makes the flow fully auditable -- any engineer can read `workflow.py` and understand exactly what the system does.

**Learning curve.** LangGraph has more advanced concepts (StateGraph, conditional edges, interrupt) than crewAI. For a team new to the framework, crewAI would be faster to onboard. In the context of this project, granular flow control justifies this cost.

---

## Consequences

- The 3 conditional edges in the graph are pure Python functions tested in `tests/test_state.py`
- Checkpointing enables fault recovery in P1 incidents without losing context
- The re-diagnosis loop (Agent 3 -> Agent 2 -> Agent 3) works natively without custom logic
