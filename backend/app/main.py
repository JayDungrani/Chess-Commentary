# backend/app/main.py

import asyncio
from contextlib import asynccontextmanager
import io
import logging
from pathlib import Path
import time
from typing import Dict, List, Optional
import uuid

import chess
import chess.pgn
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from app.config import BACKEND_DIR
from app.lichess.broadcast_streamer import (
    BroadcastGameSummary,
    LichessBroadcastStreamer,
    extract_broadcast_ids,
    parse_clock_seconds,
)
from app.engine.stockfish_pool import get_stockfish_engine, shutdown_stockfish_engine
from app.engine.opening_book import GameOpeningTracker
from app.services.broadcast_session import (
    BroadcastEventType,
    BroadcastFrame,
    BroadcastSession,
)

logger = logging.getLogger("app.api")

# In-memory registry for uploaded custom PGN/FEN games
custom_games_registry: Dict[str, dict] = {}


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


# ── Route 0: Custom PGN/FEN Upload & Registration ─────────────────────────────
class CustomGamePayload(BaseModel):
    pgn: Optional[str] = None
    fen: Optional[str] = None
    title: Optional[str] = None
    move_delay: float = 2.0


async def analyze_full_pgn_or_fen(
    game: chess.pgn.Game, engine, title: str = ""
) -> tuple[dict, list[dict]]:
    headers_dict = dict(game.headers)
    white_name = headers_dict.get("White", "White")
    black_name = headers_dict.get("Black", "Black")
    white_elo = (
        int(headers_dict["WhiteElo"])
        if headers_dict.get("WhiteElo", "").isdigit()
        else None
    )
    black_elo = (
        int(headers_dict["BlackElo"])
        if headers_dict.get("BlackElo", "").isdigit()
        else None
    )

    metadata = {
        "game_id": "",
        "speed": "classical",
        "variant": "standard",
        "rated": False,
        "white_player": {
            "username": white_name,
            "rating": white_elo,
            "title": None,
        },
        "black_player": {
            "username": black_name,
            "rating": black_elo,
            "title": None,
        },
        "event_name": title or headers_dict.get("Event", "Custom Game Studio"),
    }

    initial_fen = headers_dict.get("FEN", chess.STARTING_FEN)
    board = chess.Board(initial_fen)
    moves = list(game.mainline_moves())

    snapshots = [
        {
            "ply": 0,
            "fen": initial_fen,
            "move": None,
            "evaluation": None,
            "visualCues": None,
        }
    ]

    # If game has no moves (e.g. standalone FEN), evaluate the position directly
    if not moves:
        analysis = await engine.analyze_position(initial_fen, depth=10, movetime_ms=30)
        arrows = []
        if analysis.lines and analysis.lines[0].uci_moves:
            best_u = analysis.lines[0].uci_moves[0]
            if len(best_u) >= 4:
                arrows.append([best_u[:2], best_u[2:4], "green"])
        snapshots[0]["evaluation"] = {
            "ply": 0,
            "turn": "white" if board.turn == chess.WHITE else "black",
            "played_san": "",
            "played_uci": "",
            "fen_after": initial_fen,
            "is_book": False,
            "left_book_now": False,
            "opening_name": None,
            "eval_cp_after": analysis.score_cp,
            "mate_in_after": analysis.mate_in,
            "eval_swing_cp": 0,
            "win_prob_after": analysis.win_probability,
            "classification": "BEST",
            "is_blunder": False,
            "blunder_dossier": None,
            "should_have_played": None,
            "candidate_responses": [line.model_dump() for line in analysis.lines],
            "engine_line": analysis.lines[0].san_moves if analysis.lines else [],
            "best_line_san": analysis.lines[0].san_moves if analysis.lines else [],
            "visual_cues": {"arrows": arrows, "highlights": []},
        }
        snapshots[0]["visualCues"] = snapshots[0]["evaluation"]["visual_cues"]
        return metadata, snapshots

    opening_tracker = GameOpeningTracker()
    prev_cp = 0
    curr_node = game
    for i, move in enumerate(moves, 1):
        if curr_node.variations:
            curr_node = curr_node.variation(0)
            comment = curr_node.comment
        else:
            comment = ""

        turn_str = "white" if board.turn == chess.WHITE else "black"
        san = board.san(move)
        uci = move.uci()
        is_book, left_book_now, eco, opening_name = opening_tracker.process_move(
            board_before=board,
            move=move,
            move_san=san,
            ply=i,
        )
        board.push(move)
        fen_after = board.fen()

        clk_seconds = parse_clock_seconds(comment) if comment else None

        # Stockfish depth 10 analysis (~25ms per move)
        analysis = await engine.analyze_position(fen_after, depth=10, movetime_ms=25)
        cp = analysis.score_cp if analysis.score_cp is not None else 0
        mate = analysis.mate_in

        # Evaluation swing from mover's perspective
        swing = cp - prev_cp
        loss_cp = -swing if turn_str == "white" else swing

        if is_book:
            classification = "BOOK"
        elif loss_cp > 250:
            classification = "BLUNDER"
        elif loss_cp > 120:
            classification = "MISTAKE"
        elif loss_cp > 60:
            classification = "INACCURACY"
        elif loss_cp < -100 and abs(cp) > 150:
            classification = "BRILLIANT"
        elif loss_cp <= 15:
            classification = "BEST"
        else:
            classification = "GOOD"

        prev_cp = cp

        arrows = []
        if analysis.lines:
            top_line = analysis.lines[0]
            if top_line.uci_moves:
                best_u = top_line.uci_moves[0]
                if len(best_u) >= 4:
                    arrows.append([best_u[:2], best_u[2:4], "green"])

        if classification == "BLUNDER":
            arrows.append([uci[:2], uci[2:4], "red"])

        eval_dict = {
            "ply": i,
            "turn": turn_str,
            "played_san": san,
            "played_uci": uci,
            "fen_after": fen_after,
            "is_book": is_book,
            "left_book_now": left_book_now,
            "opening_name": opening_name,
            "eval_cp_after": cp,
            "mate_in_after": mate,
            "eval_swing_cp": swing,
            "win_prob_after": analysis.win_probability,
            "classification": classification,
            "is_blunder": classification == "BLUNDER",
            "blunder_dossier": None,
            "should_have_played": None,
            "candidate_responses": [line.model_dump() for line in analysis.lines],
            "engine_line": analysis.lines[0].san_moves if analysis.lines else [],
            "best_line_san": analysis.lines[0].san_moves if analysis.lines else [],
            "visual_cues": {"arrows": arrows, "highlights": []},
        }

        snapshots.append(
            {
                "ply": i,
                "fen": fen_after,
                "move": {
                    "ply": i,
                    "turn": turn_str,
                    "san": san,
                    "uci": uci,
                    "fen": fen_after,
                    "is_check": board.is_check(),
                    "is_checkmate": board.is_checkmate(),
                    "is_stalemate": board.is_stalemate(),
                    "is_draw": board.is_game_over() and not board.is_checkmate(),
                    "is_time_trouble": False,
                    "move_time_spent_seconds": 0.0,
                    "white_clock_seconds": clk_seconds if turn_str == "white" else None,
                    "black_clock_seconds": clk_seconds if turn_str == "black" else None,
                },
                "evaluation": eval_dict,
                "visualCues": eval_dict["visual_cues"],
            }
        )

    return metadata, snapshots


@app.post(
    "/api/custom/game",
    summary="Register and analyze custom PGN or FEN game",
    description="Loads all moves, evaluations, classifications, and candidate lines at once like chess.com analysis.",
)
async def register_custom_game(payload: CustomGamePayload, request: Request = None):
    pgn_text = (payload.pgn or "").strip()
    fen_text = (payload.fen or "").strip()

    if not pgn_text and not fen_text:
        raise HTTPException(status_code=400, detail="Either PGN text or FEN position must be provided.")

    if not pgn_text and fen_text:
        try:
            b = chess.Board(fen_text)
            pgn_text = (
                f'[Event "{payload.title or "Custom Position"}"]\n'
                f'[Site "Chess Studio"]\n'
                f'[Date "????.??.??"]\n'
                f'[White "White"]\n'
                f'[Black "Black"]\n'
                f'[FEN "{b.fen()}"]\n'
                f'[SetUp "1"]\n\n*'
            )
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"Invalid FEN string: {exc}")

    try:
        game = chess.pgn.read_game(io.StringIO(pgn_text))
        if not game:
            raise HTTPException(status_code=400, detail="Could not parse PGN content.")
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid PGN structure: {exc}")

    custom_id = f"custom_{uuid.uuid4().hex[:8]}"
    title = payload.title or game.headers.get("Event", "Custom Game Studio")

    engine = None
    if request is not None and hasattr(request, "app") and hasattr(request.app.state, "engine"):
        engine = request.app.state.engine
    if engine is None:
        engine = await get_stockfish_engine()

    metadata, snapshots = await analyze_full_pgn_or_fen(game, engine, title)
    metadata["game_id"] = custom_id
    ply_count = len(snapshots) - 1

    custom_games_registry[custom_id] = {
        "pgn": pgn_text,
        "title": title,
        "plies": ply_count,
        "metadata": metadata,
        "initial_fen": game.headers.get("FEN", chess.STARTING_FEN),
        "snapshots": snapshots,
        "move_delay": payload.move_delay,
        "created_at": time.time(),
    }

    return {
        "game_id": custom_id,
        "title": title,
        "plies": ply_count,
        "metadata": metadata,
        "initial_fen": game.headers.get("FEN", chess.STARTING_FEN),
        "snapshots": snapshots,
        "move_delay": payload.move_delay,
    }


@app.get(
    "/api/custom/game/{game_id}",
    summary="Get pre-calculated custom game analysis",
    description="Returns pre-calculated move snapshots, evaluations, and metadata for a custom game.",
)
async def get_custom_game(game_id: str):
    clean_id = game_id.strip()
    if clean_id not in custom_games_registry:
        raise HTTPException(status_code=404, detail="Custom game session not found or expired.")
    entry = custom_games_registry[clean_id]
    return {
        "game_id": clean_id,
        "title": entry.get("title", "Custom Game Studio"),
        "plies": entry.get("plies", 0),
        "metadata": entry.get("metadata"),
        "initial_fen": entry.get("initial_fen", chess.STARTING_FEN),
        "snapshots": entry.get("snapshots", []),
        "move_delay": entry.get("move_delay", 2.0),
    }


# ── Route 0.5: On-Demand Position Analysis ────────────────────────────────────
class AnalyzePositionPayload(BaseModel):
    fen: str
    depth: int = 14
    multipv: int = 3


async def _run_fen_analysis(engine, fen: str, depth: int, multipv: int):
    try:
        chess.Board(fen)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid FEN string: {exc}")

    if engine is None:
        engine = await get_stockfish_engine()

    analysis = await engine.analyze_position(fen=fen, depth=depth)
    lines = analysis.lines
    top_line = lines[0] if lines else None

    arrows = []
    if top_line and top_line.uci_moves:
        u = top_line.uci_moves[0]
        if len(u) >= 4:
            arrows.append([u[:2], u[2:4], "green"])

    return {
        "fen": fen,
        "eval_cp_after": analysis.score_cp,
        "mate_in_after": analysis.mate_in,
        "win_prob_after": analysis.win_probability,
        "depth": analysis.depth,
        "candidate_responses": [line.model_dump() for line in lines],
        "engine_line": top_line.san_moves if top_line else [],
        "best_line_san": top_line.san_moves if top_line else [],
        "visual_cues": {
            "arrows": arrows,
            "highlights": [],
        },
        "classification": "BEST",
    }


@app.get(
    "/api/engine/analyze",
    summary="Evaluate position on demand (GET)",
    description="Returns detailed Stockfish engine continuation lines and evaluation for a given FEN.",
)
async def analyze_position_get(
    request: Request,
    fen: str = Query(..., description="Target FEN string"),
    depth: int = Query(14, description="Analysis search depth"),
    multipv: int = Query(3, description="Number of candidate lines"),
):
    return await _run_fen_analysis(request.app.state.engine, fen, depth, multipv)


@app.post(
    "/api/engine/analyze",
    summary="Evaluate position on demand (POST)",
    description="Returns detailed Stockfish engine continuation lines and evaluation for a given FEN payload.",
)
async def analyze_position_post(request: Request, payload: AnalyzePositionPayload):
    return await _run_fen_analysis(
        request.app.state.engine, payload.fen, payload.depth, payload.multipv
    )


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
    delay: Optional[float] = Query(
        None, description="Pacing delay in seconds for custom PGN games"
    ),
):
    if game_id.startswith("custom_"):
        clean_id = game_id.strip()
        if clean_id not in custom_games_registry:
            raise HTTPException(status_code=404, detail="Custom game session not found or expired.")
        custom_entry = custom_games_registry[clean_id]
        pacing = delay if delay is not None else custom_entry.get("move_delay", 2.0)
        session = BroadcastSession(
            game_id=clean_id,
            round_id=None,
            replay_all=replay_all,
            enable_tts=tts,
            engine=request.app.state.engine,
            custom_pgn=custom_entry["pgn"],
            custom_move_delay=pacing,
        )
    else:
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