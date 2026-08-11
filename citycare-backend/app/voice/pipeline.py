"""Pipecat real-time audio pipeline for Twilio Media Stream calls."""

import asyncio
from typing import Optional
from fastapi import WebSocket
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineTask, PipelineParams
from pipecat.transports.websocket.fastapi import FastAPIWebsocketTransport, FastAPIWebsocketParams
from pipecat.serializers.twilio import TwilioFrameSerializer
from pipecat.audio.vad.silero import SileroVADAnalyzer
from app.voice.config import get_voice_settings
from app.voice.processor import CityCareVoiceProcessor
from app.voice.service import clear_call_session
from app.utils.logger import get_logger

logger = get_logger(__name__)


async def run_voice_pipeline(websocket: WebSocket, stream_sid: str, call_sid: str = "default") -> None:
    """
    Build and execute the real-time Pipecat telephony audio pipeline:
    Twilio WS -> FastAPIWebsocketTransport -> VAD -> Deepgram STT
    -> CityCareVoiceProcessor (Handbook RAG + Gemini) -> Sarvam TTS
    -> FastAPIWebsocketTransport -> Twilio WS.
    """
    settings = get_voice_settings()
    logger.info("Initializing Pipecat voice pipeline for CallSid=%s, StreamSid=%s", call_sid, stream_sid)

    # 1. Twilio Audio Serializer & Transport
    serializer = TwilioFrameSerializer(
        stream_sid=stream_sid,
        params=TwilioFrameSerializer.InputParams(auto_hang_up=False)
    )
    transport_params = FastAPIWebsocketParams(
        add_wav_header=False,
        serializer=serializer,
    )
    transport = FastAPIWebsocketTransport(
        websocket=websocket,
        params=transport_params,
    )

    # 2. VAD
    try:
        vad = SileroVADAnalyzer()
    except Exception as exc:
        logger.warning("SileroVADAnalyzer unavailable, falling back without VAD: %s", exc)
        vad = None

    # 3. Deepgram STT (Speech-to-Text)
    stt = None
    deepgram_key = settings.deepgram_api_key
    if deepgram_key and not deepgram_key.startswith("your-"):
        try:
            from pipecat.services.deepgram.stt import DeepgramSTTService
            stt = DeepgramSTTService(api_key=deepgram_key)
        except Exception as exc:
            logger.warning("Failed to initialize DeepgramSTTService: %s", exc)

    # 4. Sarvam TTS (Text-to-Speech)
    tts = None
    sarvam_key = settings.sarvam_api_key
    if sarvam_key and not sarvam_key.startswith("your-"):
        try:
            from pipecat.services.sarvam.tts import SarvamTTSService
            tts = SarvamTTSService(api_key=sarvam_key)
        except Exception as exc:
            logger.warning("Failed to initialize SarvamTTSService: %s", exc)

    # 5. CityCare Voice Processor (Handbook RAG + Gemini AI)
    voice_processor = CityCareVoiceProcessor(call_sid=call_sid)

    # 6. Assemble Pipeline
    pipeline_steps = [transport.input()]
    if stt:
        pipeline_steps.append(stt)
    pipeline_steps.append(voice_processor)
    if tts:
        pipeline_steps.append(tts)
    pipeline_steps.append(transport.output())

    pipeline = Pipeline(pipeline_steps)

    task = PipelineTask(
        pipeline,
        params=PipelineParams(allow_interruptions=True)
    )

    runner = PipelineRunner()

    try:
        logger.info("Starting Pipecat voice pipeline runner [CallSid=%s]", call_sid)
        await runner.run(task)
    except asyncio.CancelledError:
        logger.info("Voice pipeline cancelled for CallSid=%s", call_sid)
    except Exception as exc:
        logger.error("Error executing voice pipeline for CallSid=%s: %s", call_sid, exc)
    finally:
        clear_call_session(call_sid)
        logger.info("Cleaned up voice session for CallSid=%s", call_sid)
