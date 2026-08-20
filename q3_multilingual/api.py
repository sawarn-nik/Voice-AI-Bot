"""
Q3 Multilingual Voice Bots — Unified API
==========================================

POST /ph/start          — Start a Philippines (Taglish) call session
POST /ph/turn           — Process one turn in Philippines bot
GET  /ph/summary/{id}   — Get Philippines call summary

POST /id/start          — Start an Indonesia (Bahasa) call session
POST /id/turn           — Process one turn in Indonesia bot
GET  /id/summary/{id}   — Get Indonesia call summary

GET  /asr-config        — Return ASR configurations for both markets
GET  /health            — Liveness check

Run:
    uvicorn q3_multilingual.api:app --port 8002 --reload
"""

from __future__ import annotations

import uuid
from typing import Dict, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from q3_multilingual.philippines.agent_ph import PhilippinesVoiceBot, ASR_CONFIG_PH
from q3_multilingual.indonesia.agent_id import IndonesiaVoiceBot, ASR_CONFIG_ID
from shared.utils import logger

app = FastAPI(
    title="Darwix Multilingual Voice Bots — Q3",
    version="1.0.0",
    description="Philippines (Taglish) and Indonesia (Bahasa) localized voice bots.",
)

_ph_sessions: Dict[str, PhilippinesVoiceBot] = {}
_id_sessions: Dict[str, IndonesiaVoiceBot] = {}


# ---------------------------------------------------------------------------
# Philippines endpoints
# ---------------------------------------------------------------------------

class PHStartRequest(BaseModel):
    time_of_day: str = "araw"


class TurnRequest(BaseModel):
    session_id: str
    user_utterance: str


@app.post("/ph/start")
async def ph_start(req: PHStartRequest):
    session_id = str(uuid.uuid4())
    bot = PhilippinesVoiceBot(session_id=session_id)
    _ph_sessions[session_id] = bot
    greeting = bot.get_greeting(time_of_day=req.time_of_day)
    return {"session_id": session_id, "market": "PH", "greeting": greeting}


@app.post("/ph/turn")
async def ph_turn(req: TurnRequest):
    bot = _ph_sessions.get(req.session_id)
    if not bot:
        raise HTTPException(status_code=404, detail="PH session not found.")
    response = bot.respond(req.user_utterance)
    return {
        "session_id": req.session_id,
        "agent_response": response,
        "outcome": bot.outcome,
        "stage": bot.stage,
        "lead": bot.lead,
    }


@app.get("/ph/summary/{session_id}")
async def ph_summary(session_id: str):
    bot = _ph_sessions.get(session_id)
    if not bot:
        raise HTTPException(status_code=404, detail="PH session not found.")
    return bot.get_summary()


# ---------------------------------------------------------------------------
# Indonesia endpoints
# ---------------------------------------------------------------------------

class IDStartRequest(BaseModel):
    waktu: str = "pagi"
    call_type: str = "qualification"
    nama: str = "Bapak/Ibu"
    tanggal_jatuh_tempo: Optional[str] = None
    jumlah: Optional[int] = None


@app.post("/id/start")
async def id_start(req: IDStartRequest):
    session_id = str(uuid.uuid4())
    bot = IndonesiaVoiceBot(session_id=session_id, call_type=req.call_type)
    _id_sessions[session_id] = bot
    greeting = bot.get_greeting(
        waktu=req.waktu,
        nama=req.nama,
        tanggal_jatuh_tempo=req.tanggal_jatuh_tempo,
        jumlah=req.jumlah,
    )
    return {"session_id": session_id, "market": "ID", "greeting": greeting}


@app.post("/id/turn")
async def id_turn(req: TurnRequest):
    bot = _id_sessions.get(req.session_id)
    if not bot:
        raise HTTPException(status_code=404, detail="ID session not found.")
    response = bot.respond(req.user_utterance)
    return {
        "session_id": req.session_id,
        "agent_response": response,
        "outcome": bot.outcome,
        "stage": bot.stage,
        "detected_accent": bot.detected_accent,
        "lead": bot.lead,
    }


@app.get("/id/summary/{session_id}")
async def id_summary(session_id: str):
    bot = _id_sessions.get(session_id)
    if not bot:
        raise HTTPException(status_code=404, detail="ID session not found.")
    return bot.get_summary()


# ---------------------------------------------------------------------------
# Shared endpoints
# ---------------------------------------------------------------------------

@app.get("/asr-config")
async def asr_config():
    return {
        "philippines": ASR_CONFIG_PH,
        "indonesia": ASR_CONFIG_ID,
    }


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "service": "multilingual_bots",
        "ph_active_sessions": len(_ph_sessions),
        "id_active_sessions": len(_id_sessions),
    }
