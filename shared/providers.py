"""
Provider Abstractions
=====================
Per Require.md section 30 — all provider-specific calls go here.
Swap providers by changing config, not application code.

LLMProvider   : GroqProvider (primary) → GeminiProvider (fallback)
STTProvider   : GroqWhisperProvider
TTSProvider   : EdgeTTSProvider
EmbeddingProvider : LocalEmbeddingProvider (sentence-transformers)
                    → GeminiEmbeddingProvider (fallback)
"""

from __future__ import annotations

import asyncio
import io
import os
import time
from typing import List, Optional
from shared.config import settings
from shared.utils import logger


# ===========================================================================
# LLM
# ===========================================================================

class LLMProvider:
    def chat(self, messages: List[dict], max_tokens: int = 500, temperature: float = 0.4) -> str:
        raise NotImplementedError


class GroqProvider(LLMProvider):
    def __init__(self):
        from groq import Groq
        self._client = Groq(api_key=settings.groq_api_key)
        self._model = "groq/compound-mini"
        logger.info("llm_provider", provider="groq", model=self._model)

    def chat(self, messages: List[dict], max_tokens: int = 500, temperature: float = 0.4) -> str:
        resp = self._client.chat.completions.create(
            model=self._model,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        return resp.choices[0].message.content or ""


class GeminiProvider(LLMProvider):
    def __init__(self):
        from google import genai
        self._client = genai.Client(api_key=settings.google_api_key)
        self._model = "gemini-2.5-flash"
        logger.info("llm_provider", provider="gemini", model=self._model)

    def chat(self, messages: List[dict], max_tokens: int = 500, temperature: float = 0.4) -> str:
        from google.genai import types
        # Convert OpenAI-style messages to Gemini format
        system_parts = [m["content"] for m in messages if m["role"] == "system"]
        conv_messages = [m for m in messages if m["role"] != "system"]

        gemini_msgs = []
        for m in conv_messages:
            role = "user" if m["role"] == "user" else "model"
            gemini_msgs.append(types.Content(role=role, parts=[types.Part(text=m["content"])]))

        system_instruction = "\n".join(system_parts) if system_parts else None

        resp = self._client.models.generate_content(
            model=self._model,
            contents=gemini_msgs,
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                max_output_tokens=max_tokens,
                temperature=temperature,
            ),
        )
        return resp.text or ""


class LLMRouter(LLMProvider):
    """
    Routes to Groq first. Falls back to Gemini on 429/timeout/failure.
    Per Require.md section 21.
    """
    def __init__(self):
        self._primary: Optional[LLMProvider] = None
        self._fallback: Optional[LLMProvider] = None

        if settings.groq_api_key:
            try:
                self._primary = GroqProvider()
            except Exception as e:
                logger.warning("groq_init_failed", error=str(e))

        if settings.google_api_key:
            try:
                self._fallback = GeminiProvider()
            except Exception as e:
                logger.warning("gemini_init_failed", error=str(e))

        if not self._primary and not self._fallback:
            raise RuntimeError("No LLM provider configured. Set GROQ_API_KEY or GOOGLE_API_KEY.")

    def chat(self, messages: List[dict], max_tokens: int = 500, temperature: float = 0.4) -> str:
        if self._primary:
            try:
                return self._primary.chat(messages, max_tokens, temperature)
            except Exception as e:
                err = str(e)
                if any(k in err for k in ["429", "timeout", "rate", "overloaded", "unavailable"]):
                    logger.warning("llm_primary_failed_fallback", error=err[:80])
                else:
                    logger.error("llm_primary_error", error=err[:80])
                    # Still fall through to fallback

        if self._fallback:
            try:
                return self._fallback.chat(messages, max_tokens, temperature)
            except Exception as e:
                logger.error("llm_fallback_error", error=str(e)[:80])

        return ""


# ===========================================================================
# STT — Groq Whisper
# ===========================================================================

class STTProvider:
    def transcribe(self, audio_bytes: bytes, language: str = "en", filename: str = "audio.wav") -> str:
        raise NotImplementedError


class GroqWhisperProvider(STTProvider):
    """
    Groq Whisper — free, fast, multilingual.
    Supports: en, tl (Tagalog), id (Indonesian), and 90+ languages.
    Model: whisper-large-v3-turbo
    """
    def __init__(self):
        from groq import Groq
        self._client = Groq(api_key=settings.groq_api_key)
        self._model = "whisper-large-v3-turbo"
        logger.info("stt_provider", provider="groq_whisper", model=self._model)

    def transcribe(self, audio_bytes: bytes, language: str = "en", filename: str = "audio.wav") -> str:
        t0 = time.perf_counter()
        audio_file = io.BytesIO(audio_bytes)
        audio_file.name = filename
        try:
            resp = self._client.audio.transcriptions.create(
                file=audio_file,
                model=self._model,
                language=language if language != "tl" else None,  # Whisper auto-detects Tagalog
                response_format="text",
            )
            latency_ms = (time.perf_counter() - t0) * 1000
            text = str(resp).strip()
            logger.info("stt_transcribed", latency_ms=round(latency_ms, 1), chars=len(text))
            return text
        except Exception as e:
            logger.error("stt_error", error=str(e))
            return ""


# ===========================================================================
# TTS — Edge-TTS (no API key, free, multilingual)
# ===========================================================================

EDGE_TTS_VOICES = {
    "en":    "en-US-AriaNeural",
    "en-US": "en-US-AriaNeural",
    "en-PH": "en-US-AriaNeural",        # closest available
    "fil-PH": "fil-PH-BlessicaNeural",  # native Filipino female voice
    "id-ID": "id-ID-GadisNeural",       # native Indonesian female voice
}


class TTSProvider:
    async def synthesize(self, text: str, language: str = "en") -> bytes:
        raise NotImplementedError


class EdgeTTSProvider(TTSProvider):
    """
    Edge-TTS — Microsoft's neural TTS, free, no API key required.
    Filipino and Indonesian voices available natively.
    """
    async def synthesize(self, text: str, language: str = "en") -> bytes:
        import edge_tts
        voice = EDGE_TTS_VOICES.get(language, EDGE_TTS_VOICES["en"])
        try:
            communicate = edge_tts.Communicate(text, voice)
            audio_chunks = []
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    audio_chunks.append(chunk["data"])
            result = b"".join(audio_chunks)
            logger.info("tts_synthesized", provider="edge_tts", voice=voice, chars=len(text))
            return result
        except Exception as e:
            logger.error("tts_error", error=str(e))
            return b""

    def synthesize_sync(self, text: str, language: str = "en") -> bytes:
        return asyncio.run(self.synthesize(text, language))


# ===========================================================================
# Embeddings — Google Gemini (free, API already configured)
# with local hash-based fallback if network unavailable
# ===========================================================================

EMBEDDING_DIM = 3072  # gemini-embedding-001


class EmbeddingProvider:
    def embed(self, texts: List[str]) -> List[List[float]]:
        raise NotImplementedError

    def embed_one(self, text: str) -> List[float]:
        return self.embed([text])[0]


class GeminiEmbeddingProvider(EmbeddingProvider):
    """Google gemini-embedding-001 — free tier, 3072 dims, multilingual."""
    def __init__(self):
        from google import genai
        self._client = genai.Client(api_key=settings.google_api_key)
        logger.info("embedding_provider", provider="gemini", model="gemini-embedding-001")

    def embed(self, texts: List[str]) -> List[List[float]]:
        from google.genai import types
        vectors = []
        for text in texts:
            result = self._client.models.embed_content(
                model="gemini-embedding-001",
                contents=text,
                config=types.EmbedContentConfig(task_type="RETRIEVAL_DOCUMENT"),
            )
            vectors.append(list(result.embeddings[0].values))
        return vectors


class LocalHashEmbeddingProvider(EmbeddingProvider):
    """
    Deterministic hash-based embeddings — zero network, zero cost.
    Poor retrieval quality but pipeline runs fully offline.
    Used only when no API key available.
    """
    def embed(self, texts: List[str]) -> List[List[float]]:
        import hashlib, math
        vectors = []
        for text in texts:
            seed = int(hashlib.md5(text.encode()).hexdigest(), 16)
            rng = seed
            vec = []
            for _ in range(EMBEDDING_DIM):
                rng = (rng * 1664525 + 1013904223) & 0xFFFFFFFF
                vec.append((rng / 0xFFFFFFFF) * 2 - 1)
            mag = math.sqrt(sum(v * v for v in vec))
            vectors.append([v / mag for v in vec])
        return vectors


def get_embedding_provider() -> EmbeddingProvider:
    if settings.google_api_key:
        try:
            return GeminiEmbeddingProvider()
        except Exception as e:
            logger.warning("gemini_embed_init_failed", error=str(e))
    logger.warning("using_hash_embeddings_no_api_key")
    return LocalHashEmbeddingProvider()


def get_llm_router() -> LLMRouter:
    return LLMRouter()


def get_stt_provider() -> GroqWhisperProvider:
    return GroqWhisperProvider()


def get_tts_provider() -> EdgeTTSProvider:
    return EdgeTTSProvider()
