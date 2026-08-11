"""FastAPI routes for Twilio voice webhook and WebSocket media stream."""

import json
from typing import Optional
from fastapi import APIRouter, Form, Request, Response, WebSocket, WebSocketDisconnect
from app.voice.config import get_websocket_stream_url
from app.voice.pipeline import run_voice_pipeline
from app.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/voice", tags=["Telephony VoiceBot"])


@router.post("/incoming")
@router.get("/incoming")
async def incoming_voice_webhook(
    request: Request,
    CallSid: Optional[str] = Form(None),
    From: Optional[str] = Form(None),
):
    """
    Twilio voice webhook endpoint.
    Returns TwiML XML instructing Twilio to open a WebSocket media stream to /voice/ws.
    """
    call_sid = CallSid or "anonymous"
    from_number = From or "unknown"
    logger.info("Incoming phone call received from %s [CallSid=%s]", from_number, call_sid)

    stream_url = get_websocket_stream_url()
    twiml_xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Connect>
        <Stream url="{stream_url}">
            <Parameter name="call_sid" value="{call_sid}" />
            <Parameter name="from_number" value="{from_number}" />
        </Stream>
    </Connect>
</Response>"""

    return Response(content=twiml_xml, media_type="application/xml")


@router.websocket("/ws")
async def voice_websocket_stream(websocket: WebSocket):
    """
    WebSocket endpoint handling Twilio Media Stream audio events.
    Parses initial Twilio start event, then hands over to the Pipecat voice pipeline.
    """
    await websocket.accept()
    logger.info("WebSocket connection established on /voice/ws")

    stream_sid: Optional[str] = None
    call_sid: str = "default"

    try:
        # Wait for Twilio's initial 'connected' / 'start' event
        while not stream_sid:
            data_text = await websocket.receive_text()
            event_data = json.loads(data_text)
            event_type = event_data.get("event")

            if event_type == "start":
                start_data = event_data.get("start", {})
                stream_sid = start_data.get("streamSid") or event_data.get("streamSid")
                call_sid = start_data.get("callSid") or start_data.get("customParameters", {}).get("call_sid") or "default"
                logger.info("Twilio Media Stream started [StreamSid=%s, CallSid=%s]", stream_sid, call_sid)
                break
            elif event_type == "stop":
                logger.info("Twilio Media Stream stopped before start [CallSid=%s]", call_sid)
                await websocket.close()
                return

        if stream_sid:
            # Launch Pipecat real-time voice audio pipeline
            await run_voice_pipeline(websocket, stream_sid, call_sid)

    except WebSocketDisconnect:
        logger.info("WebSocket disconnected for CallSid=%s", call_sid)
    except Exception as exc:
        logger.error("Error in voice WebSocket stream handler [CallSid=%s]: %s", call_sid, exc)
    finally:
        logger.info("Closed voice WebSocket session for CallSid=%s", call_sid)
