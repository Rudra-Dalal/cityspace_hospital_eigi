"""Custom Pipecat frame processor integrating Deepgram STT, CityCare AI Handbook RAG, and Sarvam TTS."""

from pipecat.processors.frame_processor import FrameProcessor, FrameDirection
from pipecat.frames.frames import Frame, TranscriptionFrame, TTSTextFrame
from app.voice.service import run_voice_chat
from app.utils.logger import get_logger

logger = get_logger(__name__)


class CityCareVoiceProcessor(FrameProcessor):
    """
    Pipecat pipeline stage that intercepts STT user speech transcriptions,
    queries the existing CityCare Handbook RAG + Gemini AI, and sends
    the grounded natural answer text to the TTS service.
    """

    def __init__(self, call_sid: str = "default"):
        super().__init__()
        self.call_sid = call_sid

    async def process_frame(self, frame: Frame, direction: FrameDirection = FrameDirection.DOWNSTREAM):
        await super().process_frame(frame, direction)

        if isinstance(frame, TranscriptionFrame):
            text = (frame.text or "").strip()
            if text:
                logger.info("VoiceBot received transcript [CallSid=%s]: %s", self.call_sid, text)
                # Generate grounded response using Handbook RAG & Gemini
                answer_text = await run_voice_chat(text, self.call_sid)
                logger.info("VoiceBot generated answer [CallSid=%s]: %s", self.call_sid, answer_text)

                # Send text to Sarvam TTS pipeline stage
                await self.push_frame(TTSTextFrame(text=answer_text), direction)
                return

        await self.push_frame(frame, direction)
