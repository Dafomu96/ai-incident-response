"""
tests/test_tools_mock.py — Tests de los tools en modo mock.
Verifica que los mocks devuelven datos útiles sin APIs externas.
"""
import pytest
import asyncio
from tools.prometheus import fetch_metrics, _mock_metrics
from tools.loki import fetch_logs, _mock_logs
from tools.github_api import fetch_recent_commits, _mock_commits
from tools.kubernetes_api import fetch_pod_status, _mock_pod_status


class TestPrometheus:
    def test_mock_returns_string(self):
        result = _mock_metrics("payment-service", 120)
        assert isinstance(result, str)
        assert "payment-service" in result

    def test_mock_contains_key_metrics(self):
        result = _mock_metrics("payment-service", 60)
        assert "error_rate" in result
        assert "latency" in result
        assert "cpu" in result.lower()

    @pytest.mark.asyncio
    async def test_fetch_uses_mock_when_no_url(self, monkeypatch):
        monkeypatch.delenv("PROMETHEUS_URL", raising=False)
        result = await fetch_metrics("payment-service", 60)
        assert "[MOCK]" in result


class TestLoki:
    def test_mock_returns_string(self):
        result = _mock_logs("payment-service", 120)
        assert isinstance(result, str)
        assert "payment-service" in result

    def test_mock_contains_errors(self):
        result = _mock_logs("payment-service", 120)
        assert "ERROR" in result

    @pytest.mark.asyncio
    async def test_fetch_uses_mock_when_no_url(self, monkeypatch):
        monkeypatch.delenv("LOKI_URL", raising=False)
        result = await fetch_logs("payment-service", 60)
        assert "[MOCK]" in result


class TestGitHub:
    def test_mock_returns_string(self):
        result = _mock_commits("payment-service")
        assert isinstance(result, str)

    def test_mock_contains_commit_info(self):
        result = _mock_commits("payment-service")
        assert "payment-service" in result
        # Los commits mock tienen formato [sha] mensaje
        assert "[" in result and "]" in result

    @pytest.mark.asyncio
    async def test_fetch_uses_mock_when_no_token(self, monkeypatch):
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)
        result = await fetch_recent_commits("payment-service")
        assert "[MOCK]" in result


class TestKubernetes:
    def test_mock_returns_string(self):
        result = _mock_pod_status("payment-service")
        assert isinstance(result, str)

    def test_mock_contains_pod_status(self):
        result = _mock_pod_status("payment-service")
        assert "payment-service" in result
        # El mock incluye CrashLoopBackOff como señal relevante
        assert "CrashLoopBackOff" in result

    @pytest.mark.asyncio
    async def test_fetch_uses_mock_when_no_k8s(self, monkeypatch):
        monkeypatch.delenv("K8S_KUBECONFIG_PATH", raising=False)
        result = await fetch_pod_status("payment-service")
        assert "[MOCK]" in result
