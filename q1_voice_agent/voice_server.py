"""
Voice WebSocket Server
======================
Full-duplex voice pipeline:

  Browser Mic (WebM/Opus chunks)
       ↓ WebSocket binary frames
  Groq Whisper STT  (~400ms)
       ↓ transcript text
  KB Retrieval (Qdrant + Gemini embeddings)
       ↓ grounded context
  LLM (Groq compound-mini → Gemini fallback)
       ↓ response text
  Edge-TTS (en-US-AriaNeural)
       ↓ MP3 audio bytes
  Browser Speaker

Protocol
--------
Client → Server:  binary frames (raw WebM audio chunks)
Server → Client:
  {"type": "transcript", "text": "...", "speaker": "user"}
  {"type": "transcript", "text": "...", "speaker": "aria"}
  {"type": "audio"}  followed immediately by a binary audio frame
  {"type": "status", "stage": "listening|thinking|speaking"}
  {"type": "lead", "data": {...}}
  {"type": "outcome", "outcome": "QUALIFIED|FOLLOW_UP|..."}
  {"type": "error", "message": "..."}
"""

from __future__ import annotations

import asyncio
import io
import json
import uuid
from typing import Dict

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse

from q1_voice_agent.agent import VoiceAgent
from shared.providers import GroqWhisperProvider, EdgeTTSProvider
from shared.database import upsert_lead
from shared.utils import logger

app = FastAPI(title="Darwix Voice Agent — Real-Time Voice Interface")

_sessions: Dict[str, VoiceAgent] = {}
_stt = GroqWhisperProvider()
_tts = EdgeTTSProvider()


@app.websocket("/voice/{session_id}")
async def voice_ws(websocket: WebSocket, session_id: str):
    """
    Handles one full voice call session.
    Each binary message received = one audio chunk from the browser mic.
    """
    await websocket.accept()
    logger.info("voice_ws_connected", session_id=session_id)

    agent = VoiceAgent(session_id=session_id)
    _sessions[session_id] = agent

    # Send opening greeting as audio
    greeting = (
        "Hello! This is Aria from ExampleInsurer. I'm calling to share how our "
        "health insurance plans can protect you and your family. Do you have about 3 minutes?"
    )
    await _send_text_and_audio(websocket, greeting, speaker="aria")
    agent.state.add_turn("assistant", greeting)

    try:
        while True:
            message = await websocket.receive()

            if "bytes" in message and message["bytes"]:
                # Complete audio blob sent as single binary message after mic release
                audio_bytes = message["bytes"]
                if len(audio_bytes) < 2000:
                    await _send_status(websocket, "listening")
                    continue

                await _send_status(websocket, "transcribing")

                transcript = await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda ab=audio_bytes: _stt.transcribe(ab, language="en", filename="audio.webm"),
                )


                if not transcript or len(transcript.strip()) < 2:
                    await _send_status(websocket, "listening")
                    continue

                await websocket.send_text(json.dumps({
                    "type": "transcript", "text": transcript, "speaker": "user",
                }))
                await _send_status(websocket, "thinking")

                response_text = agent.respond(transcript)

                await websocket.send_text(json.dumps({
                    "type": "transcript", "text": response_text, "speaker": "aria",
                }))
                await _send_audio(websocket, response_text)

                await websocket.send_text(json.dumps({
                    "type": "lead", "data": agent.state.lead.to_crm_dict(),
                }))

                if agent.state.stage in ("done", "escalated"):
                    upsert_lead(agent.get_lead_crm_payload())
                    await websocket.send_text(json.dumps({
                        "type": "outcome",
                        "outcome": agent.state.outcome,
                        "summary": agent.get_call_summary(),
                    }))

                await _send_status(websocket, "listening")

            elif "text" in message:
                data = json.loads(message["text"])
                if data.get("type") == "ping":
                    await websocket.send_text(json.dumps({"type": "pong"}))

    except WebSocketDisconnect:
        logger.info("voice_ws_disconnected", session_id=session_id)
    finally:
        # Save partial lead on disconnect
        if session_id in _sessions:
            payload = _sessions[session_id].get_lead_crm_payload()
            upsert_lead(payload)
            del _sessions[session_id]


async def _send_status(ws: WebSocket, stage: str) -> None:
    await ws.send_text(json.dumps({"type": "status", "stage": stage}))


async def _send_text_and_audio(ws: WebSocket, text: str, speaker: str = "aria") -> None:
    await ws.send_text(json.dumps({"type": "transcript", "text": text, "speaker": speaker}))
    await _send_audio(ws, text)


async def _send_audio(ws: WebSocket, text: str) -> None:
    for attempt in range(3):
        try:
            audio = await asyncio.wait_for(_tts.synthesize(text, language="en"), timeout=15)
            if audio:
                await ws.send_text(json.dumps({"type": "audio"}))
                await ws.send_bytes(audio)
            return
        except asyncio.TimeoutError:
            logger.warning("tts_timeout_retry", attempt=attempt+1)
            await asyncio.sleep(1)
        except Exception as e:
            logger.error("tts_send_error", error=str(e))
            return


@app.get("/voice-call", response_class=HTMLResponse)
async def voice_call_ui():
    """Browser-based voice calling interface."""
    session_id = str(uuid.uuid4())
    return HTMLResponse(content=_build_voice_html(session_id))


@app.get("/health")
async def health():
    return {"status": "ok", "service": "voice_server", "active_sessions": len(_sessions)}


def _build_voice_html(session_id: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Darwix Voice Agent — Aria</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ font-family: 'Segoe UI', Arial, sans-serif; background: #0f172a; color: #e2e8f0; display: flex; flex-direction: column; height: 100vh; }}
    header {{ background: #1e293b; padding: 16px 24px; border-bottom: 1px solid #334155; display: flex; align-items: center; gap: 12px; }}
    .logo {{ width: 36px; height: 36px; background: #3b82f6; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 18px; }}
    header h1 {{ font-size: 1.1rem; color: #38bdf8; }}
    header .sub {{ font-size: 0.8rem; color: #64748b; }}
    #chat {{ flex: 1; overflow-y: auto; padding: 20px; display: flex; flex-direction: column; gap: 12px; }}
    .msg {{ max-width: 75%; padding: 12px 16px; border-radius: 12px; font-size: 0.9rem; line-height: 1.5; }}
    .msg.aria {{ background: #1e3a5f; border-radius: 12px 12px 12px 2px; align-self: flex-start; }}
    .msg.user {{ background: #1e4d3a; border-radius: 12px 12px 2px 12px; align-self: flex-end; }}
    .msg .label {{ font-size: 0.72rem; color: #64748b; margin-bottom: 4px; font-weight: bold; text-transform: uppercase; }}
    footer {{ background: #1e293b; padding: 20px 24px; border-top: 1px solid #334155; display: flex; flex-direction: column; align-items: center; gap: 12px; }}
    #status {{ font-size: 0.85rem; color: #94a3b8; height: 20px; }}
    #status.listening {{ color: #22c55e; }}
    #status.speaking {{ color: #3b82f6; }}
    #status.thinking {{ color: #f59e0b; }}
    #mic-btn {{ width: 72px; height: 72px; border-radius: 50%; border: none; cursor: pointer; font-size: 28px; transition: all 0.2s; background: #3b82f6; color: white; box-shadow: 0 0 0 0 rgba(59,130,246,0.5); }}
    #mic-btn.recording {{ background: #ef4444; box-shadow: 0 0 0 8px rgba(239,68,68,0.3); animation: pulse 1.5s infinite; }}
    #mic-btn:disabled {{ background: #475569; cursor: not-allowed; box-shadow: none; }}
    @keyframes pulse {{ 0%,100% {{ box-shadow: 0 0 0 0 rgba(239,68,68,0.4); }} 50% {{ box-shadow: 0 0 0 14px rgba(239,68,68,0); }} }}
    #lead-panel {{ position: fixed; right: 16px; top: 80px; width: 220px; background: #1e293b; border: 1px solid #334155; border-radius: 8px; padding: 12px; font-size: 0.78rem; }}
    #lead-panel h3 {{ font-size: 0.8rem; color: #94a3b8; margin-bottom: 8px; text-transform: uppercase; }}
    .lead-row {{ display: flex; justify-content: space-between; padding: 3px 0; border-bottom: 1px solid #334155; }}
    .lead-row .key {{ color: #64748b; }}
    .lead-row .val {{ color: #38bdf8; font-weight: bold; }}
    #outcome-banner {{ display: none; background: #14532d; border: 1px solid #22c55e; border-radius: 8px; padding: 12px; text-align: center; font-weight: bold; color: #86efac; }}
  </style>
</head>
<body>
  <header>
    <div class="logo">🎙️</div>
    <div>
      <h1>Aria — ExampleInsurer</h1>
      <div class="sub">Health Insurance Lead Qualification</div>
    </div>
  </header>

  <div id="chat"></div>

  <div id="lead-panel">
    <h3>Lead Captured</h3>
    <div id="lead-fields"></div>
    <div id="outcome-banner"></div>
  </div>

  <footer>
    <div id="status">Connecting...</div>
    <button id="mic-btn" disabled>🎙️</button>
    <div style="font-size:0.75rem;color:#475569">Hold to speak · Release to send</div>
  </footer>

  <script>
    const SESSION_ID = '{session_id}';
    const WS_URL = `ws://${{location.host}}/voice/${{SESSION_ID}}`;
    const chat = document.getElementById('chat');
    const micBtn = document.getElementById('mic-btn');
    const statusEl = document.getElementById('status');
    const leadFields = document.getElementById('lead-fields');
    const outcomeBanner = document.getElementById('outcome-banner');

    let ws, mediaRecorder, audioChunks = [];
    let audioQueue = [], isPlaying = false;
    let isConnected = false;
    let expectingAudio = false;

    // ── WebSocket ──────────────────────────────────────────────
    function connect() {{
      ws = new WebSocket(WS_URL);
      ws.binaryType = 'arraybuffer';

      ws.onopen = () => {{
        isConnected = true;
        setStatus('listening', '🟢 Listening — hold mic button to speak');
        micBtn.disabled = false;
      }};

      ws.onmessage = (event) => {{
        if (event.data instanceof ArrayBuffer) {{
          // Audio frame
          const blob = new Blob([event.data], {{ type: 'audio/mpeg' }});
          audioQueue.push(blob);
          if (!isPlaying) playNextAudio();
          return;
        }}
        const msg = JSON.parse(event.data);

        if (msg.type === 'transcript') {{
          appendMsg(msg.speaker, msg.text);
        }}
        else if (msg.type === 'status') {{
          const labels = {{
            listening: '🟢 Listening — hold mic button to speak',
            transcribing: '⌛ Transcribing...',
            thinking: '🤔 Aria is thinking...',
            speaking: '🔊 Aria is speaking...',
          }};
          setStatus(msg.stage, labels[msg.stage] || msg.stage);
        }}
        else if (msg.type === 'lead') {{
          updateLeadPanel(msg.data);
        }}
        else if (msg.type === 'outcome') {{
          outcomeBanner.style.display = 'block';
          outcomeBanner.textContent = '✅ ' + msg.outcome + ' — Call Complete';
          micBtn.disabled = true;
        }}
        else if (msg.type === 'audio') {{
          // next binary frame is audio
        }}
      }};

      ws.onclose = () => {{
        isConnected = false;
        setStatus('', '🔴 Disconnected');
        micBtn.disabled = true;
      }};
    }}

    // ── Audio playback ─────────────────────────────────────────
    async function playNextAudio() {{
      if (audioQueue.length === 0) {{ isPlaying = false; return; }}
      isPlaying = true;
      setStatus('speaking', '🔊 Aria is speaking...');
      const blob = audioQueue.shift();
      const url = URL.createObjectURL(blob);
      const audio = new Audio(url);
      audio.onended = () => {{
        URL.revokeObjectURL(url);
        if (audioQueue.length > 0) playNextAudio();
        else {{ isPlaying = false; setStatus('listening', '🟢 Listening'); }}
      }};
      await audio.play().catch(e => console.warn('Audio play:', e));
    }}

    // ── Mic recording ──────────────────────────────────────────
    async function startRecording() {{
      const stream = await navigator.mediaDevices.getUserMedia({{ audio: true }});

      // Pick best supported format
      const mimeType = MediaRecorder.isTypeSupported('audio/webm;codecs=opus')
        ? 'audio/webm;codecs=opus'
        : MediaRecorder.isTypeSupported('audio/webm')
          ? 'audio/webm'
          : 'audio/ogg;codecs=opus';

      mediaRecorder = new MediaRecorder(stream, {{ mimeType }});
      audioChunks = [];  // collect locally — DO NOT stream chunks to server

      mediaRecorder.ondataavailable = (e) => {{
        if (e.data.size > 0) audioChunks.push(e.data);
      }};

      mediaRecorder.onstop = () => {{
        // Assemble all chunks into one complete audio blob and send
        const blob = new Blob(audioChunks, {{ type: mimeType }});
        audioChunks = [];
        if (blob.size > 1000 && ws.readyState === WebSocket.OPEN) {{
          blob.arrayBuffer().then(buf => ws.send(buf));
        }} else {{
          setStatus('listening', '🟢 Listening — hold mic button to speak');
        }}
      }};

      mediaRecorder.start();  // no timeslice — collect everything until stop()
      micBtn.classList.add('recording');
      micBtn.textContent = '⏹️';
      setStatus('recording', '🔴 Recording — release to send');
    }}

    function stopRecording() {{
      if (mediaRecorder && mediaRecorder.state !== 'inactive') {{
        mediaRecorder.stop();  // triggers onstop → sends complete blob
        mediaRecorder.stream.getTracks().forEach(t => t.stop());
      }}
      micBtn.classList.remove('recording');
      micBtn.textContent = '🎙️';
    }}

    micBtn.addEventListener('mousedown', startRecording);
    micBtn.addEventListener('mouseup', stopRecording);
    micBtn.addEventListener('touchstart', (e) => {{ e.preventDefault(); startRecording(); }});
    micBtn.addEventListener('touchend', (e) => {{ e.preventDefault(); stopRecording(); }});

    // ── UI helpers ─────────────────────────────────────────────
    function appendMsg(speaker, text) {{
      const div = document.createElement('div');
      div.className = 'msg ' + (speaker === 'aria' ? 'aria' : 'user');
      div.innerHTML = `<div class="label">${{speaker === 'aria' ? 'ARIA' : 'YOU'}}</div>${{text}}`;
      chat.appendChild(div);
      chat.scrollTop = chat.scrollHeight;
    }}

    function setStatus(cls, text) {{
      statusEl.className = cls;
      statusEl.textContent = text;
    }}

    function updateLeadPanel(data) {{
      const fields = ['name','age','smoker','has_preexisting_conditions','monthly_budget_php','plan_interest','contact_number','callback_time'];
      const labels = {{'name':'Name','age':'Age','smoker':'Smoker','has_preexisting_conditions':'Pre-existing','monthly_budget_php':'Budget (PHP)','plan_interest':'Plan','contact_number':'Phone','callback_time':'Callback'}};
      leadFields.innerHTML = fields
        .filter(k => data[k] !== null && data[k] !== undefined)
        .map(k => `<div class="lead-row"><span class="key">${{labels[k]}}</span><span class="val">${{data[k]}}</span></div>`)
        .join('');
    }}

    connect();
  </script>
</body>
</html>"""
