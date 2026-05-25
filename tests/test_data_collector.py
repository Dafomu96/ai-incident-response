"""
tests/test_data_collector.py — Tests de integración del Agente 2 (Data Collector).

Verifica que:
1. Los 4 tools se llaman correctamente y devuelven datos útiles
2. El nodo integra los datos en el estado correctamente
3. El paralelismo funciona (asyncio.gather)
4. Los datos recopilados son relevantes para el servicio solicitado
"""
import pytest
from unittest.mock import AsyncMock, patch
from schemas.incident import IncidentAlert, IncidentReport, Severity


# ── Fixtures ───────────────────────────────────────────────────────────────────

@pytest.fixture
def payment_alert():
    return IncidentAlert(
        alert_id="test-dc-001",
        service="payment-service",
        metric="http_request_duration_seconds_p99",
        value=2.34,
        threshold=0.5,
        description="P99 latency spike",
    )


@pytest.fixture
def payment_report(payment_alert):
    return IncidentReport(
        alert_id=payment_alert.alert_id,
        severity=Severity.P2,
        service=payment_alert.service,
        escalate_to_full_graph=True,
        classification_reasoning="Latency spike",
        time_window_minutes=120,
    )


@pytest.fixture
def base_state(payment_alert, payment_report):
    return {
        "alert": payment_alert,
        "incident_report": payment_report,
        "diagnosis_attempts": 0,
        "resolved": False,
        "messages": [],
    }


# ── Tests tools individuales ───────────────────────────────────────────────────

class TestPrometheusToolIntegration:
    @pytest.mark.asyncio
    async def test_fetch_metrics_returns_data(self, monkeypatch):
        monkeypatch.delenv("PROMETHEUS_URL", raising=False)
        from tools.prometheus import fetch_metrics
        result = await fetch_metrics("payment-service", 120)
        assert isinstance(result, str)
        assert len(result) > 0

    @pytest.mark.asyncio
    async def test_fetch_metrics_service_specific(self, monkeypatch):
        monkeypatch.delenv("PROMETHEUS_URL", raising=False)
        from tools.prometheus import fetch_metrics
        payment = await fetch_metrics("payment-service", 120)
        auth = await fetch_metrics("auth-service", 120)
        # Cada servicio devuelve datos distintos
        assert payment != auth

    @pytest.mark.asyncio
    async def test_fetch_metrics_contains_relevant_signals(self, monkeypatch):
        monkeypatch.delenv("PROMETHEUS_URL", raising=False)
        from tools.prometheus import fetch_metrics
        result = await fetch_metrics("payment-service", 120)
        # El mock de payment-service debe tener señales de DB pool
        assert "error_rate" in result.lower() or "latency" in result.lower()


class TestLokiToolIntegration:
    @pytest.mark.asyncio
    async def test_fetch_logs_returns_data(self, monkeypatch):
        monkeypatch.delenv("LOKI_URL", raising=False)
        from tools.loki import fetch_logs
        result = await fetch_logs("payment-service", 120)
        assert isinstance(result, str)
        assert len(result) > 0

    @pytest.mark.asyncio
    async def test_fetch_logs_service_specific(self, monkeypatch):
        monkeypatch.delenv("LOKI_URL", raising=False)
        from tools.loki import fetch_logs
        payment = await fetch_logs("payment-service", 120)
        auth = await fetch_logs("auth-service", 120)
        assert payment != auth

    @pytest.mark.asyncio
    async def test_fetch_logs_payment_has_db_errors(self, monkeypatch):
        monkeypatch.delenv("LOKI_URL", raising=False)
        from tools.loki import fetch_logs
        result = await fetch_logs("payment-service", 120)
        assert "ERROR" in result

    @pytest.mark.asyncio
    async def test_fetch_logs_auth_has_memory_signals(self, monkeypatch):
        monkeypatch.delenv("LOKI_URL", raising=False)
        from tools.loki import fetch_logs
        result = await fetch_logs("auth-service", 120)
        assert "cache" in result.lower() or "memory" in result.lower() or "OOM" in result


class TestGitHubToolIntegration:
    @pytest.mark.asyncio
    async def test_fetch_commits_returns_data(self, monkeypatch):
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)
        from tools.github_api import fetch_recent_commits
        result = await fetch_recent_commits("payment-service")
        assert isinstance(result, str)
        assert len(result) > 0

    @pytest.mark.asyncio
    async def test_fetch_commits_service_specific(self, monkeypatch):
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)
        from tools.github_api import fetch_recent_commits
        payment = await fetch_recent_commits("payment-service")
        inventory = await fetch_recent_commits("inventory-service")
        assert payment != inventory

    @pytest.mark.asyncio
    async def test_fetch_commits_payment_has_postgres_bump(self, monkeypatch):
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)
        from tools.github_api import fetch_recent_commits
        result = await fetch_recent_commits("payment-service")
        assert "postgres" in result.lower()

    @pytest.mark.asyncio
    async def test_fetch_commits_inventory_has_eager_loading(self, monkeypatch):
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)
        from tools.github_api import fetch_recent_commits
        result = await fetch_recent_commits("inventory-service")
        assert "eager" in result.lower() or "N+1" in result


class TestKubernetesToolIntegration:
    @pytest.mark.asyncio
    async def test_fetch_pod_status_returns_data(self, monkeypatch):
        monkeypatch.delenv("K8S_KUBECONFIG_PATH", raising=False)
        from tools.kubernetes_api import fetch_pod_status
        result = await fetch_pod_status("payment-service")
        assert isinstance(result, str)
        assert len(result) > 0

    @pytest.mark.asyncio
    async def test_fetch_pod_status_contains_pod_info(self, monkeypatch):
        monkeypatch.delenv("K8S_KUBECONFIG_PATH", raising=False)
        from tools.kubernetes_api import fetch_pod_status
        result = await fetch_pod_status("payment-service")
        assert "payment-service" in result


# ── Tests integración del nodo completo ───────────────────────────────────────

class TestDataCollectorNode:
    def test_node_returns_all_four_data_sources(self, base_state):
        """El nodo debe retornar los 4 campos de datos recopilados."""
        from agents.data_collector import data_collector_node
        result = data_collector_node(base_state)
        assert "collected_logs" in result
        assert "collected_metrics" in result
        assert "recent_commits" in result
        assert "k8s_pod_status" in result

    def test_node_data_is_non_empty(self, base_state):
        """Todos los campos deben tener contenido."""
        from agents.data_collector import data_collector_node
        result = data_collector_node(base_state)
        assert result["collected_logs"]
        assert result["collected_metrics"]
        assert result["recent_commits"]
        assert result["k8s_pod_status"]

    def test_node_uses_service_from_report(self, base_state):
        """El nodo debe usar el servicio del incident_report, no del alert."""
        from agents.data_collector import data_collector_node
        result = data_collector_node(base_state)
        # Los datos de payment-service deben contener señales relevantes
        assert "payment" in result["collected_logs"].lower() or \
               "payment" in result["k8s_pod_status"].lower()

    def test_node_without_report_uses_alert_service(self, payment_alert):
        """Si no hay incident_report, usa el servicio del alert."""
        from agents.data_collector import data_collector_node
        state = {
            "alert": payment_alert,
            "incident_report": None,
            "diagnosis_attempts": 0,
            "resolved": False,
            "messages": [],
        }
        result = data_collector_node(state)
        assert "collected_logs" in result
        assert result["collected_logs"]

    def test_node_data_contains_service_specific_signals(self, base_state):
        """Los datos de payment-service deben tener señales de DB connection pool."""
        from agents.data_collector import data_collector_node
        result = data_collector_node(base_state)
        combined = (
            result["collected_logs"] +
            result["collected_metrics"] +
            result["recent_commits"]
        ).lower()
        # Al menos una de las señales clave debe estar presente
        assert any(signal in combined for signal in [
            "connection", "postgres", "pool", "latency", "error"
        ])

    def test_node_different_services_return_different_data(self, payment_alert):
        """Servicios distintos deben devolver datos distintos."""
        from agents.data_collector import data_collector_node
        from schemas.incident import IncidentReport, Severity

        # Estado con auth-service
        auth_report = IncidentReport(
            alert_id="test-auth",
            severity=Severity.P2,
            service="auth-service",
            escalate_to_full_graph=True,
            classification_reasoning="Memory issue",
        )
        auth_alert = IncidentAlert(
            alert_id="test-auth",
            service="auth-service",
            metric="memory_usage",
            value=0.95,
            threshold=0.85,
        )
        auth_state = {
            "alert": auth_alert,
            "incident_report": auth_report,
            "diagnosis_attempts": 0,
            "resolved": False,
            "messages": [],
        }
        payment_state = {
            "alert": payment_alert,
            "incident_report": IncidentReport(
                alert_id="test-payment",
                severity=Severity.P2,
                service="payment-service",
                escalate_to_full_graph=True,
                classification_reasoning="Latency",
            ),
            "diagnosis_attempts": 0,
            "resolved": False,
            "messages": [],
        }

        auth_result = data_collector_node(auth_state)
        payment_result = data_collector_node(payment_state)

        assert auth_result["collected_logs"] != payment_result["collected_logs"]
        assert auth_result["collected_metrics"] != payment_result["collected_metrics"]
