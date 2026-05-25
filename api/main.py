"""
api/main.py — FastAPI backend.
"""
from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Any
from concurrent.futures import ThreadPoolExecutor

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Request
from fastapi.responses import JSONResponse

from schemas.incident import IncidentAlert
from graph.workflow import compile_graph
from tools.slack_hitl import update_hitl_message

from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="AI Incident Response", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_incidents: dict[str, Any] = {}
_graph = compile_graph()
_executor = ThreadPoolExecutor(max_workers=4)


def _run_graph(alert: IncidentAlert) -> dict:
    """Ejecuta el grafo en un thread separado para no bloquear el event loop."""
    return _graph.invoke(
        {
            "alert": alert,
            "diagnosis_attempts": 0,
            "resolved": False,
            "messages": [],
        },
        config={"configurable": {"thread_id": alert.alert_id}},
    )


@app.post("/incident")
async def create_incident(alert: IncidentAlert):
    if alert.alert_id in _incidents:
        raise HTTPException(400, f"Incident {alert.alert_id} already exists")

    _incidents[alert.alert_id] = {
        "status": "running",
        "alert": alert,
        "started_at": datetime.utcnow(),
    }

    import asyncio
    loop = asyncio.get_event_loop()
    try:
        result = await loop.run_in_executor(_executor, _run_graph, alert)
        _incidents[alert.alert_id].update({
            "status": "resolved" if result.get("resolved") else "pending_hitl",
            "result": result,
            "finished_at": datetime.utcnow(),
        })
        return {
            "alert_id": alert.alert_id,
            "status": _incidents[alert.alert_id]["status"],
            "severity": result["incident_report"].severity if result.get("incident_report") else None,
            "root_cause": result["diagnosis"].top_hypothesis.hypothesis if result.get("diagnosis") else None,
        }
    except Exception as e:
        _incidents[alert.alert_id]["status"] = "error"
        _incidents[alert.alert_id]["error"] = str(e)
        raise HTTPException(500, str(e))


@app.get("/incident/{alert_id}")
async def get_incident(alert_id: str):
    if alert_id not in _incidents:
        raise HTTPException(404, f"Incident {alert_id} not found")
    inc = _incidents[alert_id]
    result = inc.get("result", {})
    return {
        "alert_id": alert_id,
        "status": inc["status"],
        "severity": result["incident_report"].severity if result.get("incident_report") else None,
        "root_cause": result["diagnosis"].top_hypothesis.hypothesis if result.get("diagnosis") else None,
        "resolved": result.get("resolved", False),
    }


@app.post("/slack/actions")
async def slack_actions(request: Request):
    form = await request.form()
    payload = json.loads(form.get("payload", "{}"))

    actions = payload.get("actions", [])
    if not actions:
        return JSONResponse({"ok": True})

    action = actions[0]
    value = action.get("value", "")
    parts = value.split("|")
    if len(parts) != 2:
        return JSONResponse({"ok": True})

    decision, alert_id = parts
    approved = decision == "approve"

    if alert_id in _incidents:
        _incidents[alert_id]["hitl_approved"] = approved
        _incidents[alert_id]["status"] = "approved" if approved else "rejected"

    channel = payload.get("channel", {}).get("id", "")
    ts = payload.get("message", {}).get("ts", "")
    if channel and ts:
        import asyncio
        asyncio.create_task(update_hitl_message(channel, ts, approved))

    action_text = "approved ✅" if approved else "rejected ❌"
    return JSONResponse({"text": f"Action {action_text}"})


@app.websocket("/ws/{incident_id}")
async def websocket_endpoint(websocket: WebSocket, incident_id: str):
    await websocket.accept()
    import asyncio
    try:
        while True:
            if incident_id in _incidents:
                inc = _incidents[incident_id]
                await websocket.send_json({
                    "alert_id": incident_id,
                    "status": inc["status"],
                    "timestamp": datetime.utcnow().isoformat(),
                })
                if inc["status"] in ("resolved", "error", "rejected"):
                    break
            await asyncio.sleep(2)
    except WebSocketDisconnect:
        pass


@app.get("/health")
async def health():
    return {"status": "ok", "version": "0.1.0"}
