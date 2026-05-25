"""
tests/test_state.py — Tests del IncidentState y el grafo LangGraph.
Verifica que el estado se construye correctamente y el grafo compila.
No requieren LLM — usan mocks.
"""
import pytest
from unittest.mock import patch, MagicMock
from schemas.incident import IncidentAlert, IncidentReport, Severity
from graph.state import IncidentState
from graph.workflow import build_graph, compile_graph, route_after_triage, route_after_diagnosis, route_after_planning
from schemas.diagnosis import DiagnosisResult, RootCauseHypothesis
from schemas.remediation import RemediationPlan


# ── Fixtures ───────────────────────────────────────────────────────────────────

@pytest.fixture
def base_alert():
    return IncidentAlert(
        alert_id="state-test-001",
        service="payment-service",
        metric="error_rate",
        value=0.15,
        threshold=0.05,
    )


@pytest.fixture
def p1_report(base_alert):
    return IncidentReport(
        alert_id=base_alert.alert_id,
        severity=Severity.P1,
        service=base_alert.service,
        escalate_to_full_graph=True,
        classification_reasoning="High error rate",
    )


@pytest.fixture
def p3_report(base_alert):
    return IncidentReport(
        alert_id=base_alert.alert_id,
        severity=Severity.P3,
        service=base_alert.service,
        escalate_to_full_graph=False,
        classification_reasoning="Minor anomaly, auto-recoverable",
    )


@pytest.fixture
def confident_diagnosis():
    hyp = RootCauseHypothesis(
        hypothesis="DB connection pool exhaustion",
        probability=0.90,
        evidence=["ConnectionPoolExhaustedException in logs"],
    )
    return DiagnosisResult(
        alert_id="state-test-001",
        hypotheses=[hyp],
        top_hypothesis=hyp,
        overall_confidence=0.90,
        data_sources_used=["loki", "prometheus"],
        reasoning_chain="...",
        requires_more_data=False,
    )


@pytest.fixture
def low_confidence_diagnosis():
    hyp = RootCauseHypothesis(
        hypothesis="Unknown network issue",
        probability=0.40,
        evidence=["Some packet loss"],
    )
    return DiagnosisResult(
        alert_id="state-test-001",
        hypotheses=[hyp],
        top_hypothesis=hyp,
        overall_confidence=0.40,
        data_sources_used=["prometheus"],
        reasoning_chain="...",
        requires_more_data=True,
    )


# ── Tests routing condicional ──────────────────────────────────────────────────

class TestRouting:
    def test_triage_escalates_p1(self, base_alert, p1_report):
        state = {"alert": base_alert, "incident_report": p1_report}
        assert route_after_triage(state) == "data_collector"

    def test_triage_no_escalate_p3(self, base_alert, p3_report):
        from langgraph.graph import END
        state = {"alert": base_alert, "incident_report": p3_report}
        assert route_after_triage(state) == END

    def test_triage_none_report_returns_error(self, base_alert):
        state = {"alert": base_alert, "incident_report": None}
        assert route_after_triage(state) == "error"

    def test_diagnosis_confident_goes_to_planning(self, confident_diagnosis):
        state = {"diagnosis": confident_diagnosis, "diagnosis_attempts": 1}
        assert route_after_diagnosis(state) == "remediation_planner"

    def test_diagnosis_low_confidence_retries(self, low_confidence_diagnosis):
        state = {"diagnosis": low_confidence_diagnosis, "diagnosis_attempts": 0}
        assert route_after_diagnosis(state) == "data_collector"

    def test_diagnosis_max_retries_goes_to_planning(self, low_confidence_diagnosis):
        # Después de 2 intentos, avanza aunque la confianza sea baja
        state = {"diagnosis": low_confidence_diagnosis, "diagnosis_attempts": 2}
        assert route_after_diagnosis(state) == "remediation_planner"

    def test_planning_with_approval_goes_to_hitl(self):
        plan = RemediationPlan(
            alert_id="test",
            actions=[],
            auto_executable=[],
            requires_approval=["act-001"],  # hay acciones que necesitan aprobación
            execution_order=[],
        )
        state = {"remediation_plan": plan}
        assert route_after_planning(state) == "hitl_node"

    def test_planning_no_approval_goes_to_execute(self):
        plan = RemediationPlan(
            alert_id="test",
            actions=[],
            auto_executable=["act-001"],
            requires_approval=[],  # todo auto-ejecutable
            execution_order=[],
        )
        state = {"remediation_plan": plan}
        assert route_after_planning(state) == "execute_remediation"


# ── Tests compilación del grafo ────────────────────────────────────────────────

class TestGraphCompilation:
    def test_graph_builds_without_error(self):
        """El grafo se construye sin errores de configuración."""
        graph = build_graph()
        assert graph is not None

    def test_graph_compiles_with_memory_saver(self):
        """El grafo compila con MemorySaver (modo desarrollo)."""
        compiled = compile_graph()
        assert compiled is not None

    def test_graph_has_correct_nodes(self):
        """Verifica que los 5 agentes + nodos de control están presentes."""
        graph = build_graph()
        # LangGraph expone los nodos en el builder
        expected_nodes = {
            "monitor_triage", "data_collector", "diagnostic_reasoner",
            "remediation_planner", "postmortem_writer",
            "hitl_node", "execute_remediation", "error"
        }
        assert expected_nodes.issubset(set(graph.nodes))
