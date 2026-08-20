"""
Real-Time Streaming Pipeline
==============================
Orchestrates the full Q4 flow:

  Audio chunks → ASR → TranscriptChunk → SignalDetector → NudgeEngine → WebSocket push

Supports two input modes:
  1. Live: real audio streamed from Deepgram (production)
  2. Simulation: a saved transcript replayed at real-time speed (demo/testing)
     — this is what the assessment calls "a recording replayed at real-time speed in chunks"

Latency measurement points:
  T0 = audio chunk received
  T1 = ASR final transcript returned        → ASR latency = T1 - T0
  T2 = signals extracted                    → signal latency = T2 - T1
  T3 = nudge generated (incl. LLM if used) → LLM latency = T3 - T2
  T4 = nudge pushed to WebSocket/dashboard  → delivery latency = T4 - T3
  E2E latency = T4 - T0

P50/P95 computed over all nudge deliveries in the session.
"""

from __future__ import annotations

import asyncio
import json
import time
from typing import AsyncGenerator, Callable, Dict, List, Optional, Awaitable

import numpy as np

from q4_live_insights.models import (
    TranscriptChunk,
    DetectedSignal,
    Nudge,
    Speaker,
    CallSession,
)
from q4_live_insights.signal_detector import SignalDetector
from q4_live_insights.nudge_engine import NudgeEngine
from shared.config import settings
from shared.utils import logger


NudgeCallback = Callable[[Nudge], Awaitable[None]]


class LiveInsightsPipeline:
    """
    Stateful pipeline for a single call session.

    Usage
    -----
        pipeline = LiveInsightsPipeline(session_id, on_nudge=push_to_websocket)

        # Simulation mode
        await pipeline.run_simulation(transcript_turns)

        # Live mode — feed chunks as they arrive from Deepgram
        await pipeline.process_chunk(text, speaker, asr_latency_ms)
    """

    def __init__(
        self,
        session_id: str,
        on_nudge: Optional[NudgeCallback] = None,
    ):
        self.session = CallSession(session_id=session_id)
        self._signal_detector = SignalDetector()
        self._nudge_engine = NudgeEngine(session_id=session_id)
        self._on_nudge = on_nudge
        self._e2e_latencies: List[float] = []
        logger.info("pipeline_init", session_id=session_id)

    # ------------------------------------------------------------------
    # Public: process one transcript chunk
    # ------------------------------------------------------------------

    async def process_chunk(
        self,
        text: str,
        speaker: Speaker,
        asr_latency_ms: float = 0.0,
        is_final: bool = True,
    ) -> List[Nudge]:
        """
        Process one transcribed chunk through the full pipeline.
        Returns any nudges generated this chunk.
        """
        if not text.strip():
            return []

        t_received = time.perf_counter()

        chunk = TranscriptChunk(
            session_id=self.session.session_id,
            speaker=speaker,
            text=text,
            is_final=is_final,
            timestamp=time.time(),
            asr_latency_ms=asr_latency_ms,
        )
        self.session.chunks.append(chunk)

        # Skip very short utterances from LLM analysis (noise reduction)
        if len(text.split()) < 4 and speaker == Speaker.CUSTOMER:
            return []

        # Signal detection
        t_signal_start = time.perf_counter()
        signals, rule_latency_ms, llm_latency_ms = self._signal_detector.process_chunk(
            chunk, self.session
        )
        signal_latency_ms = (time.perf_counter() - t_signal_start) * 1000

        # Add signals to session
        self.session.signals.extend(signals)

        if not signals:
            return []

        # Nudge generation
        nudges = self._nudge_engine.process_signals(
            signals=signals,
            session=self.session,
            signal_latency_ms=signal_latency_ms,
            asr_latency_ms=asr_latency_ms,
        )

        # Deliver nudges
        for nudge in nudges:
            t_deliver = time.perf_counter()
            self.session.nudges.append(nudge)
            nudge.delivered = True

            delivery_latency_ms = (time.perf_counter() - t_deliver) * 1000
            nudge.delivery_latency_ms = delivery_latency_ms

            e2e = (time.perf_counter() - t_received) * 1000 + asr_latency_ms
            self._e2e_latencies.append(e2e)

            self.session.add_latency("e2e", e2e)

            logger.info(
                "nudge_delivered",
                session_id=self.session.session_id,
                nudge_id=nudge.nudge_id,
                signal_type=nudge.signal_type.value,
                e2e_ms=round(e2e, 1),
                priority=nudge.priority.value,
            )

            if self._on_nudge:
                await self._on_nudge(nudge)

        return nudges

    # ------------------------------------------------------------------
    # Simulation mode
    # ------------------------------------------------------------------

    async def run_simulation(
        self,
        turns: List[dict],
        realtime_speed: bool = True,
    ) -> Dict:
        """
        Replay a transcript at real-time speed.

        turns format:
            [{"speaker": "agent"|"customer", "text": "...", "delay_s": 2.5}, ...]

        delay_s = simulated pause before this utterance (mimics natural speech gaps).
        asr_latency is simulated as Deepgram's typical 200-400ms.

        Returns session summary with latency report.
        """
        logger.info(
            "simulation_start",
            session_id=self.session.session_id,
            turns=len(turns),
        )

        import random

        for turn in turns:
            if realtime_speed:
                delay = turn.get("delay_s", 1.5)
                await asyncio.sleep(delay)

            speaker = Speaker.AGENT if turn["speaker"] == "agent" else Speaker.CUSTOMER
            # Simulate ASR latency (Deepgram Nova-2: 200-400ms)
            simulated_asr_ms = random.uniform(200, 420)

            await self.process_chunk(
                text=turn["text"],
                speaker=speaker,
                asr_latency_ms=simulated_asr_ms,
                is_final=True,
            )

        return self.get_session_summary()

    # ------------------------------------------------------------------
    # Latency reporting
    # ------------------------------------------------------------------

    def get_latency_report(self) -> dict:
        """Compute P50/P95 end-to-end latency and component breakdown."""
        if not self._e2e_latencies:
            return {"message": "No nudges generated yet."}

        arr = np.array(self._e2e_latencies)

        # Per-component averages from nudge records
        nudges_with_all = [
            n for n in self.session.nudges
            if n.asr_latency_ms is not None and n.llm_latency_ms is not None
        ]

        avg_asr = np.mean([n.asr_latency_ms for n in nudges_with_all]) if nudges_with_all else None
        avg_signal = np.mean([n.signal_latency_ms for n in nudges_with_all]) if nudges_with_all else None
        avg_llm = np.mean([n.llm_latency_ms for n in nudges_with_all]) if nudges_with_all else None
        avg_delivery = np.mean([n.delivery_latency_ms for n in nudges_with_all]) if nudges_with_all else None

        return {
            "session_id": self.session.session_id,
            "total_nudges": len(self.session.nudges),
            "total_signals": len(self.session.signals),
            "e2e_latency": {
                "p50_ms": round(float(np.percentile(arr, 50)), 1),
                "p95_ms": round(float(np.percentile(arr, 95)), 1),
                "min_ms": round(float(arr.min()), 1),
                "max_ms": round(float(arr.max()), 1),
            },
            "component_latency_avg_ms": {
                "asr":      round(avg_asr, 1) if avg_asr else "N/A",
                "signal_detection": round(avg_signal, 1) if avg_signal else "N/A",
                "llm":      round(avg_llm, 1) if avg_llm else "N/A",
                "delivery": round(avg_delivery, 1) if avg_delivery else "N/A",
            },
        }

    def get_session_summary(self) -> dict:
        nudges = self.session.nudges
        return {
            "session_id": self.session.session_id,
            "total_chunks": len(self.session.chunks),
            "total_signals": len(self.session.signals),
            "total_nudges": len(nudges),
            "nudge_breakdown": _breakdown(nudges),
            "latency_report": self.get_latency_report(),
            "transcript_preview": self.session.full_transcript[:1000],
        }

    def get_active_nudges(self) -> List[Nudge]:
        return self._nudge_engine.get_active_nudges()

    def dismiss_nudge(self, nudge_id: str) -> None:
        self._nudge_engine.dismiss_nudge(nudge_id)


def _breakdown(nudges: List[Nudge]) -> dict:
    from collections import Counter
    counts = Counter(n.signal_type.value for n in nudges)
    return dict(counts)
