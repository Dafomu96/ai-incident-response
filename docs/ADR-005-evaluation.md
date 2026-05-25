# ADR-005 — Custom evaluation with LangSmith over RAGAS

**Status:** Accepted
**Date:** May 2026
**Author:** David Font Munoz

---

## Context

Evaluating an agentic RAG system requires measuring two distinct things: retrieval quality (are the right chunks being retrieved?) and final output quality (is the diagnosis correct?). RAGAS is the standard framework in the LangChain ecosystem for this.

During the evaluation system design, RAGAS and a custom LangSmith implementation were assessed.

---

## The problem with RAGAS in this context

RAGAS has three concrete problems for this project:

**Dependency conflicts.** RAGAS requires specific versions of `datasets` and `langchain` that are incompatible with LangGraph 0.2+ in Python 3.11. The conflict manifests at installation time and has no clean solution without degrading one of the two libraries. In a production system, forcing incompatible versions to satisfy an evaluation library is unacceptable.

**Cost per evaluation.** RAGAS's main metrics (faithfulness, answer relevancy, context precision) require additional LLM calls per evaluation. Evaluating 8 incidents with RAGAS would generate ~40-60 additional LLM calls on top of the main pipeline calls. With a 100k tokens/day limit on Groq's free tier, this consumes a significant portion of the daily budget.

**Abstract metrics vs business metrics.** Faithfulness measures whether the LLM output is supported by the retrieved context. Context precision measures whether retrieved chunks are relevant to the query. These metrics are useful for general Q&A RAG systems, but for an incident response system the metric that matters is: **did the system correctly diagnose the root cause?** This question can only be answered with real ground truth, not with proxy metrics.

---

## Decision

**Direct evaluation against historical ground truth with LangSmith and custom metrics.**

---

## Ground truth dataset

`evals/datasets/historical_incidents.json` contains 8 real incidents with:

```json
{
  "alert_id": "hist-001",
  "alert": { ... },
  "ground_truth": {
    "severity": "P2",
    "root_cause": "DB connection pool exhaustion due to slow query after index drop",
    "root_cause_keywords": ["connection pool", "database", "postgres", "query", "driver"],
    "correct_actions": ["kill_blocking_queries", "recreate_index", "restart_service"]
  }
}
```

The ground truth includes the textual root cause, keywords that should appear in the diagnosis, and the correct remediation actions.

---

## Implemented metrics

**Keyword overlap score.** Measures what fraction of the ground truth keywords appear in Agent 3's top-1 hypothesis. Simple, deterministic, no additional LLM calls.

```python
def keyword_overlap_score(hypothesis: str, keywords: list[str]) -> float:
    hypothesis_lower = hypothesis.lower()
    matches = sum(1 for kw in keywords if kw.lower() in hypothesis_lower)
    return matches / len(keywords)
```

**Top-1 accuracy.** Agent 3's most probable hypothesis exceeds the keyword overlap threshold (0.25).

**Top-3 accuracy.** At least one of the 3 first hypotheses exceeds the threshold. More permissive -- measures whether the system considers the correct root cause even if it is not ranked first.

**Severity accuracy.** The severity classified by Agent 1 matches the ground truth.

**System metrics.** HITL trigger rate (what percentage of incidents generate a human approval), postmortem rate (always 100% if the pipeline completes), avg diagnosis attempts (indicates whether the re-diagnosis loop activates).

---

## Current results

Evaluation over 8 incidents with Groq Llama 3.3 70B (development model):

| Metric | Result |
|---|---|
| Severity accuracy | 62% |
| Top-1 accuracy | 38% |
| Top-3 accuracy | 62% |
| Avg keyword score | 23% |
| HITL trigger rate | 100% |
| Postmortem rate | 100% |

**Honest analysis of results:** the development model (Groq Llama 3.3 70B) has a known bias toward "postgres driver update" as root cause in incidents with ambiguous signals, because the GitHub mock data always includes a postgres driver commit. In incidents with clear and specific signals (N+1 query in inventory-service, Elasticsearch node failure in search-service) Top-1 is correct. With Claude Sonnet in production and real per-service data, significant improvements are expected in edge cases.

---

## LangSmith as observability platform

All evaluation executions are traced in LangSmith with:

- Full input of each node (alert, logs, metrics, commits)
- Output of each agent (IncidentReport, DiagnosisResult, RemediationPlan, PostmortemDraft)
- Token usage and latency per agent
- Comparison between executions to detect regressions

This enables A/B testing between versions of the Diagnostic Reasoner -- changing the prompt, model, or retrieval strategy and comparing results on the same ground truth dataset.

---

## Discarded alternatives

**RAGAS.** Discarded due to the three problems described above: dependency conflicts, cost per evaluation, and abstract metrics that do not answer the business question.

**Manual evaluation.** Reading Agent 3 outputs and judging whether they are correct. Not scalable, not reproducible, not automatable in CI/CD.

**LLM-as-judge.** Using an LLM to evaluate whether the diagnosis is correct by comparing it with the ground truth. Adds cost and non-determinism. Appropriate when there is no structured ground truth -- in this case there is.

---

## Trade-offs accepted

**Keyword overlap is an imperfect metric.** A correct diagnosis phrased with synonyms may score 0%. An incorrect diagnosis that casually mentions the keywords may score high. To mitigate this, Top-3 accuracy is used alongside Top-1, and the threshold was calibrated empirically (0.25) to minimize false negatives.

**The 8-incident dataset is small.** It is not statistically representative. The objective is to have a reproducible baseline for detecting regressions between versions, not to measure the system's absolute precision. For a robust production evaluation dataset, 50-100 real historical incidents would be needed.
