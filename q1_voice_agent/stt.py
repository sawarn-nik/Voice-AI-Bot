"""
Speech-to-Text
==============
Supports two backends — selected automatically based on available API keys:

  1. OpenAI Whisper (file-based) — works with just OPENAI_API_KEY
     Used for the web demo: user types OR uploads a short audio clip.

  2. Deepgram Nova-2 (streaming) — requires DEEPGRAM_API_KEY
     Used for real Twilio PSTN calls and live streaming.

For the web calling interface (POST /web-call/turn), text is passed directly
so STT is not needed at all — the browser sends typed text.

For the Q4 live insights demo, audio is simulated from transcript text,
so no STT is required there either.

STT is only strictly needed when connecting a real phone/microphone.
"""

from __future__ import annotations

import asyncio
import io
import time
from typing import Callable, Optional

from shared.config import settings
from shared.utils import logger


# ---------------------------------------------------------------------------
# OpenAI Whisper STT (file-based, works with just OPENAI_API_KEY)
# ---------------------------------------------------------------------------

class WhisperSTT:
    """
    Transcribes audio using OpenAI Whisper API.
    Accepts raw audio bytes (wav/mp3/webm) and returns a transcript string.

    This is the default when Deepgram is not configured.
    Not streaming — processes complete utterances (suitable for web demo).
    Latency: ~500ms–1.5s depending on audio length.
    """

    def __init__(self, language: str = "en"):
        import openai
        self._client = openai.OpenAI(api_key=settings.openai_api_key)
        self.language = language

    def transcribe(self, audio_bytes: bytes, filename: str = "audio.wav") -> str:
        """
        Transcribe audio bytes to text.
        audio_bytes: raw audio data (wav, mp3, webm, m4a all accepted)
        Returns transcript string, or "" on failure.
        """
        t0 = time.perf_counter()
        try:
            audio_file = io.BytesIO(audio_bytes)
            audio_file.name = filename

            response = self._client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file,
                language=self.language,
            )
            latency_ms = (time.perf_counter() - t0) * 1000
            text = response.text.strip()
            logger.info("whisper_transcribed", latency_ms=round(latency_ms, 1), chars=len(text))
            return text
        except Exception as e:
            logger.error("whisper_error", error=str(e))
            return ""

    async def transcribe_async(self, audio_bytes: bytes, filename: str = "audio.wav") -> str:
        """Async wrapper — runs Whisper in a thread pool to avoid blocking."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.transcribe, audio_bytes, filename)


# ---------------------------------------------------------------------------
# Deepgram Nova-2 STT (streaming, requires DEEPGRAM_API_KEY)
# ---------------------------------------------------------------------------

class DeepgramSTT:
    """
    Real-time streaming STT using Deepgram Nova-2.
    Only instantiated when DEEPGRAM_API_KEY is set.

    on_transcript(text: str, is_final: bool, speaker: int) is called
    whenever Deepgram returns a result.
    """

    def __init__(
        self,
        on_transcript: Callable[[str, bool, int], None],
        language: str = "en-US",
        sample_rate: int = 8000,
        encoding: str = "mulaw",
    ):
        self.on_transcript = on_transcript
        self.language = language
        self.sample_rate = sample_rate
        self.encoding = encoding
        self._connection = None

        try:
            from deepgram import DeepgramClient
            self._client = DeepgramClient(settings.deepgram_api_key)
        except ImportError:
            logger.warning("deepgram_sdk_not_installed")
            self._client = None

    async def connect(self) -> None:
        if not self._client:
            logger.error("deepgram_unavailable")
            return

        from deepgram import LiveTranscriptionEvents, LiveOptions
        options = LiveOptions(
            model="nova-2",
            language=self.language,
            smart_format=True,
            diarize=True,
            interim_results=True,
            utterance_end_ms=1000,
            encoding=self.encoding,
            sample_rate=self.sample_rate,
            channels=1,
        )
        self._connection = self._client.listen.asynclive.v("1")
        self._connection.on(LiveTranscriptionEvents.Transcript, self._on_transcript_event)
        self._connection.on(LiveTranscriptionEvents.Error, self._on_error_event)
        await self._connection.start(options)
        logger.info("deepgram_connected", language=self.language)

    async def send_audio(self, chunk: bytes) -> None:
        if self._connection:
            await self._connection.send(chunk)

    async def close(self) -> None:
        if self._connection:
            await self._connection.finish()

    async def _on_transcript_event(self, *args, **kwargs) -> None:
        result = kwargs.get("result")
        if not result:
            return
        try:
            alt = result.channel.alternatives[0]
            text = alt.transcript.strip()
            if not text:
                return
            is_final = result.is_final
            speaker = alt.words[0].speaker if alt.words else 0
            self.on_transcript(text, is_final, speaker)
        except Exception as e:
            logger.error("transcript_parse_error", error=str(e))

    async def _on_error_event(self, *args, **kwargs) -> None:
        logger.error("deepgram_error", detail=str(kwargs))


# ---------------------------------------------------------------------------
# Factory — picks the right backend automatically
# ---------------------------------------------------------------------------

def get_stt(language: str = "en") -> WhisperSTT:
    """
    Returns a WhisperSTT instance.
    Deepgram streaming is used directly in the Twilio WebSocket handler
    when DEEPGRAM_API_KEY is available.
    """
    return WhisperSTT(language=language)


# ---------------------------------------------------------------------------
# Language configs (for documentation / Q3 reference)
# ---------------------------------------------------------------------------

LANGUAGE_CONFIGS = {
    "en-PH": {
        "primary":  "Deepgram nova-2-general (tl+en) — if key available",
        "fallback": "Whisper-1 with language='tl'",
        "note": "Taglish handled well by both; Whisper slightly better on mixed sentences",
    },
    "fil-PH": {
        "primary":  "Deepgram nova-2-general, language=tl",
        "fallback": "Whisper-1, language='tl'",
        "note": "po/ho particles occasionally dropped",
    },
    "id-ID": {
        "primary":  "Deepgram nova-2-general, language=id",
        "fallback": "Whisper-1, language='id'",
        "note": "Javanese accent WER ~17%; Sundanese ~19%",
    },
}


def get_stt_config(market: str) -> dict:
    return LANGUAGE_CONFIGS.get(market, LANGUAGE_CONFIGS["en-PH"])
