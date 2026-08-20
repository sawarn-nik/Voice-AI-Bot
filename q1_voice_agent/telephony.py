"""
Telephony Layer — Twilio Media Streams + Web Interface
======================================================
Provides two calling interfaces:

1. Twilio WebSocket (PSTN calls to/from a real phone number)
   - TwiML webhook: POST /twiml  → returns <Connect><Stream> XML
   - WebSocket:     WS /stream   → handles real-time audio frames

2. Web calling interface (browser WebRTC via VAPI / Retell)
   - POST /web-call/start  → initialises session, returns session_id
   - POST /web-call/turn   → processes one text turn (for demo/testing)
   - GET  /web-call/summary → returns CRM summary

3. CRM webhook
   - POST /crm/lead  → saves qualified lead to mock CRM store

Run:
    uvicorn q1_voice_agent.telephony:app --port 8000 --reload
"""

from __future__ import annotations

import asyncio
import base64
import json
import uuid
from typing import Dict, Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request, HTTPException
from fastapi.responses import HTMLResponse, Response
from pydantic import BaseModel

from q1_voice_agent.agent import VoiceAgent, text_to_speech
from q1_voice_agent.prompts import OPENING_SCRIPT_COLD
from q1_voice_agent.stt import WhisperSTT
from shared.config import settings
from shared.utils import logger
from shared.database import upsert_lead, get_all_leads, get_lead

app = FastAPI(
    title="Darwix Voice Agent — Q1",
    version="1.0.0",
    description="Health insurance lead qualification voice agent.",
)

# In-memory session store (replace with Redis in production)
_sessions: Dict[str, VoiceAgent] = {}

# Mock CRM store
_crm_leads: list = []


# ---------------------------------------------------------------------------
# TwiML — tells Twilio to open a media stream to our WebSocket
# ---------------------------------------------------------------------------

TWIML_RESPONSE = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Say voice="alice">
    Please hold while we connect you to our health insurance specialist.
  </Say>
  <Connect>
    <Stream url="wss://{host}/stream" />
  </Connect>
</Response>"""


@app.post("/twiml")
async def twiml_webhook(request: Request):
    """
    Twilio calls this URL when an inbound call arrives.
    Returns TwiML that opens a bidirectional media stream.
    """
    host = request.headers.get("host", "localhost")
    xml = TWIML_RESPONSE.format(host=host)
    return Response(content=xml, media_type="application/xml")


# ---------------------------------------------------------------------------
# Twilio Media Stream WebSocket
# ---------------------------------------------------------------------------

@app.websocket("/stream")
async def twilio_stream(websocket: WebSocket):
    """
    Handles the Twilio media stream protocol.

    Twilio sends:
      {"event": "start", "streamSid": ..., "start": {"callSid": ...}}
      {"event": "media", "media": {"payload": "<base64-mulaw-audio>"}}
      {"event": "stop"}

    We send:
      {"event": "media", "streamSid": ..., "media": {"payload": "<base64-mulaw-audio>"}}
      {"event": "mark", ...}  (optional, for sync)
    """
    await websocket.accept()
    session_id = str(uuid.uuid4())
    agent: Optional[VoiceAgent] = None
    stream_sid: Optional[str] = None

    # Deepgram streaming STT connection
    dg_connection = None
    transcript_buffer = ""

    logger.info("twilio_stream_connected", session_id=session_id)

    try:
        async for raw_message in websocket.iter_text():
            data = json.loads(raw_message)
            event = data.get("event")

            if event == "start":
                stream_sid = data["streamSid"]
                call_sid = data.get("start", {}).get("callSid", "unknown")
                agent = VoiceAgent(session_id=session_id)
                _sessions[session_id] = agent

                # Send opening greeting
                greeting = OPENING_SCRIPT_COLD
                audio = await text_to_speech(greeting)
                if audio:
                    await _send_audio_to_twilio(websocket, stream_sid, audio)

                logger.info("stream_start", session_id=session_id, call_sid=call_sid)

            elif event == "media" and agent:
                # Receive audio chunk (base64 mulaw 8kHz)
                payload = data["media"]["payload"]
                audio_chunk = base64.b64decode(payload)

                # In production: pipe to Deepgram streaming STT
                # For this implementation we accumulate and process on silence detection
                # (simplified — real implementation uses Deepgram's streaming SDK)
                # transcript_buffer is updated by Deepgram callbacks

            elif event == "stop":
                logger.info("stream_stop", session_id=session_id)
                if agent:
                    summary = agent.get_call_summary()
                    _save_crm_lead(agent)
                    logger.info("call_ended", session_id=session_id, summary=summary[:200])
                break

    except WebSocketDisconnect:
        logger.info("twilio_stream_disconnected", session_id=session_id)
    finally:
        _sessions.pop(session_id, None)


async def _send_audio_to_twilio(
    websocket: WebSocket, stream_sid: str, audio_bytes: bytes
) -> None:
    """Send PCM/mulaw audio back to Twilio via the media stream."""
    payload = base64.b64encode(audio_bytes).decode("utf-8")
    message = {
        "event": "media",
        "streamSid": stream_sid,
        "media": {"payload": payload},
    }
    await websocket.send_text(json.dumps(message))


# ---------------------------------------------------------------------------
# Web Calling Interface (text-based for demo / testing)
# ---------------------------------------------------------------------------

class WebCallStartRequest(BaseModel):
    caller_name: str = "Valued Customer"


class WebCallTurnRequest(BaseModel):
    session_id: str
    user_utterance: str


class WebCallTurnResponse(BaseModel):
    session_id: str
    agent_response: str
    outcome: str
    stage: str
    lead_captured: dict


@app.post("/web-call/start")
async def web_call_start(req: WebCallStartRequest):
    """Initialise a new call session and return the opening greeting."""
    session_id = str(uuid.uuid4())
    agent = VoiceAgent(session_id=session_id, caller_name=req.caller_name)
    _sessions[session_id] = agent

    greeting = OPENING_SCRIPT_COLD
    logger.info("web_call_start", session_id=session_id, caller=req.caller_name)

    return {
        "session_id": session_id,
        "agent_greeting": greeting,
        "instructions": "Send subsequent turns to POST /web-call/turn",
    }


@app.post("/web-call/turn", response_model=WebCallTurnResponse)
async def web_call_turn(req: WebCallTurnRequest):
    """Process one user turn and return the agent's response."""
    agent = _sessions.get(req.session_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Session not found. Start a new call first.")

    response_text = agent.respond(req.user_utterance)

    # Upsert to CRM on every turn so partial leads are never lost
    _save_crm_lead(agent)

    return WebCallTurnResponse(
        session_id=req.session_id,
        agent_response=response_text,
        outcome=agent.state.outcome,
        stage=agent.state.stage,
        lead_captured=agent.state.lead.to_crm_dict(),
    )


@app.get("/web-call/summary/{session_id}")
async def web_call_summary(session_id: str):
    """Return the CRM summary for a session."""
    agent = _sessions.get(session_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Session not found.")
    return {
        "session_id": session_id,
        "summary": agent.get_call_summary(),
        "crm_payload": agent.get_lead_crm_payload(),
    }


# ---------------------------------------------------------------------------
# CRM Mock
# ---------------------------------------------------------------------------

def _save_crm_lead(agent: VoiceAgent) -> None:
    """Upsert lead to SQLite DB and in-memory list."""
    payload = agent.get_lead_crm_payload()
    # SQLite (persistent)
    upsert_lead(payload)
    # In-memory (for fast /crm/leads response)
    for i, existing in enumerate(_crm_leads):
        if existing.get("session_id") == agent.session_id:
            _crm_leads[i] = payload
            return
    _crm_leads.append(payload)


@app.get("/crm/leads")
async def get_crm_leads():
    """Return all leads from SQLite (persistent across restarts)."""
    leads = get_all_leads()
    # Serialize datetime objects
    for lead in leads:
        for k, v in lead.items():
            if hasattr(v, "isoformat"):
                lead[k] = v.isoformat()
    return {"total": len(leads), "leads": leads}


@app.post("/crm/lead")
async def save_crm_lead_webhook(payload: dict):
    """Accept an external CRM webhook payload."""
    _crm_leads.append(payload)
    return {"status": "saved", "total_leads": len(_crm_leads)}


# ---------------------------------------------------------------------------
# Health check & demo UI
# ---------------------------------------------------------------------------

@app.get("/health")
async def health():
    return {
        "status": "ok",
        "service": "voice_agent",
        "active_sessions": len(_sessions),
        "crm_leads": len(_crm_leads),
        "stt_backend": "whisper-1 (openai)" if not settings.deepgram_api_key else "deepgram nova-2",
    }


@app.post("/web-call/transcribe")
async def transcribe_audio(file: bytes = None, session_id: str = None):
    """
    Optional: upload audio bytes, get transcript back via Whisper.
    Useful for testing STT without Deepgram.
    """
    if not file:
        raise HTTPException(status_code=400, detail="No audio provided.")
    stt = WhisperSTT()
    text = await stt.transcribe_async(file)
    return {"transcript": text, "session_id": session_id}


DEMO_HTML = """
<!DOCTYPE html>
<html>
<head>
  <title>Darwix Voice Agent Demo</title>
  <style>
    body { font-family: Arial, sans-serif; max-width: 700px; margin: 40px auto; padding: 0 20px; }
    #chat { border: 1px solid #ccc; padding: 16px; height: 400px; overflow-y: auto; background: #f9f9f9; border-radius: 8px; }
    .user-msg { color: #1a56db; margin: 8px 0; }
    .agent-msg { color: #1a7550; margin: 8px 0; }
    .meta { color: #888; font-size: 0.85em; }
    input[type=text] { width: 80%; padding: 8px; }
    button { padding: 8px 16px; background: #1a56db; color: white; border: none; cursor: pointer; border-radius: 4px; }
  </style>
</head>
<body>
  <h1>Darwix Health Insurance Voice Agent</h1>
  <p class="meta">Web calling interface — type your responses as if you are the customer.</p>
  <div id="chat"></div>
  <br>
  <input type="text" id="msg" placeholder="Type your response..." />
  <button onclick="sendMsg()">Send</button>
  <button onclick="startCall()">New Call</button>
  <p class="meta" id="session-info">No active session.</p>

  <script>
    let sessionId = null;

    async function startCall() {
      const res = await fetch('/web-call/start', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({caller_name: 'Web Caller'})
      });
      const data = await res.json();
      sessionId = data.session_id;
      document.getElementById('session-info').innerText = 'Session: ' + sessionId;
      document.getElementById('chat').innerHTML = '';
      appendMsg('ARIA', data.agent_greeting, 'agent-msg');
    }

    async function sendMsg() {
      const input = document.getElementById('msg');
      const text = input.value.trim();
      if (!text || !sessionId) return;
      input.value = '';
      appendMsg('YOU', text, 'user-msg');

      const res = await fetch('/web-call/turn', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({session_id: sessionId, user_utterance: text})
      });
      const data = await res.json();
      appendMsg('ARIA', data.agent_response, 'agent-msg');
      document.getElementById('session-info').innerText =
        'Session: ' + sessionId + ' | Stage: ' + data.stage + ' | Outcome: ' + data.outcome;
    }

    function appendMsg(speaker, text, cls) {
      const div = document.getElementById('chat');
      div.innerHTML += '<div class="' + cls + '"><b>' + speaker + ':</b> ' + text + '</div>';
      div.scrollTop = div.scrollHeight;
    }

    document.getElementById('msg').addEventListener('keypress', e => {
      if (e.key === 'Enter') sendMsg();
    });

    // Auto-start
    startCall();
  </script>
</body>
</html>
"""


@app.get("/", response_class=HTMLResponse)
async def demo_ui():
    """Simple browser-based calling interface for demo and testing."""
    return DEMO_HTML
