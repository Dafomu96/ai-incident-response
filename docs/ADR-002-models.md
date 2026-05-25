# ADR-002 — LLM model selection by task type

**Status:** Accepted
**Date:** May 2026
**Author:** David Font Munoz

---

## Context

The system has 5 agents with very different requirements in terms of latency, reasoning capability and cost. The simplest decision would be to use a single model for all agents, but this implies a negative trade-off on at least one of the three dimensions for each agent.

System constraints:

- **Agent 1 (Triage):** must classify severity in under 500ms. It is the system entry point and any latency here is directly perceived as system response time.
- **Agents 3, 4, 5:** need deep reasoning, reliable chain-of-thought, and structured outputs that pass strict Pydantic v2 validation on the first attempt.
- **RAG contextualization:** generates 50-100 tokens of context per chunk at ingestion time. With documents of several thousand tokens and 512-token chunks, a single ingestion can require dozens of calls. Cost accumulates quickly.
- **Resilience:** the system cannot depend on a single LLM provider.

---

## Decision

**Three different models per task type, with global fallback.**

| Agent | Model (development) | Model (production) | Criterion |
|---|---|---|---|
| Agent 1 -- Triage | Groq Llama 3.3 70B | Groq Llama 3.3 70B | Latency <500ms |
| Agents 3/4/5 | Groq Llama 3.3 70B | Claude Sonnet | Deep reasoning |
| RAG contextualization | Groq Llama 3.3 70B | Claude Haiku | Minimum cost per chunk |
| Global fallback | GPT-4o | GPT-4o | Resilience |

---

## Reasoning per model

### Groq Llama 3.3 70B -- Agent 1 (always)

Agent 1 performs a classification with explicit criteria (P1/P2/P3) over a structured input. It does not need deep reasoning -- it needs speed. Groq with Llama 3.3 70B responds in ~300ms thanks to its specialized hardware (LPU), well below the 500ms target. Claude Sonnet has a median latency of 1-3 seconds for structured responses, unacceptable for the entry point of an incident response system where every second counts.

### Claude Sonnet -- Agents 3, 4, 5 (production)

Agent 3 (Diagnostic Reasoner) is the core of the system. It must correlate logs, metrics, commits and pod status, query them against historical runbooks via RAG, and generate hypotheses ordered by probability with evidence. This is exactly the type of task where Claude Sonnet outperforms smaller models: multi-step reasoning, coherent chain-of-thought, and fidelity in complex structured outputs.

In internal evaluations, Llama 3.3 70B tends to anchor the diagnosis on the most obvious signal in the data, ignoring secondary signals. Claude Sonnet better integrates contradictory evidence and produces more nuanced hypotheses.

Structured outputs with Pydantic v2 are more reliable with Claude Sonnet -- fewer parsing errors requiring retry, which reduces total pipeline latency.

### Claude Haiku -- RAG contextualization (production)

Chunk contextualization (Contextual Retrieval) requires one call per chunk to generate 50-100 tokens of context. This task is simple: "describe what part of the document this chunk is". No deep reasoning needed. Claude Haiku at ~20x lower cost than Sonnet is the obvious choice. The savings are significant when ingesting large knowledge bases.

### GPT-4o -- Global fallback

If the Anthropic API is unavailable, the system automatically falls back to GPT-4o via retry logic with tenacity. This ensures service continuity during P1 incidents where waiting for a provider to recover is not an option.

---

## Development vs production

During development, all agents use Groq Llama 3.3 70B at zero cost on the free tier. This introduces a known bias in evaluations -- the model tends to diagnose "postgres driver update" regardless of incident type when signals are ambiguous.

Evaluation results with Groq (Top-3 accuracy: 62%) are the development baseline. With Claude Sonnet in production, significant improvements are expected in cases where the root cause requires integrating signals from multiple sources without a dominant clear signal.

This dev/prod distinction is deliberate and documented -- it is not a hidden limitation of the system.

---

## Discarded alternatives

**A single model for everything.** If Claude Sonnet is chosen for all agents, Agent 1 has latency >1s -- unacceptable. If Groq is chosen for everything, Agents 3/4/5 have lower diagnostic precision on complex cases. Task-specific selection is the only approach that optimizes all three dimensions simultaneously.

**Mixtral 8x7B.** Evaluated as an alternative to Llama 3.3 70B for Agent 1. Similar latency but worse structured output quality. Discarded.

**GPT-4o as primary model.** Higher latency and cost than Claude Sonnet without a clear advantage in the system's specific tasks. Kept as fallback for availability and reliability.

---

## Trade-offs accepted

**Operational complexity.** Multiple API keys, multiple configurations, multiple failure points. Offset by cost-latency-quality optimization per task and by fallback resilience.

**Dev/prod inconsistency.** Evaluation results in development are not directly comparable with production. Documented explicitly in the README and in the evaluation ADR.
