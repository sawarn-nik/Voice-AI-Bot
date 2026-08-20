"""
Voice Agent Core
================
Uses groq/compound-mini (best free context handling) without function calling.
Lead fields extracted via a fast post-processing parser on the conversation.
"""

from __future__ import annotations

import json
import re
import uuid
from typing import Optional, List

import httpx

from q1_voice_agent.prompts import (
    SYSTEM_PROMPT,
    FALLBACK_RESPONSE,
    ESCALATION_RESPONSE,
    QUALIFICATION_FLOW,
)
from q1_voice_agent.qualification import QualificationState
from q2_knowledge_base.retriever import Retriever
from shared.config import settings
from shared.utils import logger


# ---------------------------------------------------------------------------
# LLM factory — no function calling, plain chat completion
# ---------------------------------------------------------------------------

def _get_llm_client():
    from shared.providers import get_llm_router
    return get_llm_router()


# ---------------------------------------------------------------------------
# Lightweight lead field extractor (regex-based, no LLM needed)
# ---------------------------------------------------------------------------

def _extract_lead_fields(utterance: str) -> dict:
    """
    Extract lead fields from a customer utterance using fast regex patterns.
    Returns only fields that are clearly present — never guesses.
    """
    text = utterance.lower()
    fields = {}

    # Age — "I am 34", "I'm 22 years old", "age is 30"
    m = re.search(r"\b(?:i(?:'m| am)|age is|aged?)\s+(\d{2})\b", text)
    if m:
        fields["age"] = int(m.group(1))

    # Smoker
    if re.search(r"\b(i smoke|i am a smoker|i'm a smoker)\b", text):
        fields["smoker"] = True
    elif re.search(r"\b(don'?t smoke|not a smoker|non.?smoker|neither.*smok|no.*smok)\b", text):
        fields["smoker"] = False

    # Pre-existing conditions
    if re.search(r"\b(no pre.?existing|no.*condition|healthy|no.*health issue)\b", text):
        fields["has_preexisting"] = False
    elif re.search(r"\b(have.*condition|pre.?existing|diabetes|hypertension|asthma)\b", text):
        fields["has_preexisting"] = True

    # Budget — "4500", "php 4,500", "4500 a month"
    m = re.search(r"(?:php\s*)?(\d[\d,]+)\s*(?:php|pesos?|a month|per month|/month|monthly)?", text)
    if m:
        budget = int(m.group(1).replace(",", ""))
        if 500 <= budget <= 50000:  # sanity range
            fields["monthly_budget"] = budget

    # Phone — PH mobile format
    m = re.search(r"0?9\d{9}", utterance)
    if m:
        fields["contact_number"] = m.group(0)

    # Email
    m = re.search(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}", utterance)
    if m:
        fields["email"] = m.group(0)

    # Name — "my name is X", "I am X", "this is X"
    m = re.search(r"(?:my name is|i(?:'m| am)|this is)\s+([A-Z][a-z]+(?: [A-Z][a-z]+)+)", utterance)
    if m:
        fields["name"] = m.group(1)

    # Dependents
    if re.search(r"\bfor myself\b|\bjust me\b|\bindividual\b|\bonly me\b", text):
        fields["num_dependents"] = 0
    m = re.search(r"\b(one|1)\s+(?:spouse|wife|husband)\b", text)
    if m:
        fields["num_dependents"] = 1
    m = re.search(r"\b(\d+)\s+(?:depend|child|kid|member)", text)
    if m:
        fields["num_dependents"] = int(m.group(1))

    # Callback time
    for kw in ["morning", "afternoon", "evening", "monday", "tuesday", "wednesday",
               "thursday", "friday", "saturday", "sunday", "weekend", "weekday"]:
        if kw in text:
            fields["callback_time"] = utterance.strip()
            break

    return fields


# ---------------------------------------------------------------------------
# Voice Agent
# ---------------------------------------------------------------------------

class VoiceAgent:
    def __init__(self, session_id: str = None, caller_name: str = "there"):
        self.session_id = session_id or str(uuid.uuid4())
        self.caller_name = caller_name
        self.state = QualificationState(session_id=self.session_id)
        self._retriever = Retriever()
        self._llm = _get_llm_client()
        logger.info("voice_agent_init", session_id=self.session_id)

    def respond(self, user_utterance: str) -> str:
        logger.info("agent_user_turn", session_id=self.session_id, text=user_utterance[:100])
        self.state.add_turn("user", user_utterance)

        # Escalation check
        if self._is_escalation_request(user_utterance):
            self.state.escalation_requested = True
            self.state.stage = "escalated"
            self.state.add_turn("assistant", ESCALATION_RESPONSE)
            return ESCALATION_RESPONSE

        # Always extract lead fields from utterance (fast, no API call)
        fields = _extract_lead_fields(user_utterance)
        if fields:
            self._apply_lead_fields(fields)

        # KB retrieval — skip for very short or data-only turns
        kb_context = ""
        if len(user_utterance.split()) >= 5 and not self._is_data_only(user_utterance):
            kb_context, _ = self._retriever.search_grounded(
                query=user_utterance,
                top_k=settings.kb_top_k,
            )

        messages = self._build_messages(kb_context)
        response_text = self._call_llm(messages)

        self._parse_outcome_tags(response_text)
        clean_response = self._strip_tags(response_text)

        # Guard: never return empty
        if not clean_response.strip():
            clean_response = self._continuation_prompt()

        self.state.add_turn("assistant", clean_response)
        logger.info("agent_response", session_id=self.session_id, response=clean_response[:100])
        return clean_response

    # ------------------------------------------------------------------
    # LLM
    # ------------------------------------------------------------------

    def _build_messages(self, kb_context: str) -> List[dict]:
        context_block = f"\n\n[KNOWLEDGE BASE CONTEXT]\n{kb_context}" if kb_context else ""
        system = SYSTEM_PROMPT + QUALIFICATION_FLOW + context_block
        messages = [{"role": "system", "content": system}]
        messages.extend(self.state.conversation_history[-14:])
        return messages

    def _call_llm(self, messages: List[dict]) -> str:
        try:
            result = self._llm.chat(messages, max_tokens=500, temperature=0.4)
            return result or ""
        except Exception as e:
            logger.error("llm_api_error", error=str(e)[:120])
            return FALLBACK_RESPONSE

    # ------------------------------------------------------------------
    # Lead field application
    # ------------------------------------------------------------------

    def _apply_lead_fields(self, fields: dict) -> None:
        lead = self.state.lead
        for k, v in fields.items():
            if hasattr(lead, k) and v is not None:
                setattr(lead, k, v)
                logger.info("lead_field_updated", field=k, value=v)
        # Auto-recommend plan when budget + dependents known
        if lead.monthly_budget and lead.plan_interest is None:
            rec = self.state.recommend_plan()
            if rec:
                lead.plan_interest = rec

    # ------------------------------------------------------------------
    # Continuation fallback
    # ------------------------------------------------------------------

    def _continuation_prompt(self) -> str:
        """Called when LLM returns empty — generate a minimal continuation."""
        lead = self.state.lead
        if not lead.name:
            return "Could I get your full name to continue?"
        if not lead.contact_number:
            return "What's the best phone number to reach you?"
        if not lead.monthly_budget:
            return "And roughly what monthly budget did you have in mind for health coverage?"
        return "Thank you! Let me put together the best recommendation for you."

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _is_data_only(self, text: str) -> bool:
        """True when utterance is just providing a value, not asking a question."""
        stripped = text.strip()
        if re.search(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}", stripped):
            return True
        if re.search(r"0?9\d{9}", stripped):
            return True
        short_answers = {"yes","no","sure","okay","ok","yep","nope","correct","right",
                         "please","thanks","thank you","sms","email","morning","afternoon",
                         "evening","monday","tuesday","wednesday","thursday","friday"}
        if stripped.lower().rstrip(".,!") in short_answers:
            return True
        return False

    _ESCALATION_TRIGGERS = [
        "speak to a human", "speak to a person", "talk to someone",
        "transfer me", "human agent", "real person", "supervisor",
        "manager", "escalate", "not happy", "this is ridiculous",
    ]

    def _is_escalation_request(self, text: str) -> bool:
        return any(t in text.lower() for t in self._ESCALATION_TRIGGERS)

    def _parse_outcome_tags(self, text: str) -> None:
        if "[ESCALATE]" in text:
            self.state.escalation_requested = True
            self.state.stage = "escalated"
        elif "[QUALIFIED]" in text:
            self.state.stage = "done"
            self.state.outcome = "QUALIFIED"
        elif "[NOT_QUALIFIED]" in text:
            self.state.stage = "done"
            self.state.outcome = "NOT_QUALIFIED"
        elif "[FOLLOW_UP]" in text:
            self.state.stage = "closing"
            self.state.outcome = "FOLLOW_UP"

    def _strip_tags(self, text: str) -> str:
        return re.sub(r"\[(QUALIFIED|NOT_QUALIFIED|FOLLOW_UP|ESCALATE)\]", "", text).strip()

    def get_call_summary(self) -> str:
        self.state.finalize_outcome()
        return self.state.to_summary()

    def get_lead_crm_payload(self) -> dict:
        self.state.finalize_outcome()
        return {**self.state.lead.to_crm_dict(), "outcome": self.state.outcome, "turns": self.state.turns}


# ---------------------------------------------------------------------------
# TTS — Edge-TTS (primary, free, no API key)
# ElevenLabs kept as optional enhancement if key is present
# ---------------------------------------------------------------------------

def _build_tts_client():
    return None  # Edge-TTS needs no client object


async def text_to_speech(text: str, language: str = "en") -> bytes:
    """
    TTS priority: Edge-TTS (free) → ElevenLabs (if key present)
    Edge-TTS: en-US-AriaNeural for English
    """
    from shared.providers import EdgeTTSProvider
    tts = EdgeTTSProvider()
    audio = await tts.synthesize(text, language=language)
    if audio:
        return audio

    # ElevenLabs fallback (optional)
    if settings.elevenlabs_api_key:
        try:
            from elevenlabs.client import ElevenLabs
            client = ElevenLabs(api_key=settings.elevenlabs_api_key)
            result = client.generate(text=text, voice="EXAVITQu4vr4xnSDxMaL", model="eleven_turbo_v2")
            return b"".join(result)
        except Exception as e:
            logger.warning("elevenlabs_tts_failed", error=str(e))

    return b""
