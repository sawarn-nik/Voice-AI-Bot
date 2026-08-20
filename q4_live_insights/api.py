"""
Q4 Live Insights API + WebSocket Dashboard
===========================================

REST endpoints
--------------
POST /session/start              — create a session, return session_id
POST /session/{id}/chunk         — push a single transcript chunk (for testing)
POST /session/{id}/simulate      — replay a transcript at real-time speed
GET  /session/{id}/nudges        — poll active nudges
GET  /session/{id}/latency       — get latency report
GET  /session/{id}/summary       — get full session summary
POST /session/{id}/dismiss/{nid} — dismiss a nudge
GET  /health

WebSocket
---------
WS /ws/{session_id}              — real-time nudge push channel
  Server pushes JSON nudge objects as they are generated.
  Client can send {"action": "dismiss", "nudge_id": "..."} to dismiss.

Dashboard
---------
GET /dashboard/{session_id}       — HTML live dashboard (auto-refreshing)

Run:
    uvicorn q4_live_insights.api:app --port 8003 --reload
"""

from __future__ import annotations

import asyncio
import json
import uuid
from typing import Dict, List, Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from q4_live_insights.models import Nudge, Speaker
from q4_live_insights.pipeline import LiveInsightsPipeline
from shared.utils import logger

app = FastAPI(
    title="Darwix Live Insights — Q4",
    version="1.0.0",
    description="Real-time call analysis, signal detection, and agent nudge engine.",
)

# Active pipeline sessions
_sessions: Dict[str, LiveInsightsPipeline] = {}
# WebSocket connections per session
_ws_connections: Dict[str, List[WebSocket]] = {}


# ---------------------------------------------------------------------------
# REST endpoints
# ---------------------------------------------------------------------------

@app.post("/session/start")
async def start_session():
    session_id = str(uuid.uuid4())

    async def push_nudge_to_ws(nudge: Nudge) -> None:
        """Callback: push nudge to all connected WebSockets for this session."""
        connections = _ws_connections.get(session_id, [])
        dead = []
        for ws in connections:
            try:
                await ws.send_text(json.dumps({
                    "event": "nudge",
                    "data": nudge.model_dump(),
                }))
            except Exception:
                dead.append(ws)
        for ws in dead:
            connections.remove(ws)

    pipeline = LiveInsightsPipeline(session_id=session_id, on_nudge=push_nudge_to_ws)
    _sessions[session_id] = pipeline
    _ws_connections[session_id] = []

    logger.info("session_started", session_id=session_id)
    return {"session_id": session_id, "ws_url": f"/ws/{session_id}"}


class ChunkRequest(BaseModel):
    speaker: str  # "agent" | "customer"
    text: str
    asr_latency_ms: float = 300.0
    is_final: bool = True


@app.post("/session/{session_id}/chunk")
async def push_chunk(session_id: str, req: ChunkRequest):
    pipeline = _get_pipeline(session_id)
    speaker = Speaker.AGENT if req.speaker == "agent" else Speaker.CUSTOMER

    nudges = await pipeline.process_chunk(
        text=req.text,
        speaker=speaker,
        asr_latency_ms=req.asr_latency_ms,
        is_final=req.is_final,
    )

    return {
        "session_id": session_id,
        "nudges_generated": len(nudges),
        "nudges": [n.model_dump() for n in nudges],
    }


class SimulateRequest(BaseModel):
    turns: List[dict]  # [{"speaker": "agent"|"customer", "text": "...", "delay_s": 1.5}]
    realtime_speed: bool = False  # set False for instant test replay


@app.post("/session/{session_id}/simulate")
async def simulate_call(session_id: str, req: SimulateRequest):
    """
    Replay a transcript at real-time speed (assessment requirement:
    'a recording replayed at real-time speed in chunks').
    """
    pipeline = _get_pipeline(session_id)
    summary = await pipeline.run_simulation(req.turns, realtime_speed=req.realtime_speed)
    return summary


@app.get("/session/{session_id}/nudges")
async def get_nudges(session_id: str):
    pipeline = _get_pipeline(session_id)
    active = pipeline.get_active_nudges()
    return {
        "session_id": session_id,
        "active_nudges": len(active),
        "nudges": [n.model_dump() for n in active],
    }


@app.get("/session/{session_id}/latency")
async def get_latency(session_id: str):
    pipeline = _get_pipeline(session_id)
    return pipeline.get_latency_report()


@app.get("/session/{session_id}/summary")
async def get_summary(session_id: str):
    pipeline = _get_pipeline(session_id)
    return pipeline.get_session_summary()


@app.post("/session/{session_id}/dismiss/{nudge_id}")
async def dismiss_nudge(session_id: str, nudge_id: str):
    pipeline = _get_pipeline(session_id)
    pipeline.dismiss_nudge(nudge_id)
    return {"status": "dismissed", "nudge_id": nudge_id}


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "service": "live_insights",
        "active_sessions": len(_sessions),
    }


# ---------------------------------------------------------------------------
# WebSocket
# ---------------------------------------------------------------------------

@app.websocket("/ws/{session_id}")
async def websocket_nudge_stream(websocket: WebSocket, session_id: str):
    """
    Real-time nudge push channel.
    Client connects and receives nudge JSON objects as they are generated.
    """
    await websocket.accept()
    pipeline = _sessions.get(session_id)
    if not pipeline:
        await websocket.send_text(json.dumps({"error": "session_not_found"}))
        await websocket.close()
        return

    _ws_connections.setdefault(session_id, []).append(websocket)
    logger.info("ws_connected", session_id=session_id)

    try:
        # Send current active nudges immediately on connect
        active = pipeline.get_active_nudges()
        if active:
            await websocket.send_text(json.dumps({
                "event": "active_nudges",
                "data": [n.model_dump() for n in active],
            }))

        # Listen for client messages (e.g., dismiss)
        while True:
            raw = await websocket.receive_text()
            msg = json.loads(raw)
            if msg.get("action") == "dismiss":
                pipeline.dismiss_nudge(msg["nudge_id"])
                await websocket.send_text(json.dumps({"event": "dismissed", "nudge_id": msg["nudge_id"]}))

    except WebSocketDisconnect:
        logger.info("ws_disconnected", session_id=session_id)
        conns = _ws_connections.get(session_id, [])
        if websocket in conns:
            conns.remove(websocket)


# ---------------------------------------------------------------------------
# Live Dashboard HTML
# ---------------------------------------------------------------------------

DASHBOARD_HTML = """
<!DOCTYPE html>
<html>
<head>
  <title>Darwix Live Insights Dashboard</title>
  <meta http-equiv="refresh" content="3">
  <style>
    * { box-sizing: border-box; }
    body { font-family: 'Segoe UI', Arial, sans-serif; margin: 0; background: #0f172a; color: #e2e8f0; }
    header { background: #1e293b; padding: 16px 24px; border-bottom: 1px solid #334155; }
    header h1 { margin: 0; font-size: 1.2rem; color: #38bdf8; }
    .container { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; padding: 16px; }
    .card { background: #1e293b; border-radius: 8px; padding: 16px; border: 1px solid #334155; }
    .card h2 { margin: 0 0 12px; font-size: 0.85rem; text-transform: uppercase; color: #94a3b8; letter-spacing: 1px; }
    .nudge { border-radius: 6px; padding: 12px; margin-bottom: 10px; border-left: 4px solid; }
    .nudge.high   { background: #450a0a; border-color: #ef4444; }
    .nudge.medium { background: #1c1917; border-color: #f59e0b; }
    .nudge.low    { background: #0f172a; border-color: #64748b; }
    .nudge .headline { font-weight: bold; font-size: 0.95rem; }
    .nudge .body { font-size: 0.85rem; color: #cbd5e1; margin-top: 4px; }
    .nudge .source { font-size: 0.75rem; color: #64748b; margin-top: 6px; font-style: italic; }
    .nudge .meta { font-size: 0.72rem; color: #475569; margin-top: 4px; }
    .transcript { font-size: 0.82rem; line-height: 1.7; }
    .transcript .agent { color: #7dd3fc; }
    .transcript .customer { color: #86efac; }
    .stat { display: inline-block; margin-right: 20px; }
    .stat .value { font-size: 1.4rem; font-weight: bold; color: #38bdf8; }
    .stat .label { font-size: 0.75rem; color: #94a3b8; }
    .empty { color: #475569; font-size: 0.85rem; }
    .badge { display: inline-block; padding: 2px 8px; border-radius: 12px; font-size: 0.72rem; margin-left: 6px; }
    .badge.high { background: #7f1d1d; color: #fca5a5; }
    .badge.medium { background: #78350f; color: #fcd34d; }
    .badge.low { background: #1e293b; color: #94a3b8; }
  </style>
</head>
<body>
  <header>
    <h1>⚡ Darwix Live Insights — Session: {session_id}</h1>
  </header>
  <div class="container">

    <div class="card" style="grid-column: span 2">
      <h2>Stats</h2>
      <div class="stat"><div class="value">{total_chunks}</div><div class="label">Utterances</div></div>
      <div class="stat"><div class="value">{total_signals}</div><div class="label">Signals</div></div>
      <div class="stat"><div class="value">{total_nudges}</div><div class="label">Nudges</div></div>
      <div class="stat"><div class="value">{p50_ms}ms</div><div class="label">P50 E2E</div></div>
      <div class="stat"><div class="value">{p95_ms}ms</div><div class="label">P95 E2E</div></div>
    </div>

    <div class="card">
      <h2>Active Nudges ({active_count})</h2>
      {nudge_html}
    </div>

    <div class="card">
      <h2>Live Transcript</h2>
      <div class="transcript">{transcript_html}</div>
    </div>

  </div>
</body>
</html>
"""


@app.get("/dashboard/{session_id}", response_class=HTMLResponse)
async def dashboard(session_id: str):
    pipeline = _sessions.get(session_id)
    if not pipeline:
        return HTMLResponse("<h2>Session not found.</h2>", status_code=404)

    session = pipeline.session
    active = pipeline.get_active_nudges()
    latency = pipeline.get_latency_report()

    # Nudge HTML
    if active:
        nudge_parts = []
        for n in sorted(active, key=lambda x: x.priority.value):
            confidence_pct = round(n.confidence * 100)
            nudge_parts.append(f"""
              <div class="nudge {n.priority.value}">
                <div class="headline">{n.headline}
                  <span class="badge {n.priority.value}">{n.priority.value.upper()}</span>
                </div>
                <div class="body">{n.body}</div>
                <div class="source">"{n.source_text[:120]}..."</div>
                <div class="meta">Confidence: {confidence_pct}% | E2E: {round(n.end_to_end_latency_ms or 0)}ms | Signal: {n.signal_type.value}</div>
              </div>
            """)
        nudge_html = "".join(nudge_parts)
    else:
        nudge_html = '<div class="empty">No active nudges.</div>'

    # Transcript HTML
    chunks = [c for c in session.chunks if c.is_final][-15:]
    transcript_parts = []
    for c in chunks:
        css = "agent" if c.speaker.value == "agent" else "customer"
        label = "AGENT" if css == "agent" else "CUST"
        transcript_parts.append(f'<div class="{css}"><b>[{label}]</b> {c.text}</div>')
    transcript_html = "".join(transcript_parts) or '<div class="empty">No transcript yet.</div>'

    e2e = latency.get("e2e_latency", {})

    html = DASHBOARD_HTML.format(
        session_id=session_id[:12],
        total_chunks=len(session.chunks),
        total_signals=len(session.signals),
        total_nudges=len(session.nudges),
        active_count=len(active),
        p50_ms=e2e.get("p50_ms", "—"),
        p95_ms=e2e.get("p95_ms", "—"),
        nudge_html=nudge_html,
        transcript_html=transcript_html,
    )
    return HTMLResponse(html)


def _get_pipeline(session_id: str) -> LiveInsightsPipeline:
    p = _sessions.get(session_id)
    if not p:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found.")
    return p
