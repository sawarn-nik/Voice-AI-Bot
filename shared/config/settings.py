"""
Centralised settings loaded from environment variables.
Uses pydantic-settings so every field is typed and validated at startup.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Literal


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # OpenAI
    openai_api_key: str = ""

    # Groq
    groq_api_key: str = ""
    groq_stt_model: str = "whisper-large-v3-turbo"
    groq_llm_model: str = "groq/compound-mini"

    # Gemini (LLM fallback + embeddings)
    gemini_api_key: str = ""
    gemini_llm_model: str = "models/gemini-2.5-flash"

    # TTS
    tts_provider: str = "edge"
    tts_voice_en: str = "en-US-AriaNeural"
    tts_voice_filipino: str = "fil-PH-BlessicaNeural"
    tts_voice_indonesian: str = "id-ID-GadisNeural"

    # Database
    database_url: str = "sqlite:///./darwix.db" 

    # Google AI Studio (free tier — Gemini embeddings)
    google_api_key: str = ""

    # Deepgram
    deepgram_api_key: str = ""

    # ElevenLabs
    elevenlabs_api_key: str = ""

    # Twilio
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_phone_number: str = ""

    # Pinecone
    pinecone_api_key: str = ""
    pinecone_environment: str = "us-east-1-aws"
    pinecone_index_name: str = "darwix-kb"

    # Qdrant (local on-disk — no Docker needed)
    qdrant_host: str = "localhost"
    qdrant_port: int = 6333
    qdrant_collection: str = "darwix_kb"
    qdrant_path: str = "q2_knowledge_base/embeddings"  # local folder, no server needed

    # Redis
    redis_url: str = "redis://localhost:6379"

    # App
    app_env: Literal["development", "production"] = "development"
    app_port: int = 8000
    log_level: str = "INFO"
    secret_key: str = "change-me-in-production"

    # Knowledge Base
    kb_chunk_size: int = 400
    kb_chunk_overlap: int = 80
    kb_embedding_model: str = "text-embedding-3-small"
    kb_top_k: int = 5

    # Voice Agent
    voice_agent_model: str = "gpt-4o"
    voice_agent_use_case: str = "health_insurance_lead"
    voice_agent_language: str = "en-US"

    # Live Insights
    nudge_confidence_threshold: float = 0.65
    nudge_cooldown_seconds: int = 30
    nudge_max_active: int = 5
    stream_chunk_seconds: int = 3


settings = Settings()
