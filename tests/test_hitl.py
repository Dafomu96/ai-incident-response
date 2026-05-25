"""
tests/test_hitl.py — Tests del flujo HITL.
"""
import pytest
import json
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime

from schemas.remediation import HITLRequest, RemediationAction, ActionRisk


@pytest.fixture
def sample_hitl_request():
    action = RemediationAction(
        action_id="act-rollback-001",
        description="Rollback postgres driver to v14.1",
        command="kubectl rollout undo deployment/payment-service",
        risk=ActionRisk.HIGH,
        reversible=True,
        estimated_impact="~2 min de downtime durante el rollback",
    )
    return HITLRequest(
        alert_id="test-hitl-001",
        action=action,
        diagnosis_summary="Postgres driver bump causó connection pool exhaustion (confianza: 87%)",
        slack_channel="#incident-approvals",
        timeout_minutes=10,
    )


class TestHITLRequest:
    def test_hitl_request_creation(self, sample_hitl_request):
        assert sample_hitl_request.alert_id == "test-hitl-001"
        assert sample_hitl_request.approved is None  # pendiente por defecto
        assert sample_hitl_request.timeout_minutes == 10

    def test_hitl_pending_by_default(self, sample_hitl_request):
        assert sample_hitl_request.approved is None

    def test_hitl_high_risk_action(self, sample_hitl_request):
        assert sample_hitl_request.action.risk == ActionRisk.HIGH
        assert sample_hitl_request.action.reversible is True


class TestSlackBlocks:
    def test_blocks_contain_alert_id(self, sample_hitl_request):
        from tools.slack_hitl import _build_hitl_blocks
        blocks = _build_hitl_blocks(sample_hitl_request)
        blocks_str = json.dumps(blocks)
        assert "test-hitl-001" in blocks_str

    def test_blocks_contain_command(self, sample_hitl_request):
        from tools.slack_hitl import _build_hitl_blocks
        blocks = _build_hitl_blocks(sample_hitl_request)
        blocks_str = json.dumps(blocks)
        assert "kubectl rollout undo" in blocks_str

    def test_blocks_have_approve_reject_buttons(self, sample_hitl_request):
        from tools.slack_hitl import _build_hitl_blocks
        blocks = _build_hitl_blocks(sample_hitl_request)
        action_block = next(b for b in blocks if b.get("type") == "actions")
        action_ids = [e["action_id"] for e in action_block["elements"]]
        assert "hitl_approve" in action_ids
        assert "hitl_reject" in action_ids

    def test_approve_button_value_format(self, sample_hitl_request):
        from tools.slack_hitl import _build_hitl_blocks
        blocks = _build_hitl_blocks(sample_hitl_request)
        action_block = next(b for b in blocks if b.get("type") == "actions")
        approve_btn = next(e for e in action_block["elements"] if e["action_id"] == "hitl_approve")
        assert approve_btn["value"] == "approve|test-hitl-001"

    def test_reject_button_value_format(self, sample_hitl_request):
        from tools.slack_hitl import _build_hitl_blocks
        blocks = _build_hitl_blocks(sample_hitl_request)
        action_block = next(b for b in blocks if b.get("type") == "actions")
        reject_btn = next(e for e in action_block["elements"] if e["action_id"] == "hitl_reject")
        assert reject_btn["value"] == "reject|test-hitl-001"


class TestSlackSendMock:
    @pytest.mark.asyncio
    async def test_send_uses_mock_when_no_token(self, sample_hitl_request, monkeypatch):
        monkeypatch.delenv("SLACK_BOT_TOKEN", raising=False)
        # Reimportar con env limpio
        import importlib
        import tools.slack_hitl as slack_module
        monkeypatch.setattr(slack_module, "SLACK_BOT_TOKEN", "")
        result = await slack_module.send_hitl_request(sample_hitl_request)
        assert result.get("ts") == "mock-ts"

    @pytest.mark.asyncio
    async def test_send_with_token_calls_slack_api(self, sample_hitl_request, monkeypatch):
        import tools.slack_hitl as slack_module
        monkeypatch.setattr(slack_module, "SLACK_BOT_TOKEN", "xoxb-fake-token")

        mock_response = MagicMock()
        mock_response.json.return_value = {"ok": True, "ts": "1234567890.123", "channel": "C123"}

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_response)
            result = await slack_module.send_hitl_request(sample_hitl_request)

        assert result.get("ts") == "1234567890.123"


class TestFastAPIHITLCallback:
    @pytest.mark.asyncio
    async def test_slack_callback_approve(self):
        from fastapi.testclient import TestClient
        from api.main import app, _incidents

        # Simular incidente existente
        _incidents["test-cb-001"] = {"status": "pending_hitl"}

        client = TestClient(app)
        payload = json.dumps({
            "actions": [{"action_id": "hitl_approve", "value": "approve|test-cb-001"}],
            "channel": {"id": "C123"},
            "message": {"ts": "123.456"},
        })
        resp = client.post("/slack/actions", data={"payload": payload})
        assert resp.status_code == 200
        assert _incidents["test-cb-001"]["hitl_approved"] is True
        assert _incidents["test-cb-001"]["status"] == "approved"

    @pytest.mark.asyncio
    async def test_slack_callback_reject(self):
        from fastapi.testclient import TestClient
        from api.main import app, _incidents

        _incidents["test-cb-002"] = {"status": "pending_hitl"}

        client = TestClient(app)
        payload = json.dumps({
            "actions": [{"action_id": "hitl_reject", "value": "reject|test-cb-002"}],
            "channel": {"id": "C123"},
            "message": {"ts": "123.456"},
        })
        resp = client.post("/slack/actions", data={"payload": payload})
        assert resp.status_code == 200
        assert _incidents["test-cb-002"]["hitl_approved"] is False
        assert _incidents["test-cb-002"]["status"] == "rejected"

    def test_health_endpoint(self):
        from fastapi.testclient import TestClient
        from api.main import app
        client = TestClient(app)
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"
