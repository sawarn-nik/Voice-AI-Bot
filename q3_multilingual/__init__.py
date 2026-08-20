"""
Q3 — Native-Language Voice Bots
Philippines (Taglish) and Indonesia (Bahasa Indonesia)
"""
from .philippines.agent_ph import PhilippinesVoiceBot
from .indonesia.agent_id import IndonesiaVoiceBot

__all__ = ["PhilippinesVoiceBot", "IndonesiaVoiceBot"]
