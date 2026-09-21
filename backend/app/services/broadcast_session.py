# backend/app/services/broadcast_session.py

import argparse
import asyncio
import io
import logging
import re
import sys
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, AsyncGenerator, Optional, Tuple

import aiohttp
import chess
import chess.pgn
from google.genai import types
from pydantic import BaseModel, ConfigDict, Field

CURRENT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = CURRENT_DIR.parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.append(str(BACKEND_DIR))

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

from app.config import settings
from app.lichess.game_streamer import LichessGameStreamer
from app.lichess.broadcast_streamer import (
    LichessBroadcastStreamer,
    split_pgn_blocks,
    extract_game_id_from_game,
    parse_clock_seconds,
)
from app.lichess.pacing_buffer import PacedMoveStreamer
from app.lichess.pgn_parser import (
    ChessStateTracker,
    GameMetadata,
    PlayerInfo,
    ParsedMoveEvent,
    GameTerminationEvent,
    PonderingEvent,
)
from app.engine.stockfish_pool import StockfishEngine
from app.engine.opening_book import OpeningBook, GameOpeningTracker
from app.engine.analyzer import MoveAnalyzer
from app.engine.schemas import MoveEvaluation, MoveClassification, VisualCue
from app.commentary.director import BroadcastDirector
from app.commentary.agent import CommentaryAgent
from app.commentary.prompts import SYSTEM_PROMPT
from app.commentary.schemas import (
    CommentaryExchange,
    CommentatorRole,
    CommentaryEmotion,
    SpeakingDynamic,
    CommentaryPriority,
    DialogueTurn,
)
from app.services.tts_service import TTSService

# ANSI Terminal Colors
C_RESET = "\033[0m"
C_BOLD = "\033[1m"
C_DIM = "\033[2m"
C_CYAN = "\033[96m"
C_GREEN = "\033[92m"
C_YELLOW = "\033[93m"
C_RED = "\033[91m"
C_MAGENTA = "\033[95m"


class BroadcastEventType(str, Enum):
    METADATA = "METADATA"
    MOVE = "MOVE"
    TERMINATION = "TERMINATION"
    AUDIO_INTERRUPT = "AUDIO_INTERRUPT"
    PONDERING = "PONDERING"
    ERROR = "ERROR"


@dataclass
class InitialGameStatus:
    is_ended: bool
    metadata: GameMetadata
    current_ply: int
    current_fen: str
    winner: Optional[str]
    result_code: str
    termination_reason: str
    initial_moves: list[ParsedMoveEvent] = field(default_factory=list)


class BroadcastFrame(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    event_type: BroadcastEventType
    game_id: str
    round_id: Optional[str] = None
    ply: Optional[int] = None
    fen: Optional[str] = None
    turn: Optional[str] = None
    metadata: Optional[Any] = None
    move: Optional[Any] = None
    evaluation: Optional[MoveEvaluation] = None
    commentary: Optional[CommentaryExchange] = None
    visual_cues: Optional[VisualCue] = None
    termination_reason: Optional[str] = None
    error: Optional[str] = None
    timestamp: float = Field(default_factory=time.time)


COLOR_MAP = {
    "green": "\033[92m",
    "red": "\033[91m",
    "yellow": "\033[93m",
    "blue": "\033[94m",
}


def matches_broadcast_game(game: chess.pgn.Game, target: str) -> bool:
    target_clean = target.strip().rstrip("/").split("/")[-1].lower()

    if target_clean == extract_game_id_from_game(game).lower():
        return True

    game_url = game.headers.get("GameURL", "").lower()
    if target_clean in game_url:
        return True

    site = game.headers.get("Site", "").lower()
    if target_clean in site:
        return True

    board = game.headers.get("Board", "").lower()
    if target_clean == board or target_clean == f"board-{board}":
        return True

    round_val = game.headers.get("Round", "").lower()
    if target_clean == round_val or round_val.endswith(f".{target_clean}"):
        return True

    white = game.headers.get("White", "").lower()
    black = game.headers.get("Black", "").lower()
    w_team = game.headers.get("WhiteTeam", "").lower()
    b_team = game.headers.get("BlackTeam", "").lower()

    return (
        target_clean in white
        or target_clean in black
        or target_clean in w_team
        or target_clean in b_team
    )


def format_visual_cues(eval_data: MoveEvaluation, visual_cues=None, fen: Optional[str] = None) -> list[str]:
    """
    Renders engine arrows and highlights into clean, non-redundant CLI tags:
      • Highlights:    [Square d5]
      • Better Move:   [d7 ➔ d6 (d6)] (Only on blunders/mistakes/inaccuracies)
      • Refutation:    [c3 ➔ a4 (Na4)] (On blunders)
      • Expected Next: [e4 ➔ d5 (exd5)] [e4 ➔ e5 (e5)]
    """
    lines = []
    classification = getattr(eval_data, "classification", None)
    is_suboptimal = classification in (
        MoveClassification.BLUNDER,
        MoveClassification.MISTAKE,
        MoveClassification.INACCURACY,
    )

    # 1. Square Highlights
    if visual_cues:
        highlights = getattr(visual_cues, "highlights", None) or (
            visual_cues.get("highlights") if isinstance(visual_cues, dict) else None
        )
        if highlights:
            sq_tags = [f"\033[93m[{sq}]{C_RESET}" for sq in highlights]
            lines.append(f" 🎯 Key Squares   : {' '.join(sq_tags)}")

    # 2. Better Move Arrow (Gated strictly to suboptimal moves)
    shp = getattr(eval_data, "should_have_played", None)
    if is_suboptimal and shp and not getattr(eval_data, "is_book", False):
        uci = getattr(shp, "primary_move_uci", None)
        san = getattr(shp, "primary_move_san", "")
        if uci and len(uci) >= 4:
            src, dst = uci[:2], uci[2:4]
            lines.append(f" 🎯 Engine Arrow  : {COLOR_MAP['green']}[{src} ➔ {dst} ({san})]{C_RESET}")

    # 3. Refutation / Threat Arrow (using punishment sequence)
    dossier = getattr(eval_data, "blunder_dossier", None)
    if dossier:
        san_moves = getattr(dossier, "punishment_moves_san", None)
        if san_moves and len(san_moves) > 0:
            first_san = san_moves[0]
            arrow_tag = f"[{first_san}]"
            if fen:
                try:
                    board = chess.Board(fen)
                    move = board.parse_san(first_san)
                    uci = move.uci()
                    arrow_tag = f"[{uci[:2]} ➔ {uci[2:4]} ({first_san})]"
                except Exception:
                    arrow_tag = f"[{first_san}]"
            lines.append(f" 🚨 Threat Arrow  : {COLOR_MAP['red']}{arrow_tag}{C_RESET}")

    # 4. Prospective Candidate Replies for Opponent (Next to move)
    candidates = getattr(eval_data, "candidate_responses", None)
    if candidates and not dossier:
        candidate_tags = []
        for line in candidates[:2]:
            uci = getattr(line, "primary_move_uci", None)
            san = getattr(line, "primary_move_san", "")
            if uci and len(uci) >= 4:
                src, dst = uci[:2], uci[2:4]
                candidate_tags.append(f"\033[96m[{src} ➔ {dst} ({san})]{C_RESET}")
        if candidate_tags:
            lines.append(f" 💡 Expected Next : {' '.join(candidate_tags)}")

    return lines


def format_score(score_cp: Optional[int], mate_in: Optional[int]) -> str:
    if mate_in is not None:
        return f"M{mate_in:+d}"
    if score_cp is not None:
        return f"{score_cp / 100:+.2f}"
    return " 0.00"


def format_engine_suggestions(eval_data: MoveEvaluation) -> list[str]:
    lines = []
    classification = getattr(eval_data, "classification", None)
    is_suboptimal = classification in (
        MoveClassification.BLUNDER,
        MoveClassification.MISTAKE,
        MoveClassification.INACCURACY,
    )

    # 1. Better Alternative Missed (for blunders, mistakes, and inaccuracies ONLY)
    shp = getattr(eval_data, "should_have_played", None)
    if is_suboptimal and shp and not getattr(eval_data, "is_book", False):
        alt_san = getattr(shp, "primary_move_san", "")
        alt_score = format_score(getattr(shp, "score_cp", None), getattr(shp, "mate_in", None))
        continuation = " ".join(getattr(shp, "san_moves", [])[1:5])
        cont_str = f" ➔ {continuation}" if continuation else ""
        lines.append(
            f" 🎯 {C_BOLD}Better Alternative{C_RESET} : {C_GREEN}{alt_san}{C_RESET} ({alt_score}){C_DIM}{cont_str}{C_RESET}"
        )

    # 2. Tactical Refutation (if a blunder dossier is present)
    dossier = getattr(eval_data, "blunder_dossier", None)
    if dossier and getattr(dossier, "punishment_moves_san", None):
        punishment_line = " ".join(dossier.punishment_moves_san[:4])
        lines.append(f" 🚨 {C_BOLD}Refutation Line   {C_RESET} : {C_RED}{punishment_line}{C_RESET}")

    # 3. Top Candidate Responses for Opponent
    candidates = getattr(eval_data, "candidate_responses", None) or []
    if candidates:
        cand_lines = []
        for idx, cand in enumerate(candidates[:3], start=1):
            cand_san = getattr(cand, "primary_move_san", "")
            cand_score = format_score(getattr(cand, "score_cp", None), getattr(cand, "mate_in", None))
            deep_line = " ".join(getattr(cand, "san_moves", [])[1:4])
            deep_str = f" {C_DIM}({deep_line}){C_RESET}" if deep_line else ""
            cand_lines.append(f"      {idx}. {C_CYAN}{cand_san:<6}{C_RESET} [{cand_score:>6}]{deep_str}")

        if cand_lines:
            lines.append(f" 💡 {C_BOLD}Top Continuations {C_RESET} :")
            lines.extend(cand_lines)

    return lines

def format_clock(seconds: Optional[float]) -> str:
    """Formats seconds into mm:ss or h:mm:ss display string."""
    if seconds is None:
        return "--:--"
    total_seconds = int(seconds)
    hours, remainder = divmod(total_seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours > 0:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"

async def resolve_session_targets_async(arg1: str, arg2: Optional[str] = None) -> Tuple[str, Optional[str]]:
    clean_1 = arg1.strip()
    clean_2 = arg2.strip() if arg2 else None

    for item in (clean_1, clean_2):
        if item and "lichess.org/broadcast" in item:
            parts = [p for p in item.split("/") if p and p not in ("https:", "http:", "lichess.org", "broadcast")]
            ids = [p for p in parts if re.match(r"^[a-zA-Z0-9]{8}$", p)]
            if len(ids) >= 2:
                return ids[1], ids[0]
            elif len(ids) == 1 and clean_2 and item != clean_2:
                return clean_2.split("/")[-1][:8], ids[0]

    if clean_1 and clean_2:
        if clean_2.isdigit() or len(clean_2) != 8:
            return clean_2, clean_1[:8]

        async with aiohttp.ClientSession() as session:
            try:
                async with session.head(f"https://lichess.org/api/broadcast/round/{clean_1[:8]}.pgn") as resp:
                    if resp.status == 200:
                        return clean_2[:8], clean_1[:8]
            except Exception:
                pass

        return clean_2[:8], clean_1[:8]

    match = re.search(r"([a-zA-Z0-9]{8})", clean_1)
    return (match.group(1) if match else clean_1.split("/")[-1][:8]), None


class BroadcastSession:
    def __init__(
        self,
        game_id: str,
        round_id: Optional[str] = None,
        replay_all: bool = False,
        enable_tts: bool = True,
        engine: Optional[StockfishEngine] = None,
        book: Optional[OpeningBook] = None,
        agent: Optional[CommentaryAgent] = None,
        tts_service: Optional[TTSService] = None,
    ):
        self.game_id = game_id
        self.round_id = round_id
        self.replay_all = replay_all
        self.enable_tts = enable_tts

        self._external_engine = engine is not None
        self.engine = engine or StockfishEngine(
            binary_path=settings.stockfish_path,
            multipv=settings.stockfish_multipv,
            depth=settings.stockfish_depth,
            movetime_ms=settings.stockfish_movetime_ms,
        )

        self._external_book = book is not None
        self.book = book or OpeningBook(
            book_path=settings.opening_book_path,
            min_weight=settings.opening_book_min_weight,
        )

        self.opening_tracker = GameOpeningTracker(book=self.book)
        self.analyzer = MoveAnalyzer(
            engine=self.engine,
            opening_tracker=self.opening_tracker,
            shallow_depth=4,
            shallow_movetime_ms=40,
        )

        self.director = BroadcastDirector(history_limit=6)
        self.agent = agent or CommentaryAgent()
        self.tts_service = tts_service or (TTSService() if self.enable_tts else None)

        self.paced_streamer: Optional[PacedMoveStreamer] = None
        self.is_running: bool = False
        self._stop_event = asyncio.Event()
        self._last_move_pondered: bool = False

    async def start(self) -> None:
        self.is_running = True
        self._stop_event.clear()
        await self.engine.start()

    async def stop(self) -> None:
        self.is_running = False
        self._stop_event.set()

        if self.paced_streamer:
            self.paced_streamer.stop()

        if self.tts_service:
            self.tts_service.trigger_interrupt()

        if not self._external_engine and self.engine:
            try:
                await self.engine.close()
            except Exception:
                pass

        if not self._external_book and self.book:
            try:
                self.book.close()
            except Exception:
                pass

    def _extract_winner(self, termination_reason: str) -> Optional[str]:
        reason_lower = termination_reason.lower()
        if "white wins" in reason_lower or "1-0" in reason_lower:
            return "white"
        elif "black wins" in reason_lower or "0-1" in reason_lower:
            return "black"
        elif "draw" in reason_lower or "1/2" in reason_lower or "stalemate" in reason_lower:
            return None
        return None

    async def _inspect_initial_game(self) -> Optional[InitialGameStatus]:
        user_agent = getattr(settings, "lichess_user_agent", "LiveChessCommentary/1.0")

        if self.round_id:
            url = f"https://lichess.org/api/broadcast/round/{self.round_id}.pgn"
            headers = {"User-Agent": user_agent, "Accept": "text/plain"}
            try:
                timeout = aiohttp.ClientTimeout(total=8.0)
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    async with session.get(url, headers=headers) as resp:
                        if resp.status != 200:
                            return None
                        content = await resp.text()

                for block in split_pgn_blocks(content):
                    game = chess.pgn.read_game(io.StringIO(block))
                    if game and matches_broadcast_game(game, self.game_id):
                        headers_dict = game.headers
                        result = headers_dict.get("Result", "*")
                        term_header = headers_dict.get("Termination")

                        board = game.board()
                        ply = 0
                        curr = game
                        initial_moves: list[ParsedMoveEvent] = []
                        white_name = headers_dict.get("White", "White")
                        black_name = headers_dict.get("Black", "Black")
                        prev_w_clk: Optional[float] = None
                        prev_b_clk: Optional[float] = None

                        while curr.variations:
                            curr = curr.variation(0)
                            move = curr.move
                            ply += 1

                            turn_str = "white" if board.turn == chess.WHITE else "black"
                            acting = white_name if turn_str == "white" else black_name
                            san = board.san(move)
                            uci = move.uci()
                            board.push(move)

                            clk = parse_clock_seconds(curr.comment)
                            w_clk = clk if turn_str == "white" else prev_w_clk
                            b_clk = clk if turn_str == "black" else prev_b_clk

                            move_time = 0.0
                            if turn_str == "white" and prev_w_clk is not None and clk is not None:
                                move_time = max(0.0, prev_w_clk - clk)
                            elif turn_str == "black" and prev_b_clk is not None and clk is not None:
                                move_time = max(0.0, prev_b_clk - clk)

                            if turn_str == "white" and clk is not None:
                                prev_w_clk = clk
                            elif turn_str == "black" and clk is not None:
                                prev_b_clk = clk

                            initial_moves.append(
                                ParsedMoveEvent(
                                    ply=ply,
                                    turn=turn_str,
                                    acting_player=acting,
                                    san=san,
                                    uci=uci,
                                    fen=board.fen(),
                                    white_clock_seconds=w_clk,
                                    black_clock_seconds=b_clk,
                                    move_time_spent_seconds=move_time,
                                    is_check=board.is_check(),
                                    is_checkmate=board.is_checkmate(),
                                    is_stalemate=board.is_stalemate(),
                                    is_draw=board.is_game_over() and not board.is_checkmate(),
                                    is_time_trouble=False,
                                )
                            )

                        w_elo = int(headers_dict["WhiteElo"]) if headers_dict.get("WhiteElo", "").isdigit() else None
                        b_elo = int(headers_dict["BlackElo"]) if headers_dict.get("BlackElo", "").isdigit() else None

                        metadata = GameMetadata(
                            game_id=extract_game_id_from_game(game),
                            speed="classical",
                            variant="standard",
                            rated=True,
                            white_player=PlayerInfo(
                                username=headers_dict.get("White", "White"),
                                title=headers_dict.get("WhiteTitle"),
                                rating=w_elo,
                            ),
                            black_player=PlayerInfo(
                                username=headers_dict.get("Black", "Black"),
                                title=headers_dict.get("BlackTitle"),
                                rating=b_elo,
                            ),
                            event_name=headers_dict.get("Event", "Lichess Broadcast"),
                        )

                        is_ended = result in ("1-0", "0-1", "1/2-1/2") or board.is_game_over()
                        winner = "white" if result == "1-0" else ("black" if result == "0-1" else None)
                        if is_ended and not winner and board.is_checkmate():
                            winner = "white" if board.turn == chess.BLACK else "black"

                        win_name = metadata.white_player.username if winner == "white" else metadata.black_player.username
                        extra = f" ({term_header})" if term_header else ""

                        if board.is_checkmate():
                            reason = f"Checkmate - {win_name} wins ({result})"
                        elif board.is_stalemate():
                            reason = f"Draw by Stalemate ({result})"
                        elif winner:
                            reason = f"{result} - {win_name} wins{extra}"
                        elif is_ended:
                            reason = f"{result} - Draw{extra}"
                        else:
                            reason = "Game in progress"

                        return InitialGameStatus(
                            is_ended=is_ended,
                            metadata=metadata,
                            current_ply=ply,
                            current_fen=board.fen(),
                            winner=winner,
                            result_code=result,
                            termination_reason=reason,
                            initial_moves=initial_moves,
                        )
            except Exception as exc:
                logger.warning(f"Broadcast initial inspection error: {exc}", exc_info=True)
                return None
        else:
            url = f"https://lichess.org/api/game/{self.game_id}?moves=true&tags=true"
            headers = {"User-Agent": user_agent, "Accept": "application/json"}
            try:
                timeout = aiohttp.ClientTimeout(total=5.0)
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    async with session.get(url, headers=headers) as resp:
                        if resp.status != 200:
                            return None
                        data = await resp.json()

                tracker = ChessStateTracker()
                metadata = tracker._build_metadata(data)

                moves = data.get("moves", "").strip().split()
                ply = len(moves)

                board = chess.Board()
                initial_moves: list[ParsedMoveEvent] = []
                white_name = metadata.white_player.username
                black_name = metadata.black_player.username
                for idx, m_str in enumerate(moves):
                    try:
                        turn_str = "white" if board.turn == chess.WHITE else "black"
                        acting = white_name if turn_str == "white" else black_name
                        move = board.parse_san(m_str)
                        uci = move.uci()
                        board.push(move)
                        initial_moves.append(
                            ParsedMoveEvent(
                                ply=idx + 1,
                                turn=turn_str,
                                acting_player=acting,
                                san=m_str,
                                uci=uci,
                                fen=board.fen(),
                                white_clock_seconds=None,
                                black_clock_seconds=None,
                                move_time_spent_seconds=0.0,
                                is_check=board.is_check(),
                                is_checkmate=board.is_checkmate(),
                                is_stalemate=board.is_stalemate(),
                                is_draw=board.is_game_over() and not board.is_checkmate(),
                                is_time_trouble=False,
                            )
                        )
                    except Exception:
                        break

                status = str(data.get("status", "started"))
                winner = data.get("winner")
                is_ended = (
                    status.lower() in ChessStateTracker.TERMINAL_STATUSES
                    or status.lower() not in ("created", "started")
                )

                reason = ChessStateTracker._format_status_termination(status, winner)
                result_code = "1-0" if winner == "white" else ("0-1" if winner == "black" else ("1/2-1/2" if is_ended else "*"))

                return InitialGameStatus(
                    is_ended=is_ended,
                    metadata=metadata,
                    current_ply=ply,
                    current_fen=board.fen(),
                    winner=winner,
                    result_code=result_code,
                    termination_reason=reason,
                    initial_moves=initial_moves,
                )
            except Exception as exc:
                logger.debug(f"Casual game initial inspection error: {exc}")
                return None

    async def _detect_game_end_result(
        self, white_name: str, black_name: str
    ) -> Optional[Tuple[Optional[str], str, str]]:
        board = self.analyzer.board
        if board.is_checkmate():
            winner = "black" if board.turn == chess.WHITE else "white"
            win_name = black_name if winner == "black" else white_name
            code = "0-1" if winner == "black" else "1-0"
            return winner, code, f"Checkmate - {win_name} wins"
        if board.is_stalemate():
            return None, "1/2-1/2", "Draw by Stalemate"
        if board.is_insufficient_material():
            return None, "1/2-1/2", "Draw by Insufficient Material"
        if board.is_fivefold_repetition() or board.can_claim_threefold_repetition():
            return None, "1/2-1/2", "Draw by Repetition"
        if board.is_seventyfive_moves() or board.can_claim_fifty_moves():
            return None, "1/2-1/2", "Draw by 50-move Rule"

        init_status = await self._inspect_initial_game()
        if init_status and init_status.is_ended:
            return init_status.winner, init_status.result_code, init_status.termination_reason

        return None

    async def _generate_closing_commentary(
        self,
        winner: Optional[str],
        result_str: str,
        termination_reason: str,
        white_player: str,
        black_player: str,
    ) -> CommentaryExchange:
        if winner == "white":
            fallback_turns = [
                DialogueTurn(
                    speaker=CommentatorRole.HOST,
                    text=f"And that seals it! {white_player} claims victory! {termination_reason}.",
                    emotion=CommentaryEmotion.EXCITED,
                    priority=CommentaryPriority.HIGH_DRAMA.value,
                ),
                DialogueTurn(
                    speaker=CommentatorRole.ANALYST,
                    text=f"A commanding performance by White. {white_player} held the pressure, calculated cleanly, and earned the full point.",
                    emotion=CommentaryEmotion.ANALYTICAL,
                    priority=CommentaryPriority.HIGH_DRAMA.value,
                ),
            ]
        elif winner == "black":
            fallback_turns = [
                DialogueTurn(
                    speaker=CommentatorRole.HOST,
                    text=f"It is all over! {black_player} takes the win with Black! {termination_reason}.",
                    emotion=CommentaryEmotion.EXCITED,
                    priority=CommentaryPriority.HIGH_DRAMA.value,
                ),
                DialogueTurn(
                    speaker=CommentatorRole.ANALYST,
                    text=f"Tremendous defensive and tactical control from {black_player}. Converting against tough opposition is never easy, but they closed it out.",
                    emotion=CommentaryEmotion.ANALYTICAL,
                    priority=CommentaryPriority.HIGH_DRAMA.value,
                ),
            ]
        else:
            fallback_turns = [
                DialogueTurn(
                    speaker=CommentatorRole.HOST,
                    text=f"And there it is! Hands are shaken and the match ends in a draw. {termination_reason}.",
                    emotion=CommentaryEmotion.NEUTRAL,
                    priority=CommentaryPriority.NORMAL.value,
                ),
                DialogueTurn(
                    speaker=CommentatorRole.ANALYST,
                    text=f"A thoroughly balanced contest. Both {white_player} and {black_player} probed for advantages, but the position held solid to the finish.",
                    emotion=CommentaryEmotion.ANALYTICAL,
                    priority=CommentaryPriority.NORMAL.value,
                ),
            ]

        parsed_turns = fallback_turns

        if self.agent and getattr(self.agent, "_client", None):
            closing_prompt = (
                f"### MATCH CONCLUSION:\n"
                f"- White: {white_player}\n"
                f"- Black: {black_player}\n"
                f"- Winner: {winner.upper() if winner else 'DRAW'}\n"
                f"- Result: {result_str}\n"
                f"- Termination Details: {termination_reason}\n\n"
                f"Generate a final broadcast sign-off between HOST (James) and ANALYST (Peter):\n"
                f"- Host: Announce the match conclusion with excitement and authority.\n"
                f"- Analyst: Give an insightful closing takeaway on the outcome.\n"
                f"Return ONLY valid JSON with dialogue turns."
            )
            try:
                gen_config = types.GenerateContentConfig(
                    system_instruction=SYSTEM_PROMPT,
                    response_mime_type="application/json",
                    temperature=0.5,
                    max_output_tokens=300,
                )
                response = await self.agent._client.aio.models.generate_content(
                    model=self.agent.model,
                    contents=closing_prompt,
                    config=gen_config,
                )
                raw_text = response.text or "{}"
                llm_turns = self.agent._parse_llm_json(raw_text, priority=CommentaryPriority.HIGH_DRAMA.value)
                if llm_turns:
                    parsed_turns = llm_turns
            except Exception as exc:
                logger.warning(f"LLM closing commentary generation failed ({exc}); using template.")

        for turn in parsed_turns:
            word_count = len(turn.text.split())
            turn.estimated_duration_seconds = max(1.0, round(word_count / 2.5, 2))

        exchange = CommentaryExchange(
            ply=self.analyzer.board.ply(),
            move_san="",
            turn_color="white" if self.analyzer.board.turn == chess.WHITE else "black",
            dynamic=SpeakingDynamic.BANTER,
            priority=CommentaryPriority.HIGH_DRAMA.value,
            turns=parsed_turns,
            is_interrupt=False,
        )

        if self.tts_service and self.enable_tts:
            exchange = await self.tts_service.synthesize_exchange(
                exchange=exchange,
                game_id=self.game_id,
            )

        return exchange

    async def stream_broadcast(self) -> AsyncGenerator[BroadcastFrame, None]:
        if not self.is_running:
            await self.start()

        target_start_ply = 0
        if not self.replay_all:
            init_check = await self._inspect_initial_game()

            if init_check and init_check.is_ended:
                self.analyzer.board = chess.Board(init_check.current_fen)

                yield BroadcastFrame(
                    event_type=BroadcastEventType.METADATA,
                    game_id=self.game_id,
                    round_id=self.round_id,
                    fen=chess.STARTING_FEN,
                    metadata=init_check.metadata,
                )

                for mv in getattr(init_check, "initial_moves", []):
                    yield BroadcastFrame(
                        event_type=BroadcastEventType.MOVE,
                        game_id=self.game_id,
                        round_id=self.round_id,
                        ply=mv.ply,
                        fen=mv.fen,
                        turn=mv.turn,
                        move=mv,
                    )

                closing_exchange = await self._generate_closing_commentary(
                    winner=init_check.winner,
                    result_str=init_check.result_code,
                    termination_reason=init_check.termination_reason,
                    white_player=init_check.metadata.white_player.username,
                    black_player=init_check.metadata.black_player.username,
                )

                yield BroadcastFrame(
                    event_type=BroadcastEventType.TERMINATION,
                    game_id=self.game_id,
                    round_id=self.round_id,
                    ply=init_check.current_ply,
                    fen=init_check.current_fen,
                    termination_reason=init_check.termination_reason,
                    commentary=closing_exchange,
                )
                return

            if init_check and init_check.current_ply > 0:
                target_start_ply = init_check.current_ply
                print(f"{C_DIM}>>> Detected live match at Ply {target_start_ply}. Catching up...{C_RESET}")

        if self.round_id:
            raw_streamer = LichessBroadcastStreamer(
                round_id=self.round_id,
                game_id=self.game_id,
                time_trouble_threshold_seconds=settings.time_trouble_threshold_seconds,
            )
        else:
            raw_streamer = LichessGameStreamer(
                game_id=self.game_id,
                time_trouble_threshold_seconds=settings.time_trouble_threshold_seconds,
                read_timeout_seconds=None,
            )

        print(f"{C_DIM}>>> Connecting to stream...{C_RESET}")

        is_broadcast_game = bool(self.round_id)
        max_delay = 0.0 if is_broadcast_game else settings.max_paced_move_delay_seconds

        white_name = "White"
        black_name = "Black"
        game_speed = "classical" if self.round_id else "blitz"
        game_concluded = False
        self._last_move_pondered = False

        self.paced_streamer = PacedMoveStreamer(
            streamer=raw_streamer,
            fast_forward_initial_history=not self.replay_all,
            max_paced_move_delay_seconds=max_delay,
            target_live_ply=target_start_ply,
            game_format=game_speed,
            is_broadcast=is_broadcast_game,
        )

        try:
            async for event in self.paced_streamer.stream_paced_events():
                if self._stop_event.is_set():
                    break

                is_meta = type(event).__name__ == "GameMetadata"
                is_move = type(event).__name__ == "ParsedMoveEvent"
                is_termination = type(event).__name__ == "GameTerminationEvent"
                is_pondering = type(event).__name__ == "PonderingEvent" or isinstance(event, PonderingEvent)

                if is_meta:
                    white_name = event.white_player.username
                    black_name = event.black_player.username
                    game_speed = event.speed or game_speed

                    self.analyzer.reset()
                    self.director.reset(game_format=game_speed)
                    if not is_broadcast_game and hasattr(self.paced_streamer, "set_game_format"):
                        self.paced_streamer.set_game_format(game_speed)

                    yield BroadcastFrame(
                        event_type=BroadcastEventType.METADATA,
                        game_id=self.game_id,
                        round_id=self.round_id,
                        fen=chess.STARTING_FEN,
                        metadata=event,
                    )
                    continue

                elif is_pondering:
                    analysis = self.analyzer.previous_analysis
                    if not analysis:
                        try:
                            analysis = await self.analyzer.engine.analyze_position(event.fen or self.analyzer.board.fen())
                            self.analyzer.previous_analysis = analysis
                        except Exception as exc:
                            logger.warning(f"Engine pondering analysis failed: {exc}")
                            analysis = None

                    candidate_suggestions = []
                    if analysis and getattr(analysis, "lines", None):
                        for line in analysis.lines[:2]:
                            if getattr(line, "primary_move_san", None):
                                candidate_suggestions.append(line.primary_move_san)

                    context = self.director.assemble_pondering_context(
                        ply=event.ply,
                        turn=event.turn,
                        acting_player=event.acting_player,
                        fen=event.fen or self.analyzer.board.fen(),
                        elapsed_think_seconds=event.elapsed_think_seconds,
                        candidate_suggestions=candidate_suggestions,
                        white_player=white_name,
                        black_player=black_name,
                        white_clock_seconds=event.white_clock_seconds,
                        black_clock_seconds=event.black_clock_seconds,
                    )

                    exchange = await self.agent.generate_commentary(context)

                    if self.tts_service and self.enable_tts:
                        exchange = await self.tts_service.synthesize_exchange(
                            exchange=exchange,
                            game_id=self.game_id,
                        )

                    self.director.record_exchange(exchange)
                    self._last_move_pondered = True

                    yield BroadcastFrame(
                        event_type=BroadcastEventType.PONDERING,
                        game_id=self.game_id,
                        round_id=self.round_id,
                        ply=event.ply,
                        fen=event.fen or self.analyzer.board.fen(),
                        turn=event.turn,
                        commentary=exchange,
                    )
                    continue

                elif is_termination:
                    game_concluded = True
                    reason = event.termination_reason or f"Game concluded ({event.status})"
                    winner = event.winner or self._extract_winner(reason)
                    closing_exchange = await self._generate_closing_commentary(
                        winner=winner,
                        result_str=event.status,
                        termination_reason=reason,
                        white_player=white_name,
                        black_player=black_name,
                    )
                    yield BroadcastFrame(
                        event_type=BroadcastEventType.TERMINATION,
                        game_id=self.game_id,
                        round_id=self.round_id,
                        ply=event.turns or self.analyzer.board.ply(),
                        fen=event.fen or self.analyzer.board.fen(),
                        termination_reason=reason,
                        commentary=closing_exchange,
                    )
                    break

                elif is_move:
                    if event.turn == "white" and event.acting_player:
                        white_name = event.acting_player
                    elif event.turn == "black" and event.acting_player:
                        black_name = event.acting_player

                    if target_start_ply > 1 and event.ply < (target_start_ply - 1):
                        current_move = chess.Move.from_uci(event.uci)
                        self.analyzer.opening_tracker.process_move(
                            board_before=self.analyzer.board.copy(),
                            move=current_move,
                            move_san=event.san,
                            ply=event.ply,
                        )
                        if current_move in self.analyzer.board.legal_moves:
                            self.analyzer.board.push(current_move)
                        else:
                            self.analyzer.board.set_fen(event.fen)

                        print(f"\r{C_DIM}>>> [SYNC] Fast-syncing: {event.san:<6} (Ply {event.ply}/{target_start_ply})...{C_RESET}", end="", flush=True)

                        yield BroadcastFrame(
                            event_type=BroadcastEventType.MOVE,
                            game_id=self.game_id,
                            round_id=self.round_id,
                            ply=event.ply,
                            fen=event.fen,
                            turn=event.turn,
                            move=event,
                        )
                        continue

                    elif target_start_ply > 1 and event.ply == (target_start_ply - 1):
                        current_move = chess.Move.from_uci(event.uci)
                        self.analyzer.opening_tracker.process_move(
                            board_before=self.analyzer.board.copy(),
                            move=current_move,
                            move_san=event.san,
                            ply=event.ply,
                        )
                        if current_move in self.analyzer.board.legal_moves:
                            self.analyzer.board.push(current_move)
                        else:
                            self.analyzer.board.set_fen(event.fen)

                        print(f"\r{C_DIM}>>> [SYNC] Priming engine baseline on Ply {event.ply}...{C_RESET}", end="", flush=True)
                        self.analyzer.previous_analysis = await self.analyzer.engine.analyze_position(event.fen)
                        self.analyzer.previous_move = current_move

                        yield BroadcastFrame(
                            event_type=BroadcastEventType.MOVE,
                            game_id=self.game_id,
                            round_id=self.round_id,
                            ply=event.ply,
                            fen=event.fen,
                            turn=event.turn,
                            move=event,
                        )
                        continue

                    print(f"\r" + " " * 75 + "\r", end="", flush=True)

                    evaluation = await self.analyzer.evaluate_move(event)
                    pending_audio = self.tts_service.pending_audio_seconds if self.tts_service else 0.0

                    context = self.director.assemble_context(
                        eval_data=evaluation,
                        event=event,
                        white_player=white_name,
                        black_player=black_name,
                        pending_audio_seconds=pending_audio,
                        was_pondered=self._last_move_pondered,
                    )
                    self._last_move_pondered = False

                    exchange = await self.agent.generate_commentary(context)

                    if self.tts_service and self.enable_tts:
                        if exchange.is_interrupt:
                            yield BroadcastFrame(
                                event_type=BroadcastEventType.AUDIO_INTERRUPT,
                                game_id=self.game_id,
                                round_id=self.round_id,
                                ply=event.ply,
                            )
                        exchange = await self.tts_service.synthesize_exchange(
                            exchange=exchange,
                            game_id=self.game_id,
                        )

                    self.director.record_exchange(exchange)

                    yield BroadcastFrame(
                        event_type=BroadcastEventType.MOVE,
                        game_id=self.game_id,
                        round_id=self.round_id,
                        ply=event.ply,
                        fen=event.fen,
                        turn=event.turn,
                        move=event,
                        evaluation=evaluation,
                        commentary=exchange,
                        visual_cues=evaluation.visual_cues,
                    )

                    if event.termination_reason or event.is_checkmate or event.is_stalemate:
                        game_concluded = True
                        reason = event.termination_reason or (
                            f"Checkmate - {'Black' if event.turn == 'white' else 'White'} wins"
                            if event.is_checkmate
                            else "Draw by Stalemate"
                        )
                        winner = self._extract_winner(reason)
                        closing_exchange = await self._generate_closing_commentary(
                            winner=winner,
                            result_str=reason,
                            termination_reason=reason,
                            white_player=white_name,
                            black_player=black_name,
                        )
                        yield BroadcastFrame(
                            event_type=BroadcastEventType.TERMINATION,
                            game_id=self.game_id,
                            round_id=self.round_id,
                            ply=event.ply,
                            fen=event.fen,
                            termination_reason=reason,
                            commentary=closing_exchange,
                        )
                        break

            if not game_concluded and not self._stop_event.is_set():
                result_info = await self._detect_game_end_result(white_name, black_name)
                if result_info:
                    winner, code, reason = result_info
                    closing_exchange = await self._generate_closing_commentary(
                        winner=winner,
                        result_str=code,
                        termination_reason=reason,
                        white_player=white_name,
                        black_player=black_name,
                    )
                    yield BroadcastFrame(
                        event_type=BroadcastEventType.TERMINATION,
                        game_id=self.game_id,
                        round_id=self.round_id,
                        ply=self.analyzer.board.ply(),
                        fen=self.analyzer.board.fen(),
                        termination_reason=reason,
                        commentary=closing_exchange,
                    )

        except asyncio.CancelledError:
            logger.info(f"Broadcast session {self.game_id} cancelled.")
            raise
        except Exception as exc:
            logger.error(f"Stream error: {exc}", exc_info=True)
            yield BroadcastFrame(...)
        finally:
            await self.stop()


async def main():
    parser = argparse.ArgumentParser(description="Live Broadcast Session Runner.")
    parser.add_argument("arg1", type=str, help="Round ID, Game ID, or broadcast URL")
    parser.add_argument("arg2", nargs="?", default=None, help="Matching Game ID or Round ID")
    parser.add_argument("--replay-all", action="store_true", help="Paces every move from move 1")
    parser.add_argument("--no-tts", action="store_true", help="Disable ElevenLabs voice generation")
    args = parser.parse_args()

    resolved_game, resolved_round = await resolve_session_targets_async(args.arg1, args.arg2)

    session = BroadcastSession(
        game_id=resolved_game,
        round_id=resolved_round,
        replay_all=args.replay_all,
        enable_tts=not args.no_tts,
    )

    print(f"\n{C_BOLD}Connecting BroadcastSession:{C_RESET}")
    print(f" • Target Game : {C_CYAN}{session.game_id}{C_RESET}")
    print(f" • Round ID    : {C_MAGENTA}{session.round_id or 'Casual'}{C_RESET}")
    print("─" * 70)

    try:
        async for frame in session.stream_broadcast():
            if frame.event_type == BroadcastEventType.METADATA:
                meta = frame.metadata
                print(f"\n{C_GREEN}✓ [MATCH CONNECTED]{C_RESET} {meta.white_player.username} vs {meta.black_player.username}")
                print(f"  Event: {meta.event_name} ({meta.speed.upper()})")
                print("═" * 84)

            elif frame.event_type == BroadcastEventType.MOVE:
                move = frame.move
                eval_data = frame.evaluation
                prefix = f"{(eval_data.ply + 1) // 2}." if eval_data.turn == "white" else f"{(eval_data.ply + 1) // 2}..."
                eval_str = f"{eval_data.eval_cp_after / 100:+.2f}" if eval_data.eval_cp_after is not None else "0.00"

                w_clk = format_clock(move.white_clock_seconds)
                b_clk = format_clock(move.black_clock_seconds)
                spent_str = f" | Spent: {move.move_time_spent_seconds:.1f}s" if move.move_time_spent_seconds else ""
                clock_str = f"Clocks: ⚪ {w_clk}  ⚫ {b_clk}{spent_str}"

                print(
                    f"\n{C_BOLD}{prefix:<6} {move.san:<7}{C_RESET} | "
                    f"Quality: {eval_data.classification.value:<10} | "
                    f"Eval: {eval_str:>6} | "
                    f"{C_DIM}{clock_str}{C_RESET}"
                )

                cue_lines = format_visual_cues(eval_data, frame.visual_cues, fen=frame.fen)
                for cue in cue_lines:
                    print(cue)

                suggestion_lines = format_engine_suggestions(eval_data)
                for suggestion in suggestion_lines:
                    print(suggestion)

                if frame.commentary and frame.commentary.turns:
                    for turn in frame.commentary.turns:
                        color = C_CYAN if turn.speaker.value == "HOST" else C_GREEN
                        audio_tag = f" {C_DIM}[Audio: {turn.audio_url}]{C_RESET}" if turn.audio_url else ""
                        print(f"  🎙️ {color}[{turn.speaker.value}]{C_RESET} ({turn.emotion.value}): \"{turn.text}\"{audio_tag}")

                next_to_move = "Black" if eval_data.turn == "white" else "White"
                print(f"\n{C_DIM}⏳ Waiting for {next_to_move}'s move (polling Lichess relay)...{C_RESET}", end="", flush=True)
        
            elif frame.event_type == BroadcastEventType.PONDERING:
                turn_str = "White" if frame.turn == "white" else "Black"
                print(f"\n{C_YELLOW}🤔 [PONDERING]{C_RESET} {turn_str} is in the tank, weighing candidate options...")
                if frame.commentary and frame.commentary.turns:
                    for turn in frame.commentary.turns:
                        color = C_CYAN if turn.speaker.value == "HOST" else C_GREEN
                        audio_tag = f" {C_DIM}[Audio: {turn.audio_url}]{C_RESET}" if turn.audio_url else ""
                        print(f"  🎙️ {color}[{turn.speaker.value}]{C_RESET} ({turn.emotion.value}): \"{turn.text}\"{audio_tag}")

            elif frame.event_type == BroadcastEventType.AUDIO_INTERRUPT:
                print(f"  {C_RED}⚡ [AUDIO INTERRUPT] Clearing audio buffer for urgent blunder/brilliancy!{C_RESET}")

            elif frame.event_type == BroadcastEventType.TERMINATION:
                print(f"\n{C_YELLOW}{C_BOLD}🏆 [GAME OVER]{C_RESET} Result: {C_BOLD}{frame.termination_reason}{C_RESET}")
                if frame.commentary and frame.commentary.turns:
                    for turn in frame.commentary.turns:
                        color = C_CYAN if turn.speaker.value == "HOST" else C_GREEN
                        audio_tag = f" {C_DIM}[Audio: {turn.audio_url}]{C_RESET}" if turn.audio_url else ""
                        print(f"  🎙️ {color}[{turn.speaker.value}]{C_RESET} ({turn.emotion.value}): \"{turn.text}\"{audio_tag}")
                break

            elif frame.event_type == BroadcastEventType.ERROR:
                print(f"\n{C_RED}[SESSION ERROR]{C_RESET} {frame.error}")
                break

    except KeyboardInterrupt:
        print("\nSession stopped.")
    finally:
        await session.stop()


if __name__ == "__main__":
    asyncio.run(main())