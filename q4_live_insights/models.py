"""
Q4 Data Models
==============
All Pydantic models for the live insights pipeline.
"""

from __future__ import annotations

from enum import Enum
from typing import Optional, List, Literal
from datetime import datetime
import uuid

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Signal taxonomy
# ---------------------------------------------------------------------------

class SignalType(str, Enum):
    MISSED_CROSS_SELL     = "missed_cross_sell"
    COMPLIANCE_GAP        = "compliance_gap"
    RISING_FRUSTRATION    = "rising_frustration"
    PAYMENT_DIFFICULTY    = "payment_difficulty"
    BUYING_SIGNAL         = "buying_signal"
    CALLBACK_REQUEST      = "callback_request"
    TOPIC_SHIFT           = "topic_shift"
    OBJECTION             = "objection"
    ESCALATION_RISK       = "escalation_risk"
    AMBIGUOUS             = "ambiguous"


class NudgePriority(str, Enum):
    HIGH   = "high"    # show immediately, prominent
    MEDIUM = "medium"  # show in standard queue
    LOW    = "low"     # informational only


class Speaker(str, Enum):
    AGENT    = "agent"
    CUSTOMER = "customer"
    UNKNOWN  = "unknown"


# ---------------------------------------------------------------------------
# Transcript chunk (one ASR result)
# ---------------------------------------------------------------------------

class TranscriptChunk(BaseModel):
    chunk_id:   str   = Field(default_factory=lambda: str(uuid.uuid4()))
    session_id: str
    speaker:    Speaker
    text:       str
    is_final:   bool  = True
    timestamp:  float = Field(..., description="Epoch seconds when chunk was received")
    asr_latency_ms: Optional[float] = None

    @property
    def received_at(self) -> datetime:
        return datetime.utcfromtimestamp(self.timestamp)


# ---------------------------------------------------------------------------
# Detected signal
# ---------------------------------------------------------------------------

class DetectedSignal(BaseModel):
    signal_id:    str         = Field(default_factory=lambda: str(uuid.uuid4()))
    session_id:   str
    signal_type:  SignalType
    confidence:   float       = Field(..., ge=0.0, le=1.0)
    trigger_text: str         = Field(..., description="The utterance that triggered this signal")
    speaker:      Speaker
    timestamp:    float
    metadata:     dict        = Field(default_factory=dict)

    @property
    def is_actionable(self) -> bool:
        from shared.config import settings
        return self.confidence >= settings.nudge_confidence_threshold


# ---------------------------------------------------------------------------
# Nudge
# ---------------------------------------------------------------------------

class Nudge(BaseModel):
    nudge_id:      str          = Field(default_factory=lambda: str(uuid.uuid4()))
    session_id:    str
    signal_type:   SignalType
    priority:      NudgePriority
    headline:      str          = Field(..., description="Short action title (≤10 words)")
    body:          str          = Field(..., description="Full actionable recommendation (1-2 sentences)")
    source_text:   str          = Field(..., description="Customer/agent utterance that triggered this")
    confidence:    float
    timestamp:     float
    expires_at:    float        = Field(..., description="Epoch seconds when nudge should be dismissed")
    delivered:     bool         = False
    suppressed:    bool         = False
    suppression_reason: Optional[str] = None

    # Latency tracking
    asr_latency_ms:    Optional[float] = None
    signal_latency_ms: Optional[float] = None
    llm_latency_ms:    Optional[float] = None
    delivery_latency_ms: Optional[float] = None

    @property
    def end_to_end_latency_ms(self) -> Optional[float]:
        parts = [self.asr_latency_ms, self.signal_latency_ms,
                 self.llm_latency_ms, self.delivery_latency_ms]
        if all(p is not None for p in parts):
            return sum(parts)
        return None


# ---------------------------------------------------------------------------
# Session state
# ---------------------------------------------------------------------------

class CallSession(BaseModel):
    session_id:    str   = Field(default_factory=lambda: str(uuid.uuid4()))
    started_at:    float = Field(default_factory=lambda: datetime.utcnow().timestamp())
    ended_at:      Optional[float] = None
    chunks:        List[TranscriptChunk] = Field(default_factory=list)
    signals:       List[DetectedSignal]  = Field(default_factory=list)
    nudges:        List[Nudge]           = Field(default_factory=list)
    topic_history: List[str]             = Field(default_factory=list)

    # Latency tracking
    latency_log:   List[dict] = Field(default_factory=list)

    @property
    def full_transcript(self) -> str:
        lines = []
        for c in self.chunks:
            if c.is_final:
                lines.append(f"[{c.speaker.value.upper()}]: {c.text}")
        return "\n".join(lines)

    @property
    def recent_transcript(self, n: int = 8) -> str:
        recent = [c for c in self.chunks if c.is_final][-n:]
        return "\n".join(f"[{c.speaker.value.upper()}]: {c.text}" for c in recent)

    def add_latency(self, stage: str, latency_ms: float) -> None:
        self.latency_log.append({
            "stage": stage,
            "latency_ms": latency_ms,
            "timestamp": datetime.utcnow().isoformat(),
        })


# ---------------------------------------------------------------------------
# Latency report
# ---------------------------------------------------------------------------

class LatencyReport(BaseModel):
    session_id: str
    total_nudges: int
    p50_e2e_ms: Optional[float]
    p95_e2e_ms: Optional[float]
    avg_asr_ms: Optional[float]
    avg_signal_ms: Optional[float]
    avg_llm_ms: Optional[float]
    avg_delivery_ms: Optional[float]
    component_breakdown: dict
