# backend/app/api/broadcast.py

import asyncio
import json
import logging
from dataclasses import is_dataclass, asdict
from typing import Any, List, Optional

from fastapi import APIRouter, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.lichess.broadcast_streamer import LichessBroadcastStreamer, BroadcastGameSummary
from app.services.broadcast_session import (
    BroadcastSession,
    BroadcastFrame,
    BroadcastEventType,
    resolve_session_targets_async,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/broadcast", tags=["broadcast"])


def frame_to_dict(frame: BroadcastFrame) -> dict:
    """Safely serializes BroadcastFrame containing Pydantic models and dataclasses."""
    try:
        return frame.model_dump(mode="json")
    except Exception:
        data = {}
        for k, v in frame.__dict__.items():
            if is_dataclass(v):
                data[k] = asdict(v)
            elif isinstance(v, BaseModel):
                data[k] = v.model_dump(mode="json")
            else:
                data[k] = v
        return data


# ── 1. List Tournament Games ──────────────────────────────────────────────────

@router.get("/round/{round_id}/games", response_model=List[BroadcastGameSummary])
async def get_round_games(round_id: str):
    """
    Fetches all games and boards within a Lichess tournament round.
    Useful for frontends to render match selectors.
    """
    try:
        streamer = LichessBroadcastStreamer(round_id=round_id)
        games = await streamer.list_games()
        return games
    except Exception as exc:
        logger.error(f"Failed to fetch games for round {round_id}: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


# ── 2. Server-Sent Events (SSE) Stream ────────────────────────────────────────

@router.get("/stream")
async def stream_broadcast_sse(
    game_id: str = Query(..., description="Lichess game ID, board number, or broadcast URL"),
    round_id: Optional[str] = Query(None, description="Lichess broadcast round ID if tournament"),
    replay_all: bool = Query(False, description="Replay entire match from move 1"),
    enable_tts: bool = Query(True, description="Enable ElevenLabs TTS audio synthesis"),
):
    """Streams live broadcast frames over Server-Sent Events (SSE)."""
    resolved_game, resolved_round = await resolve_session_targets_async(game_id, round_id)

    session = BroadcastSession(
        game_id=resolved_game,
        round_id=resolved_round,
        replay_all=replay_all,
        enable_tts=enable_tts,
    )

    async def event_generator():
        try:
            async for frame in session.stream_broadcast():
                payload = json.dumps(frame_to_dict(frame))
                yield f"event: {frame.event_type.value}\ndata: {payload}\n\n"

                if frame.event_type == BroadcastEventType.TERMINATION:
                    break
        except asyncio.CancelledError:
            pass
        finally:
            await session.stop()

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ── 3. WebSocket Real-Time Stream ─────────────────────────────────────────────

@router.websocket("/ws")
async def broadcast_websocket(websocket: WebSocket):
    """
    WebSocket endpoint for bidirectional real-time match commentary.
    Query parameters:
      - game_id: Target game ID or URL
      - round_id: (Optional) Round ID
      - replay_all: (Optional) bool
      - enable_tts: (Optional) bool
    """
    await websocket.accept()

    query_params = websocket.query_params
    raw_target = query_params.get("game_id")
    raw_round = query_params.get("round_id")
    replay_all = query_params.get("replay_all", "false").lower() == "true"
    enable_tts = query_params.get("enable_tts", "true").lower() == "true"

    if not raw_target:
        await websocket.send_json({
            "event_type": BroadcastEventType.ERROR.value,
            "error": "Query parameter 'game_id' is required.",
        })
        await websocket.close(code=1008)
        return

    resolved_game, resolved_round = await resolve_session_targets_async(raw_target, raw_round)

    session = BroadcastSession(
        game_id=resolved_game,
        round_id=resolved_round,
        replay_all=replay_all,
        enable_tts=enable_tts,
    )

    client_listen_task: Optional[asyncio.Task] = None

    async def handle_client_messages():
        """Listens for inbound control actions (like client abort requests)."""
        try:
            while True:
                msg = await websocket.receive_text()
                try:
                    data = json.loads(msg)
                    if data.get("action") == "stop":
                        await session.stop()
                        break
                except Exception:
                    pass
        except (WebSocketDisconnect, asyncio.CancelledError):
            pass

    try:
        client_listen_task = asyncio.create_task(handle_client_messages())

        async for frame in session.stream_broadcast():
            frame_dict = frame_to_dict(frame)
            await websocket.send_json(frame_dict)

            if frame.event_type == BroadcastEventType.TERMINATION:
                break

    except WebSocketDisconnect:
        logger.info(f"WebSocket client disconnected from game: {resolved_game}")
    except Exception as exc:
        logger.error(f"WebSocket session exception: {exc}", exc_info=True)
        try:
            await websocket.send_json({
                "event_type": BroadcastEventType.ERROR.value,
                "error": str(exc),
            })
        except Exception:
            pass
    finally:
        if client_listen_task and not client_listen_task.done():
            client_listen_task.cancel()
        await session.stop()
        try:
            await websocket.close()
        except Exception:
            pass