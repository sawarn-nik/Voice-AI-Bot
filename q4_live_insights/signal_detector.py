"""
Signal Detector
===============
Extracts signals from the rolling transcript in real time.

Two-pass architecture
---------------------
Pass 1 — Rule-based (fast, <5ms):
  Keyword/pattern matching for high-confidence, well-defined signals.
  - Compliance keywords: "I guarantee", "100% sure", "no risk"
  - Frustration markers: "this is ridiculous", "not happy", "unbelievable"
  - Buying signals: "sounds good", "I'll take it", "sign me up"

Pass 2 — LLM-based (slower, ~400-800ms):
  GPT-4o-mini on the last N utterances for nuanced signals:
  - Missed cross-sell opportunities
  - Ambiguous objections
  - Topic shifts
  - Subtle frustration/compliance gaps

Pass 1 runs on every chunk. Pass 2 runs every 3 final chunks (batched)
to manage LLM cost and latency.

Confidence scoring
------------------
Rule-based: fixed confidence per pattern (tuned on historical calls)
LLM-based: returned by LLM as a 0.0–1.0 score, then clipped
"""

from __future__ import annotations

import re
import time
import json
from typing import List, Optional, Tuple

import openai

from q4_live_insights.models import (
    TranscriptChunk,
    DetectedSignal,
    SignalType,
    Speaker,
    CallSession,
)
from shared.config import settings
from shared.utils import logger


# ---------------------------------------------------------------------------
# Rule-based pattern library
# ---------------------------------------------------------------------------

_RULES: List[Tuple[SignalType, float, List[str]]] = [
    # (signal_type, confidence, keywords/phrases)
    (
        SignalType.RISING_FRUSTRATION, 0.85,
        [
            "this is ridiculous", "i'm not happy", "not satisfied",
            "terrible service", "waste of time", "unbelievable",
            "i've been waiting", "nobody helps", "keeps happening",
            "fed up", "so annoying", "can't believe",
        ],
    ),
    (
        SignalType.COMPLIANCE_GAP, 0.90,
        [
            "i guarantee", "i promise you", "100% sure",
            "no risk at all", "definitely approved", "guaranteed approval",
            "no waiting period", "covers everything", "full refund always",
            "never be denied", "zero charges",
        ],
    ),
    (
        SignalType.BUYING_SIGNAL, 0.80,
        [
            "sounds good", "i'll take it", "sign me up",
            "where do i sign", "let's proceed", "i'm interested",
            "that works for me", "i want to enroll", "let's go ahead",
            "i'd like to apply", "great, let's do it",
        ],
    ),
    (
        SignalType.PAYMENT_DIFFICULTY, 0.82,
        [
            "can't afford", "too expensive", "short on cash",
            "financial difficulty", "lost my job", "reduced salary",
            "can't pay right now", "struggling financially",
            "installment is too high", "need lower payment",
        ],
    ),
    (
        SignalType.CALLBACK_REQUEST, 0.88,
        [
            "call me back", "call me later", "reach me tomorrow",
            "better time", "busy right now", "call next week",
            "i'll call you", "try me again",
        ],
    ),
    (
        SignalType.ESCALATION_RISK, 0.85,
        [
            "speak to a manager", "human agent", "real person",
            "your supervisor", "file a complaint", "report this",
            "want a refund", "cancel everything", "speak to someone else",
        ],
    ),
]

# Compliance disclosure keywords that SHOULD be said by agent
_REQUIRED_DISCLOSURES = [
    "waiting period",
    "pre-existing",
    "exclusions",
    "not covered",
    "free-look period",
    "30-day",
    "premium may change",
    "subject to underwriting",
]

# Cross-sell triggers detected from customer speech
_CROSS_SELL_TRIGGERS = {
    "second car": "multi-vehicle plan",
    "second vehicle": "multi-vehicle plan",
    "another car": "multi-vehicle plan",
    "my spouse also": "joint/family plan",
    "my parents": "senior/dependent coverage",
    "starting a business": "group insurance / SME plan",
    "my employee": "group insurance plan",
    "dental": "dental add-on rider",
    "vision": "vision care add-on",
    "critical illness": "critical illness rider",
    "maternity": "maternity benefit rider",
}


class RuleBasedDetector:
    """Fast pattern-matching signal detector. Runs on every transcript chunk."""

    def detect(
        self,
        chunk: TranscriptChunk,
        session: CallSession,
    ) -> List[DetectedSignal]:
        signals: List[DetectedSignal] = []
        text_lower = chunk.text.lower()

        # Rule patterns
        for signal_type, confidence, keywords in _RULES:
            for kw in keywords:
                if kw in text_lower:
                    signals.append(
                        DetectedSignal(
                            session_id=chunk.session_id,
                            signal_type=signal_type,
                            confidence=confidence,
                            trigger_text=chunk.text,
                            speaker=chunk.speaker,
                            timestamp=chunk.timestamp,
                            metadata={"matched_keyword": kw, "detector": "rule"},
                        )
                    )
                    break  # one signal per rule per chunk

        # Cross-sell triggers (customer side only)
        if chunk.speaker == Speaker.CUSTOMER:
            for trigger, offer in _CROSS_SELL_TRIGGERS.items():
                if trigger in text_lower:
                    signals.append(
                        DetectedSignal(
                            session_id=chunk.session_id,
                            signal_type=SignalType.MISSED_CROSS_SELL,
                            confidence=0.78,
                            trigger_text=chunk.text,
                            speaker=chunk.speaker,
                            timestamp=chunk.timestamp,
                            metadata={"trigger": trigger, "offer": offer, "detector": "rule"},
                        )
                    )

        # Compliance check (agent side: did agent miss a required disclosure?)
        if chunk.speaker == Speaker.AGENT:
            full_agent_text = " ".join(
                c.text.lower()
                for c in session.chunks
                if c.speaker == Speaker.AGENT and c.is_final
            )
            # Check if we're at a policy-explanation point and disclosures are missing
            explanation_keywords = ["plan", "coverage", "premium", "enroll", "sign up"]
            if any(k in text_lower for k in explanation_keywords):
                missing = [
                    d for d in _REQUIRED_DISCLOSURES
                    if d not in full_agent_text
                ]
                if len(missing) >= 2:  # 2+ missing = flag
                    signals.append(
                        DetectedSignal(
                            session_id=chunk.session_id,
                            signal_type=SignalType.COMPLIANCE_GAP,
                            confidence=0.70,
                            trigger_text=chunk.text,
                            speaker=chunk.speaker,
                            timestamp=chunk.timestamp,
                            metadata={
                                "missing_disclosures": missing,
                                "detector": "rule_compliance",
                            },
                        )
                    )

        return signals


# ---------------------------------------------------------------------------
# LLM-based detector
# ---------------------------------------------------------------------------

LLM_SIGNAL_PROMPT = """You are a real-time call quality monitor for a health insurance sales call.
Analyze the last few utterances of this conversation and identify any signals present.

TRANSCRIPT (last utterances):
{transcript}

Identify signals from this list ONLY if clearly present (do not over-detect):
- missed_cross_sell: customer mentioned a need the agent hasn't addressed
- compliance_gap: agent made a claim that's too strong or skipped required disclosure
- rising_frustration: customer tone or words suggest increasing frustration
- payment_difficulty: customer mentioned money problems or affordability issues
- buying_signal: customer expressed interest or readiness to proceed
- callback_request: customer wants to be called back later
- topic_shift: conversation topic changed significantly
- objection: customer raised a concern or reason not to buy

Respond with JSON only:
{{
  "signals": [
    {{
      "signal_type": "<type from list above>",
      "confidence": <0.0 to 1.0>,
      "reason": "<one sentence why>",
      "trigger_quote": "<exact quote from transcript that triggered this>"
    }}
  ]
}}

If no signals are present, return: {{"signals": []}}
"""


class LLMSignalDetector:
    """Nuanced LLM-based signal detector. Uses Groq (free) or OpenAI."""

    def __init__(self, batch_size: int = 3):
        if settings.groq_api_key:
            from groq import Groq
            self._client = Groq(api_key=settings.groq_api_key)
            self._model = "llama-3.1-8b-instant"  # fastest Groq model for monitoring        else:
            self._client = openai.OpenAI(api_key=settings.openai_api_key)
            self._model = "gpt-4o-mini"
        self.batch_size = batch_size
        self._chunk_counter = 0

    def should_run(self) -> bool:
        self._chunk_counter += 1
        return self._chunk_counter % self.batch_size == 0

    def detect(
        self,
        session: CallSession,
    ) -> Tuple[List[DetectedSignal], float]:
        """
        Returns (signals, llm_latency_ms).
        """
        recent_chunks = [c for c in session.chunks if c.is_final][-8:]
        if not recent_chunks:
            return [], 0.0

        transcript = "\n".join(
            f"[{c.speaker.value.upper()}]: {c.text}" for c in recent_chunks
        )

        t0 = time.perf_counter()
        try:
            response = self._client.chat.completions.create(
                model=self._model,
                messages=[
                    {
                        "role": "user",
                        "content": LLM_SIGNAL_PROMPT.format(transcript=transcript),
                    }
                ],
                temperature=0.1,
                max_tokens=400,
                response_format={"type": "json_object"},
            )
            llm_latency_ms = (time.perf_counter() - t0) * 1000

            content = response.choices[0].message.content
            data = json.loads(content)
            signals = []

            for item in data.get("signals", []):
                try:
                    signal_type = SignalType(item["signal_type"])
                    confidence = float(item.get("confidence", 0.5))
                    signals.append(
                        DetectedSignal(
                            session_id=session.session_id,
                            signal_type=signal_type,
                            confidence=min(confidence, 1.0),
                            trigger_text=item.get("trigger_quote", ""),
                            speaker=Speaker.UNKNOWN,
                            timestamp=time.time(),
                            metadata={
                                "reason": item.get("reason", ""),
                                "detector": "llm",
                            },
                        )
                    )
                except (ValueError, KeyError):
                    pass  # skip unknown signal types

            logger.info(
                "llm_detector_run",
                session=session.session_id,
                found=len(signals),
                latency_ms=round(llm_latency_ms, 1),
            )
            return signals, llm_latency_ms

        except Exception as e:
            llm_latency_ms = (time.perf_counter() - t0) * 1000
            logger.error("llm_detector_error", error=str(e))
            return [], llm_latency_ms


# ---------------------------------------------------------------------------
# Combined detector
# ---------------------------------------------------------------------------

class SignalDetector:
    """
    Orchestrates rule-based + LLM-based detection.
    Rule-based: every chunk (fast)
    LLM-based: every 3 final chunks (accurate)
    """

    def __init__(self):
        self._rule = RuleBasedDetector()
        self._llm = LLMSignalDetector(batch_size=3)

    def process_chunk(
        self,
        chunk: TranscriptChunk,
        session: CallSession,
    ) -> Tuple[List[DetectedSignal], float, float]:
        """
        Returns (all_signals, rule_latency_ms, llm_latency_ms).
        llm_latency_ms is 0 if LLM detector did not run this chunk.
        """
        t_rule_start = time.perf_counter()
        rule_signals = self._rule.detect(chunk, session)
        rule_latency_ms = (time.perf_counter() - t_rule_start) * 1000

        llm_signals: List[DetectedSignal] = []
        llm_latency_ms = 0.0

        if chunk.is_final and self._llm.should_run():
            llm_signals, llm_latency_ms = self._llm.detect(session)

        all_signals = rule_signals + llm_signals
        return all_signals, rule_latency_ms, llm_latency_ms
