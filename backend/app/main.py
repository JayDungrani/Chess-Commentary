# backend/app/main.py

import asyncio
from contextlib import asynccontextmanager
import logging
from pathlib import Path
from typing import List

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles

from app.config import BACKEND_DIR
from app.lichess.broadcast_streamer import (
    BroadcastGameSummary,
    LichessBroadcastStreamer,
    extract_broadcast_ids,
)
from app.engine.stockfish_pool import get_stockfish_engine, shutdown_stockfish_engine
from app.services.broadcast_session import (
    BroadcastEventType,
    BroadcastFrame,
    BroadcastSession,
)

logger = logging.getLogger("app.api")


# ── Application Lifespan (Startup & Teardown) ─────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.active_sessions = set()
    app.state.engine = await get_stockfish_engine()
    yield
    # Terminate all active SSE sessions cleanly on shutdown (Ctrl+C)
    for session in list(app.state.active_sessions):
        await session.stop()
    await shutdown_stockfish_engine()


# ── Single App Initialization ─────────────────────────────────────────────────
app = FastAPI(
    title="Live Chess Commentary API",
    description="Real-time chess broadcast and commentary engine",
    version="1.0.0",
    lifespan=lifespan,
)

# ── CORS Middleware ───────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Mount Static Audio Directory ──────────────────────────────────────────────
AUDIO_DIR = (BACKEND_DIR / "static" / "audio").resolve()
AUDIO_DIR.mkdir(parents=True, exist_ok=True)

app.mount(
    "/static/audio",
    StaticFiles(directory=str(AUDIO_DIR)),
    name="audio",
)

logger.info(f"📁 Static audio mounted to: {AUDIO_DIR}")


# ── SSE Stream Helper ─────────────────────────────────────────────────────────
async def _stream_session_sse(session: BroadcastSession, request: Request):
    """
    Streams BroadcastFrames via Server-Sent Events (SSE).
    Monitors client disconnects and cleans up sessions on termination or cancellation.
    """
    request.app.state.active_sessions.add(session)
    try:
        async for frame in session.stream_broadcast():
            if await request.is_disconnected():
                logger.info(f"Client disconnected from game {session.game_id}")
                break

            yield f"data: {frame.model_dump_json()}\n\n"

            if frame.event_type in (BroadcastEventType.TERMINATION, BroadcastEventType.ERROR):
                break

    except (asyncio.CancelledError, GeneratorExit):
        logger.info(f"Stream cancelled for game {session.game_id}")
    except Exception as exc:
        logger.error(f"SSE stream error: {exc}", exc_info=True)
        err_frame = BroadcastFrame(
            event_type=BroadcastEventType.ERROR,
            game_id=session.game_id,
            round_id=session.round_id,
            error=str(exc),
        )
        yield f"data: {err_frame.model_dump_json()}\n\n"
    finally:
        request.app.state.active_sessions.discard(session)
        await session.stop()


# ── Route 1: Live Casual Game Stream ──────────────────────────────────────────
@app.get(
    "/api/stream/game/{game_id}",
    summary="Stream live casual game",
    description="Streams real-time analysis, visual cues, and commentary frames for a standalone Lichess game ID via SSE.",
)
async def stream_casual_game(
    game_id: str,
    request: Request,
    replay_all: bool = Query(
        False, description="If true, replays and evaluates all moves from ply 1"
    ),
    tts: bool = Query(True, description="Enable ElevenLabs audio generation"),
):
    clean_id = game_id.strip().rstrip("/").split("/")[-1][:8]
    if len(clean_id) < 8:
        raise HTTPException(status_code=400, detail="Invalid 8-character Lichess Game ID.")

    session = BroadcastSession(
        game_id=clean_id,
        round_id=None,
        replay_all=replay_all,
        enable_tts=tts,
        engine=request.app.state.engine,
    )

    return StreamingResponse(
        _stream_session_sse(session, request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ── Route 2: Live Event / Broadcast Game Stream ───────────────────────────────
@app.get(
    "/api/stream/broadcast/{round_id}/{game_id}",
    summary="Stream live tournament broadcast game",
    description="Streams real-time moves and commentary for a specific board within a FIDE/Lichess broadcast round via SSE.",
)
async def stream_broadcast_game(
    round_id: str,
    game_id: str,
    request: Request,
    replay_all: bool = Query(
        False, description="If true, replays and evaluates all moves from ply 1"
    ),
    tts: bool = Query(True, description="Enable ElevenLabs audio generation"),
):
    extracted_round, _ = extract_broadcast_ids(round_id)
    target_game = game_id.strip().rstrip("/").split("/")[-1]

    if not extracted_round:
        raise HTTPException(status_code=400, detail="Invalid broadcast Round ID.")

    session = BroadcastSession(
        game_id=target_game,
        round_id=extracted_round,
        replay_all=replay_all,
        enable_tts=tts,
        engine=request.app.state.engine,
    )

    return StreamingResponse(
        _stream_session_sse(session, request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ── Route 3: Live Event Round Overview & Games List ───────────────────────────
@app.get(
    "/api/broadcast/{round_id}/games",
    response_model=List[BroadcastGameSummary],
    summary="Get round games and live standings",
    description="Fetches live board pairing summaries, active scores, players, and current status for all matches in a tournament round.",
)
async def get_broadcast_round_games(round_id: str):
    extracted_round, _ = extract_broadcast_ids(round_id)
    if not extracted_round:
        raise HTTPException(status_code=400, detail="Invalid broadcast Round ID.")

    try:
        streamer = LichessBroadcastStreamer(round_id=extracted_round)
        games: List[BroadcastGameSummary] = await streamer.list_games()
        return games
    except Exception as exc:
        logger.error(f"Failed to fetch games for round {extracted_round}: {exc}")
        raise HTTPException(
            status_code=502,
            detail=f"Unable to load broadcast data from Lichess relay: {str(exc)}",
        )


@app.get("/health")
async def health_check():
    return {"status": "online"}