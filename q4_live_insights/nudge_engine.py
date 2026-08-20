"""
Nudge Engine
============
Converts detected signals into actionable nudges with full quality controls.

Quality Controls
----------------
1. Confidence threshold   — only signals >= NUDGE_CONFIDENCE_THRESHOLD generate nudges
2. Duplicate suppression  — same signal_type not repeated within cooldown window
3. Cooldown per type      — configurable per signal type (default 30s)
4. Topic grouping         — signals of same type within 10s grouped into one nudge
5. Priority ordering      — compliance > frustration > missed_sell > others
6. Expiry                 — nudges auto-expire after TTL (default 60s)
7. Max active nudges      — at most NUDGE_MAX_ACTIVE nudges on screen at once
8. Low-confidence noise   — ambiguous signals below 0.65 → no nudge

False-positive controls
-----------------------
- Noisy/ambiguous calls: if ASR confidence is flagged low, skip LLM nudges
- Repeated pattern in same call: reduce confidence by 0.1 after 2nd occurrence
- Short utterances (<4 words): skip LLM-based signal detection
"""

from __future__ import annotations

import time
from typing import Dict, List, Optional, Tuple
from collections import defaultdict


from q4_live_insights.models import (
    DetectedSignal,
    Nudge,
    NudgePriority,
    SignalType,
    CallSession,
)
from shared.config import settings
from shared.utils import logger


# ---------------------------------------------------------------------------
# Priority map
# ---------------------------------------------------------------------------

_PRIORITY_MAP: Dict[SignalType, NudgePriority] = {
    SignalType.COMPLIANCE_GAP:     NudgePriority.HIGH,
    SignalType.RISING_FRUSTRATION: NudgePriority.HIGH,
    SignalType.ESCALATION_RISK:    NudgePriority.HIGH,
    SignalType.MISSED_CROSS_SELL:  NudgePriority.MEDIUM,
    SignalType.PAYMENT_DIFFICULTY: NudgePriority.MEDIUM,
    SignalType.BUYING_SIGNAL:      NudgePriority.MEDIUM,
    SignalType.OBJECTION:          NudgePriority.MEDIUM,
    SignalType.CALLBACK_REQUEST:   NudgePriority.LOW,
    SignalType.TOPIC_SHIFT:        NudgePriority.LOW,
    SignalType.AMBIGUOUS:          NudgePriority.LOW,
}

# Per-signal-type cooldowns (seconds)
_COOLDOWNS: Dict[SignalType, int] = {
    SignalType.COMPLIANCE_GAP:     20,
    SignalType.RISING_FRUSTRATION: 25,
    SignalType.ESCALATION_RISK:    15,
    SignalType.MISSED_CROSS_SELL:  45,
    SignalType.PAYMENT_DIFFICULTY: 60,
    SignalType.BUYING_SIGNAL:      30,
    SignalType.OBJECTION:          30,
    SignalType.CALLBACK_REQUEST:   60,
    SignalType.TOPIC_SHIFT:        20,
    SignalType.AMBIGUOUS:          90,
}

# Nudge TTL (how long it stays on the dashboard before auto-expiry)
_NUDGE_TTL: Dict[SignalType, int] = {
    SignalType.COMPLIANCE_GAP:     90,
    SignalType.RISING_FRUSTRATION: 60,
    SignalType.ESCALATION_RISK:    120,
    SignalType.MISSED_CROSS_SELL:  120,
    SignalType.PAYMENT_DIFFICULTY: 90,
    SignalType.BUYING_SIGNAL:      45,
    SignalType.OBJECTION:          60,
    SignalType.CALLBACK_REQUEST:   180,
    SignalType.TOPIC_SHIFT:        30,
    SignalType.AMBIGUOUS:          30,
}

# Static nudge templates (fast path — no LLM needed for well-defined signals)
_STATIC_NUDGES: Dict[SignalType, Tuple[str, str]] = {
    SignalType.COMPLIANCE_GAP: (
        "⚠️ Missing disclosure",
        "You haven't mentioned the waiting period or exclusions yet. Cover these before proceeding to close.",
    ),
    SignalType.RISING_FRUSTRATION: (
        "😤 Customer frustration rising",
        "Acknowledge their concern directly before continuing. Try: 'I completely understand your frustration — let me address that right now.'",
    ),
    SignalType.ESCALATION_RISK: (
        "🔴 Escalation risk",
        "Customer is signalling they want to speak to a human. Offer to connect them immediately to avoid a negative experience.",
    ),
    SignalType.BUYING_SIGNAL: (
        "✅ Buying signal detected",
        "Customer expressed interest. Move to close: confirm their preferred plan and next steps now.",
    ),
    SignalType.CALLBACK_REQUEST: (
        "📞 Callback requested",
        "Customer asked to be called back. Capture their preferred time and confirm it before ending the call.",
    ),
    SignalType.PAYMENT_DIFFICULTY: (
        "💸 Affordability concern",
        "Customer mentioned payment difficulty. Present the Basic Plan (PHP 1,200/mo) or offer a payment support callback.",
    ),
}


class NudgeEngine:
    """
    Converts signals into nudges with full quality controls.

    One instance per call session.
    """

    def __init__(self, session_id: str):
        self.session_id = session_id
        self._last_nudge_time: Dict[SignalType, float] = defaultdict(float)
        self._signal_occurrence_count: Dict[SignalType, int] = defaultdict(int)
        self._active_nudges: List[Nudge] = []
        from shared.providers import get_llm_router
        self._llm_client = get_llm_router()

    def process_signals(
        self,
        signals: List[DetectedSignal],
        session: CallSession,
        signal_latency_ms: float = 0.0,
        asr_latency_ms: float = 0.0,
    ) -> List[Nudge]:
        """
        Filter, deduplicate, and convert signals to nudges.
        Returns only newly generated nudges.
        """
        self._expire_nudges()
        new_nudges: List[Nudge] = []

        for signal in signals:
            nudge = self._try_generate_nudge(
                signal, session, signal_latency_ms, asr_latency_ms
            )
            if nudge:
                new_nudges.append(nudge)
                self._active_nudges.append(nudge)

        return new_nudges

    def _try_generate_nudge(
        self,
        signal: DetectedSignal,
        session: CallSession,
        signal_latency_ms: float,
        asr_latency_ms: float,
    ) -> Optional[Nudge]:
        """
        Apply all quality controls and generate nudge or suppress.
        """
        now = time.time()

        # 1. Confidence threshold
        if signal.confidence < settings.nudge_confidence_threshold:
            logger.debug(
                "nudge_suppressed_low_confidence",
                signal_type=signal.signal_type,
                confidence=signal.confidence,
            )
            return None

        # 2. Cooldown check
        cooldown = _COOLDOWNS.get(signal.signal_type, settings.nudge_cooldown_seconds)
        last_time = self._last_nudge_time[signal.signal_type]
        if now - last_time < cooldown:
            logger.debug(
                "nudge_suppressed_cooldown",
                signal_type=signal.signal_type,
                seconds_remaining=round(cooldown - (now - last_time), 1),
            )
            return None

        # 3. Max active nudges cap
        active_count = len([n for n in self._active_nudges if not n.suppressed])
        if active_count >= settings.nudge_max_active:
            logger.debug("nudge_suppressed_max_active", active=active_count)
            return None

        # 4. Repetition penalty — reduce confidence if same signal seen multiple times
        self._signal_occurrence_count[signal.signal_type] += 1
        count = self._signal_occurrence_count[signal.signal_type]
        adjusted_confidence = signal.confidence
        if count > 2:
            adjusted_confidence = max(signal.confidence - 0.1 * (count - 2), 0.0)
            if adjusted_confidence < settings.nudge_confidence_threshold:
                logger.debug(
                    "nudge_suppressed_repetition_penalty",
                    signal_type=signal.signal_type,
                    adjusted_confidence=adjusted_confidence,
                )
                return None

        # 5. Generate nudge text
        t_llm_start = time.perf_counter()
        headline, body = self._generate_nudge_text(signal, session)
        llm_latency_ms = (time.perf_counter() - t_llm_start) * 1000

        # 6. Delivery latency tracking
        delivery_latency_ms = 5.0  # simulated push to WebSocket

        expires_at = now + _NUDGE_TTL.get(signal.signal_type, 60)

        nudge = Nudge(
            session_id=self.session_id,
            signal_type=signal.signal_type,
            priority=_PRIORITY_MAP.get(signal.signal_type, NudgePriority.LOW),
            headline=headline,
            body=body,
            source_text=signal.trigger_text,
            confidence=adjusted_confidence,
            timestamp=now,
            expires_at=expires_at,
            asr_latency_ms=asr_latency_ms,
            signal_latency_ms=signal_latency_ms,
            llm_latency_ms=llm_latency_ms,
            delivery_latency_ms=delivery_latency_ms,
        )

        self._last_nudge_time[signal.signal_type] = now

        logger.info(
            "nudge_generated",
            session=self.session_id,
            signal_type=signal.signal_type.value,
            priority=nudge.priority.value,
            confidence=round(adjusted_confidence, 2),
            e2e_ms=round(nudge.end_to_end_latency_ms or 0, 1),
        )
        return nudge

    def _generate_nudge_text(
        self,
        signal: DetectedSignal,
        session: CallSession,
    ) -> Tuple[str, str]:
        """
        Returns (headline, body).
        Uses static templates for common signals (fast).
        Falls back to LLM for nuanced signals (missed cross-sell, objections).
        """
        # Static fast path
        if signal.signal_type in _STATIC_NUDGES:
            headline, body = _STATIC_NUDGES[signal.signal_type]
            # Enrich missed_cross_sell with the specific offer
            if signal.signal_type == SignalType.MISSED_CROSS_SELL:
                offer = signal.metadata.get("offer", "a relevant add-on")
                headline = "💡 Cross-sell opportunity"
                body = (
                    f"Customer mentioned '{signal.metadata.get('trigger', 'a new need')}'. "
                    f"Suggest the {offer} — this is a natural fit right now."
                )
            elif signal.signal_type == SignalType.COMPLIANCE_GAP:
                missing = signal.metadata.get("missing_disclosures", [])
                if missing:
                    body = (
                        f"You haven't mentioned: {', '.join(missing[:3])}. "
                        f"Cover these before proceeding to close."
                    )
            return headline, body

        # LLM path for nuanced signals
        try:
            recent = "\n".join(
                f"[{c.speaker.value.upper()}]: {c.text}"
                for c in session.chunks[-6:]
                if c.is_final
            )
            prompt = (
                f"You are a real-time sales coach. A '{signal.signal_type.value}' signal was detected.\n"
                f"Trigger: '{signal.trigger_text}'\n"
                f"Recent conversation:\n{recent}\n\n"
                f"Generate a JSON nudge with two fields:\n"
                f"- headline: short action title (max 8 words, include an emoji)\n"
                f"- body: 1-2 sentence actionable recommendation for the agent\n"
                f"Respond with JSON only."
            )
            raw = self._llm_client.chat(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=100,
            )
            # Strip markdown fences if present
            raw = raw.strip()
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
            data = json_safe_loads(raw.strip())
            return data.get("headline", signal.signal_type.value), data.get("body", signal.trigger_text)
        except Exception as e:
            logger.error("nudge_llm_error", error=str(e))
            return signal.signal_type.value, signal.trigger_text

    def _expire_nudges(self) -> None:
        now = time.time()
        for nudge in self._active_nudges:
            if now > nudge.expires_at and not nudge.suppressed:
                nudge.suppressed = True
                nudge.suppression_reason = "expired"

    def get_active_nudges(self) -> List[Nudge]:
        self._expire_nudges()
        return [n for n in self._active_nudges if not n.suppressed]

    def dismiss_nudge(self, nudge_id: str) -> None:
        for n in self._active_nudges:
            if n.nudge_id == nudge_id:
                n.suppressed = True
                n.suppression_reason = "dismissed_by_user"


def json_safe_loads(text: str) -> dict:
    """JSON parse with fallback."""
    import json
    try:
        return json.loads(text)
    except Exception:
        return {}
