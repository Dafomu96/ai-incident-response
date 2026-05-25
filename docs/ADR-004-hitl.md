# ADR-004 — Human-in-the-Loop by action type, not incident severity

**Status:** Accepted
**Date:** May 2026
**Author:** David Font Munoz

---

## Context

The system needs to decide when a remediation action requires human approval before being executed. The design question is: what is the variable that determines whether an action needs human supervision?

Two possible approaches:

1. **By incident severity:** P1 and P2 require approval, P3 does not.
2. **By specific action risk:** reversible low-impact actions execute automatically, destructive or hard-to-reverse actions require approval.

---

## Decision

**Permission matrix by action type, independent of incident severity.**

```
ActionRisk.LOW  --> auto-executable
ActionRisk.HIGH --> HITLRequest --> Slack --> human approval
```

---

## Reasons

**HITL by severity is incoherent with the automation objective.**

If a P1 incident is solved by restarting a pod (reversible operation in 30 seconds), waiting for human approval adds minutes of downtime with no benefit. The pod gets restarted either way -- the only difference is that the production system has been down longer.

If a P2 incident is solved by a deployment rollback (operation that can introduce regressions and affects all users), executing it automatically without approval is risky even though the severity is "only P2".

Severity describes the impact of the incident. Action risk describes the impact of the remediation. They are orthogonal dimensions.

**The correct variable is the reversibility and blast radius of the action.**

`LOW risk` actions (auto-executable):
- `kubectl rollout restart deployment/<service>` -- reversible, impact localized to the service
- `kubectl exec -- redis-cli FLUSHDB` -- reversible at minimal cost (cache regeneration)
- `kubectl scale deployment/<service> --replicas=N` -- immediately reversible
- `kubectl exec -- logrotate -f` -- no service impact

`HIGH risk` actions (require approval):
- `kubectl rollout undo deployment/<service>` -- rollback may introduce regressions
- `kubectl delete pvc/<volume>` -- potential data loss
- modifying network policies -- security and connectivity impact across multiple services
- scaling infrastructure -- immediate financial cost

---

## Implementation

Agent 4 (Remediation Planner) classifies each action when generating it:

```python
class ActionRisk(str, Enum):
    LOW = "low"   # auto-executable
    HIGH = "high" # requires human approval
```

For HIGH actions, it generates a `HITLRequest` with full context:
- Action description and exact command to execute
- Diagnosis summary with Agent 3's confidence score
- 10-minute timeout with automatic escalation if no response

The message is sent to the `#incident-approvals` Slack channel with **Approve** and **Reject** buttons. The on-call engineer makes the decision with full context visible -- no need to look up additional information to approve or reject.

---

## Timeout and automatic escalation

If there is no response within 10 minutes (configurable via `HITLRequest.timeout_minutes`), the system escalates automatically. In the current implementation this means continuing with execution -- in production it could mean notifying a higher on-call level.

The timeout prevents the system from being blocked indefinitely waiting for an approval that never comes (engineer asleep, Slack down, etc.). A P1 incident cannot wait indefinitely.

---

## Audit log

All decisions -- approved, rejected, and auto-executed -- are recorded in the graph's `IncidentState` and traced in LangSmith. This enables:

- Post-incident review: who approved what and when
- Identifying actions incorrectly classified as LOW that should be HIGH
- Measuring time between HITLRequest sent and approval (on-call response time)

---

## Discarded alternatives

**HITL for all actions.** Eliminates the benefit of automation. If every action requires human approval, the system is a recommendation generator, not an autonomous agent. Resolution time would be similar to the current manual process.

**HITL by severity (P1/P2 yes, P3 no).** Incoherent -- a P3 with a rollback action is riskier than a P1 with a restart action. See main reasoning above.

**No HITL (fully autonomous).** Unacceptable for actions with data loss risk or security impact. In real production, a system that automatically executes rollbacks without human supervision would generate operational distrust regardless of its accuracy rate.

**HITL based on diagnosis confidence.** If Agent 3's confidence is < 80%, require approval. Discarded because it conflates diagnosis uncertainty with action risk -- they are different problems. A restart action is safe even if the diagnosis has 60% confidence. A rollback is risky even if the diagnosis has 99% confidence.

---

## Trade-offs accepted

**Agent 4's LOW/HIGH classification may be incorrect.** The LLM may classify a risky action as LOW in edge cases. The audit log allows identifying these cases and improving Agent 4's prompt. The risk is mitigated by the principle that when in doubt, Agent 4 should classify HIGH.

**Dependency on Slack availability.** If Slack is unavailable, HITL cannot complete. In production this requires a fallback channel (PagerDuty, email, SMS). In the current implementation the timeout ensures the system is not blocked indefinitely.
