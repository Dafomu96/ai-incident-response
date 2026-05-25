"""
tools/slack_hitl.py — HITL via Slack con botones interactivos.

Flujo:
1. send_hitl_request() envía mensaje con botones Approve/Reject a Slack
2. El ingeniero pulsa el botón
3. Slack hace POST a /slack/actions en nuestra FastAPI
4. FastAPI actualiza el estado del grafo via callback
"""
from __future__ import annotations

import asyncio
import os
import httpx
from schemas.remediation import HITLRequest

SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN", "")
SLACK_API = "https://slack.com/api"


def _headers() -> dict:
    return {
        "Authorization": f"Bearer {SLACK_BOT_TOKEN}",
        "Content-Type": "application/json",
    }


async def send_hitl_request(request: HITLRequest) -> dict:
    """
    Envía la acción de alto riesgo a Slack para aprobación humana.
    Retorna el ts (timestamp) del mensaje para poder actualizarlo después.
    """
    if not SLACK_BOT_TOKEN:
        print(f"[MOCK HITL] Aprobación requerida: {request.action.description}")
        return {"ts": "mock-ts", "channel": request.slack_channel}

    blocks = _build_hitl_blocks(request)

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{SLACK_API}/chat.postMessage",
            headers=_headers(),
            json={
                "channel": request.slack_channel,
                "text": f":rotating_light: HITL Approval Required — Incident {request.alert_id}",
                "blocks": blocks,
            },
        )
        data = resp.json()
        if not data.get("ok"):
            print(f"[HITL] Error enviando a Slack: {data.get('error')}")
            return {}
        print(f"[HITL] Mensaje enviado a {request.slack_channel} — ts: {data['ts']}")
        return {"ts": data["ts"], "channel": data["channel"]}


async def update_hitl_message(channel: str, ts: str, approved: bool) -> None:
    """Actualiza el mensaje original con el resultado de la decisión."""
    if not SLACK_BOT_TOKEN:
        return

    emoji = ":white_check_mark:" if approved else ":x:"
    text = "approved" if approved else "rejected"

    async with httpx.AsyncClient() as client:
        await client.post(
            f"{SLACK_API}/chat.update",
            headers=_headers(),
            json={
                "channel": channel,
                "ts": ts,
                "text": f"{emoji} Action *{text}* by on-call engineer.",
                "blocks": [
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": f"{emoji} Action *{text}* by on-call engineer.",
                        },
                    }
                ],
            },
        )


def _build_hitl_blocks(request: HITLRequest) -> list:
    """Construye los bloques del mensaje Slack con botones Approve/Reject."""
    risk_emoji = ":warning:" if request.action.risk == "high" else ":information_source:"

    return [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": f":rotating_light: HITL Approval Required — {request.alert_id}",
            },
        },
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*Service:*\n{request.action.description}"},
                {"type": "mrkdwn", "text": f"*Risk:*\n{risk_emoji} {request.action.risk.upper()}"},
            ],
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*Diagnosis:*\n{request.diagnosis_summary}",
            },
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*Command to execute:*\n```{request.action.command}```",
            },
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f":alarm_clock: Auto-escalation in *{request.timeout_minutes} minutes* if no response.",
            },
        },
        {
            "type": "actions",
            "block_id": f"hitl_{request.alert_id}",
            "elements": [
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": ":white_check_mark: Approve"},
                    "style": "primary",
                    "value": f"approve|{request.alert_id}",
                    "action_id": "hitl_approve",
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": ":x: Reject"},
                    "style": "danger",
                    "value": f"reject|{request.alert_id}",
                    "action_id": "hitl_reject",
                },
            ],
        },
    ]
