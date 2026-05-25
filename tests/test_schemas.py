"""
tests/test_schemas.py — Tests unitarios de los schemas Pydantic.
No requieren LLM ni APIs externas.
"""
import pytest
from datetime import datetime
from schemas.incident import IncidentAlert, IncidentReport, Severity
from schemas.diagnosis import DiagnosisResult, RootCauseHypothesis
from schemas.remediation import RemediationPlan, RemediationAction, HITLRequest, ActionRisk
from schemas.postmortem import PostmortemDraft, TimelineEvent


# ── Fixtures reutilizables ─────────────────────────────────────────────────────

@pytest.fixture
def sample_alert():
    return IncidentAlert(
        alert_id="test-001",
        service="payment-service",
        metric="http_request_duration_seconds_p99",
        value=2.34,
        threshold=0.5,
        description="P99 latency spike",
        labels={"env": "production", "region": "eu-west-1"},
    )


@pytest.fixture
def sample_report():
    return IncidentReport(
        alert_id="test-001",
        severity=Severity.P1,
        service="payment-service",
        affected_components=["postgres", "connection-pool"],
        time_window_minutes=120,
        escalate_to_full_graph=True,
        classification_reasoning="P99 latency 4.7x over threshold with DB errors in logs",
    )


@pytest.fixture
def sample_hypothesis():
    return RootCauseHypothesis(
        hypothesis="DB connection pool exhaustion due to slow query after index drop",
        probability=0.87,
        evidence=["ConnectionPoolExhaustedException in logs", "CPU spike on postgres-primary"],
        related_runbooks=["runbook-db-pool-001"],
    )


@pytest.fixture
def sample_diagnosis(sample_hypothesis):
    return DiagnosisResult(
        alert_id="test-001",
        hypotheses=[sample_hypothesis],
        top_hypothesis=sample_hypothesis,
        overall_confidence=0.87,
        data_sources_used=["loki", "prometheus", "github"],
        reasoning_chain="Logs show ConnectionPoolExhaustedException starting T-43min...",
        requires_more_data=False,
    )


# ── Tests IncidentAlert ────────────────────────────────────────────────────────

class TestIncidentAlert:
    def test_basic_creation(self, sample_alert):
        assert sample_alert.alert_id == "test-001"
        assert sample_alert.service == "payment-service"
        assert sample_alert.value == 2.34

    def test_timestamp_default(self, sample_alert):
        assert isinstance(sample_alert.timestamp, datetime)

    def test_labels_default_empty(self):
        alert = IncidentAlert(
            alert_id="x", service="svc", metric="m", value=1.0, threshold=0.5
        )
        assert alert.labels == {}


# ── Tests IncidentReport ───────────────────────────────────────────────────────

class TestIncidentReport:
    def test_requires_hitl_p1(self, sample_report):
        assert sample_report.requires_hitl is True

    def test_requires_hitl_p2(self, sample_report):
        sample_report.severity = Severity.P2
        assert sample_report.requires_hitl is True

    def test_no_hitl_p3(self, sample_report):
        sample_report.severity = Severity.P3
        assert sample_report.requires_hitl is False

    def test_severity_enum_values(self):
        assert Severity.P1 == "P1"
        assert Severity.P2 == "P2"
        assert Severity.P3 == "P3"


# ── Tests DiagnosisResult ──────────────────────────────────────────────────────

class TestDiagnosisResult:
    def test_confidence_range(self, sample_diagnosis):
        assert 0.0 <= sample_diagnosis.overall_confidence <= 1.0

    def test_hypothesis_probability_range(self, sample_hypothesis):
        assert 0.0 <= sample_hypothesis.probability <= 1.0

    def test_invalid_probability_raises(self):
        with pytest.raises(Exception):
            RootCauseHypothesis(
                hypothesis="test",
                probability=1.5,  # inválido
                evidence=[],
            )

    def test_requires_more_data_default_false(self, sample_diagnosis):
        assert sample_diagnosis.requires_more_data is False

    def test_top_hypothesis_matches_first(self, sample_diagnosis, sample_hypothesis):
        assert sample_diagnosis.top_hypothesis.hypothesis == sample_hypothesis.hypothesis


# ── Tests RemediationPlan ──────────────────────────────────────────────────────

class TestRemediationPlan:
    def test_action_risk_classification(self):
        low_action = RemediationAction(
            action_id="act-001",
            description="Restart payment-service pod",
            command="kubectl rollout restart deployment/payment-service",
            risk=ActionRisk.LOW,
            reversible=True,
            estimated_impact="~30s de downtime por pod",
        )
        high_action = RemediationAction(
            action_id="act-002",
            description="Rollback deployment to previous version",
            command="kubectl rollout undo deployment/payment-service",
            risk=ActionRisk.HIGH,
            reversible=True,
            estimated_impact="Rollback completo — pérdida de features del deploy actual",
        )
        assert low_action.risk == ActionRisk.LOW
        assert high_action.risk == ActionRisk.HIGH

    def test_plan_creation(self):
        plan = RemediationPlan(
            alert_id="test-001",
            actions=[],
            auto_executable=[],
            requires_approval=[],
            execution_order=[],
        )
        assert plan.alert_id == "test-001"
        assert isinstance(plan.created_at, datetime)


# ── Tests PostmortemDraft ──────────────────────────────────────────────────────

class TestPostmortemDraft:
    def test_to_rag_document(self):
        postmortem = PostmortemDraft(
            alert_id="test-001",
            title="DB Connection Pool Exhaustion — payment-service",
            severity="P1",
            service="payment-service",
            timeline=[
                TimelineEvent(
                    timestamp=datetime.utcnow(),
                    event="Alert fired: P99 latency > 500ms",
                    actor="prometheus",
                )
            ],
            confirmed_root_cause="Index drop caused full table scans, exhausting connection pool",
            contributing_factors=["Missing index on orders table", "No connection pool monitoring"],
            actions_taken=["Killed blocking queries", "Recreated index", "Restarted service"],
            lessons_learned=["Add index drop protection in CI", "Alert on pool utilization > 80%"],
            preventive_measures=["Pre-deploy index validation", "Connection pool dashboard"],
            time_to_detect_minutes=5.0,
            time_to_resolve_minutes=23.0,
        )
        doc = postmortem.to_rag_document()
        assert "payment-service" in doc
        assert "connection pool" in doc.lower()
        assert "P1" in doc

    def test_rag_document_is_string(self):
        pm = PostmortemDraft(
            alert_id="x", title="t", severity="P2", service="svc",
            timeline=[], confirmed_root_cause="cause",
            contributing_factors=[], actions_taken=[],
            lessons_learned=[], preventive_measures=[],
            time_to_detect_minutes=1.0, time_to_resolve_minutes=10.0,
        )
        assert isinstance(pm.to_rag_document(), str)
