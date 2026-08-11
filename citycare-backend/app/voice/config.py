"""Telephony VoiceBot configuration and URL normalization helpers."""

import os
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class VoiceSettings(BaseSettings):
    public_base_url: str = "http://localhost:8000"
    twilio_account_sid: Optional[str] = None
    twilio_auth_token: Optional[str] = None
    twilio_phone_number: Optional[str] = None
    deepgram_api_key: Optional[str] = None
    sarvam_api_key: Optional[str] = None

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


def get_voice_settings() -> VoiceSettings:
    return VoiceSettings()


def get_normalized_base_url() -> str:
    """Return cleaned base URL without trailing slashes."""
    settings = get_voice_settings()
    url = os.getenv("PUBLIC_BASE_URL") or os.getenv("TWILIO_PUBLIC_URL") or settings.public_base_url
    url = url.strip().rstrip("/")
    return url


def get_websocket_stream_url() -> str:
    """
    Generate normalized WebSocket URL for Twilio Media Stream TwiML.
    Converts https://abc.ngrok-free.app -> wss://abc.ngrok-free.app/voice/ws
    or http://localhost:8000 -> ws://localhost:8000/voice/ws
    """
    base_url = get_normalized_base_url()
    if base_url.startswith("https://"):
        ws_base = "wss://" + base_url[len("https://"):]
    elif base_url.startswith("http://"):
        ws_base = "ws://" + base_url[len("http://"):]
    elif base_url.startswith("wss://") or base_url.startswith("ws://"):
        ws_base = base_url
    else:
        ws_base = "wss://" + base_url

    return f"{ws_base}/voice/ws"
