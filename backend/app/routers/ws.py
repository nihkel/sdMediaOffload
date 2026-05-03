import asyncio
import json
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from ..services.ws_broker import broker


router = APIRouter()
log = logging.getLogger("sdoffload.ws")


@router.websocket("/progress")
async def progress(ws: WebSocket):
    await ws.accept()
    q = broker.subscribe()
    try:
        while True:
            try:
                payload = await asyncio.wait_for(q.get(), timeout=15)
                await ws.send_text(json.dumps(payload, default=str))
            except asyncio.TimeoutError:
                await ws.send_text(json.dumps({"type": "ping"}))
    except WebSocketDisconnect:
        pass
    except Exception:
        log.exception("ws error")
    finally:
        broker.unsubscribe(q)
