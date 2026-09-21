import argparse
import asyncio
import json
import logging
import re
import sys
import time
import urllib.request
from pathlib import Path
from typing import Optional

# Ensure project root and backend directory are in sys.path
CURRENT_DIR = Path(__file__).resolve().parent
sys.path.extend([
    str(CURRENT_DIR),
    str(CURRENT_DIR / "backend"),
])

import chess

from app.config import settings
from app.lichess.game_streamer import LichessGameStreamer
from app.lichess.pacing_buffer import PacedMoveStreamer
from app.lichess.pgn_parser import GameMetadata, ParsedMoveEvent
from app.engine.stockfish_pool import StockfishEngine
from app.engine.opening_book import OpeningBook, GameOpeningTracker
from app.engine.analyzer import MoveAnalyzer
from app.engine.schemas import MoveEvaluation, MoveClassification
from app.commentary.director import BroadcastDirector
from app.commentary.agent import CommentaryAgent
from app.commentary.schemas import (
    CommentaryExchange,
    CommentatorRole,
    SpeakingDynamic,
)

# ANSI Color Codes
C_RESET = "\033[0m"
C_BOLD = "\033[1m"
C_DIM = "\033[2m"
C_CYAN = "\033[96m"      # Host
C_GREEN = "\033[92m"     # GM Analyst
C_YELLOW = "\033[93m"    # Emotions / Clocks
C_RED = "\033[91m"       # Blunders / Alerts
C_MAGENTA = "\033[95m"   # Brilliancies / Openings


def extract_game_id(game_input: str) -> str:
    """Extracts the 8-character Lichess game ID regardless of trailing slashes, colors, or query params."""
    match = re.search(r"([a-zA-Z0-9]{8})", game_input)
    if match:
        return match.group(1)
    return game_input.strip("/").split("/")[-1][:8]


def fetch_current_game_ply(game_id: str) -> int:
    """
    Fetches the live ply count using an explicit JSON header with a PGN text fallback
    so it never silently defaults to ply 0.
    """
    clean_id = extract_game_id(game_id)
    url = f"https://lichess.org/api/game/{clean_id}?moves=true&tags=false&clocks=false&evals=false"
    
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": getattr(settings, "lichess_user_agent", "LiveChessCommentary/1.0"),
            "Accept": "application/json",  # Mandatory: prevents Lichess from returning plaintext PGN
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            content_type = resp.headers.get("Content-Type", "")
            raw_body = resp.read().decode("utf-8")

            if "json" in content_type:
                data = json.loads(raw_body)
                moves_str = data.get("moves", "").strip()
                return len(moves_str.split()) if moves_str else 0
            else:
                # Fallback parser if PGN text is returned despite headers
                clean_pgn = re.sub(r"\[.*?\]", "", raw_body)
                tokens = [
                    t for t in clean_pgn.split()
                    if not re.match(r"^\d+\.+$|^1-0$|^0-1$|^1/2-1/2$|^\*$", t)
                ]
                return len(tokens)
    except Exception as exc:
        print(f"{C_YELLOW}[!] Could not pre-fetch game ply count ({exc}). Starting commentary from move 1.{C_RESET}")
        return 0


def format_clock(seconds: Optional[float]) -> str:
    if seconds is None:
        return "--:--"
    m, s = divmod(int(seconds), 60)
    return f"{m:02d}:{s:02d}"


def format_eval(score_cp: Optional[int], mate_in: Optional[int]) -> str:
    if mate_in is not None:
        return f"M{mate_in:+d}"
    if score_cp is not None:
        return f"{score_cp / 100:+.2f}"
    return " 0.00"


def render_broadcast_screen(
    eval_data: MoveEvaluation,
    event: ParsedMoveEvent,
    exchange: Optional[CommentaryExchange] = None,
    llm_elapsed_ms: float = 0.0,
):
    move_num = (eval_data.ply + 1) // 2
    prefix = f"{move_num}." if eval_data.turn == "white" else f"{move_num}..."
    player = event.acting_player or eval_data.turn.capitalize()
    w_clk = format_clock(event.white_clock_seconds)
    b_clk = format_clock(event.black_clock_seconds)

    print("\n" + "═" * 84)
    think_badge = ""
    t = getattr(event, "move_time_spent_seconds", 0.0)
    if t >= 25.0:
        think_badge = f" {C_YELLOW}🧠 [DEEP THINK]{C_RESET}"
    elif t <= 1.5:
        think_badge = f" {C_DIM}⚡ [INSTANT]{C_RESET}"

    print(
        f" {C_BOLD}{prefix:<6} {eval_data.played_san:<7}{C_RESET} (uci: {eval_data.played_uci}) | "
        f"By: {player:<14} | "
        f"Think: {t:>4.1f}s{think_badge} | "
        f"Clocks: W {w_clk} / B {b_clk}"
    )
    print("─" * 84)

    if eval_data.opening_name or eval_data.eco_code:
        eco_str = f"[{eval_data.eco_code}]" if eval_data.eco_code else ""
        print(f" Opening    : {C_MAGENTA}{eco_str} {eval_data.opening_name or 'Theory'}{C_RESET}")

    if eval_data.left_book_now:
        print(f" {C_RED}⚡ ALERT    : [OUT OF BOOK / NOVELTY] Both players have exited theory!{C_RESET}")

    eval_str = format_eval(eval_data.eval_cp_after, eval_data.mate_in_after)
    win_pct_after = f"{eval_data.win_prob_after * 100:.1f}%"
    win_pct_loss = f"{eval_data.win_prob_loss * 100:.1f}%"
    pawn_loss = f"{abs(eval_data.eval_swing_cp) / 100:.2f}"

    classification_badges = {
        MoveClassification.BOOK: f"{C_MAGENTA}📖 [BOOK]{C_RESET}",
        MoveClassification.BRILLIANT: f"{C_MAGENTA}✨ [BRILLIANT]{C_RESET}",
        MoveClassification.BEST: f"{C_GREEN}🎯 [BEST]{C_RESET}",
        MoveClassification.EXCELLENT: f"{C_GREEN}👍 [EXCELLENT]{C_RESET}",
        MoveClassification.GOOD: f"{C_GREEN}✔️  [GOOD]{C_RESET}",
        MoveClassification.INACCURACY: f"{C_YELLOW}⚠️  [INACCURACY]{C_RESET}",
        MoveClassification.NORMAL: f"{C_DIM}➖ [NORMAL]{C_RESET}",
        MoveClassification.MISTAKE: f"{C_YELLOW}❓ [MISTAKE]{C_RESET}",
        MoveClassification.BLUNDER: f"{C_RED}{C_BOLD}🚨 [BLUNDER]{C_RESET}",
    }
    badge = classification_badges.get(eval_data.classification, f"[{eval_data.classification.value}]")

    if eval_data.is_book:
        print(f" Quality    : {badge:<25} | Polyglot Theory (0.00 loss)")
    else:
        print(f" Quality    : {badge:<25} | Loss: -{pawn_loss} pawns (-{win_pct_loss} win prob)")

    print(f" Position   : Eval: {eval_str:>6} (White) | White Win Prob: {win_pct_after:>6}")

    if eval_data.blunder_dossier:
        dossier = eval_data.blunder_dossier
        trap_flag = f"{C_RED}NATURAL HUMAN TRAP{C_RESET}" if dossier.is_natural_trap else "TACTICAL OVERSIGHT"
        print("─" * 84)
        print(f" 🧠 BLUNDER ANALYSIS ({trap_flag}):")
        print(f"   • Human Intent  : [{dossier.human_motivation.value}] {dossier.motivation_explanation}")
        print(f"   • Blind Spot    : [{dossier.refutation_type.value}] {dossier.refutation_explanation}")
        if dossier.punishment_moves_san:
            print(f"   • Counter-Punch : {' '.join(dossier.punishment_moves_san)}")

    print("─" * 84)
    print(f" 🎙️ {C_BOLD}LIVE BROADCAST COMMENTARY{C_RESET} {C_DIM}(Dynamic: {exchange.dynamic.value if exchange else 'N/A'} | TTFT: {llm_elapsed_ms:.0f}ms){C_RESET}:")

    if not exchange or not exchange.turns:
        if exchange and exchange.dynamic == SpeakingDynamic.SILENCE:
            print(f"   {C_DIM}[Deliberate Pause - Natural broadcast breathing room]{C_RESET}")
        else:
            print(f"   {C_DIM}[No commentary generated]{C_RESET}")
    else:
        for turn in exchange.turns:
            speaker_color = C_CYAN if turn.speaker == CommentatorRole.HOST else C_GREEN
            speaker_name = "HOST (James)" if turn.speaker == CommentatorRole.HOST else "ANALYST (Peter - GM)"
            emotion_tag = f"{C_YELLOW}({turn.emotion.value}){C_RESET}"
            print(f"   {speaker_color}{C_BOLD}[{speaker_name}]{C_RESET} {emotion_tag}: \"{turn.text}\"")

    print("═" * 84)


async def run_live_commentary(game_id: str, replay_all: bool = False):
    clean_id = extract_game_id(game_id)

    target_start_ply = 0
    if not replay_all:
        print(f"\nDetecting current game progress on Lichess for ID: {C_BOLD}{clean_id}{C_RESET}...")
        target_start_ply = fetch_current_game_ply(clean_id)
        if target_start_ply > 0:
            print(f"{C_GREEN}✓ Live position detected at Ply {target_start_ply}. Fast-syncing history...{C_RESET}")
        else:
            print("Game is at the start or count could not be retrieved. Commentary starts from move 1.")

    raw_streamer = LichessGameStreamer(
        game_id=clean_id,
        time_trouble_threshold_seconds=settings.time_trouble_threshold_seconds,
        read_timeout_seconds=None,
    )
    paced_streamer = PacedMoveStreamer(
        streamer=raw_streamer,
        fast_forward_initial_history=True,
        max_paced_move_delay_seconds=settings.max_paced_move_delay_seconds,
    )

    engine = StockfishEngine(
        binary_path=settings.stockfish_path,
        multipv=settings.stockfish_multipv,
        depth=settings.stockfish_depth,
        movetime_ms=settings.stockfish_movetime_ms,
    )
    book = OpeningBook(
        book_path=settings.opening_book_path,
        min_weight=settings.opening_book_min_weight,
    )
    opening_tracker = GameOpeningTracker(book=book)
    analyzer = MoveAnalyzer(
        engine=engine,
        opening_tracker=opening_tracker,
        shallow_depth=4,
        shallow_movetime_ms=40,
    )

    director = BroadcastDirector(history_limit=6)
    agent = CommentaryAgent()

    white_username = "White"
    black_username = "Black"

    await engine.start()
    print(f"{C_GREEN}✓ Stockfish engine and Commentary agent online.{C_RESET}")
    print("Press Ctrl+C to stop stream.\n" + "=" * 84)

    try:
        async for event in paced_streamer.stream_paced_events():
            if isinstance(event, GameMetadata):
                white_username = event.white_player.username
                black_username = event.black_player.username
                print(f"\n[BROADCAST CONNECTED] {white_username} (White) vs {black_username} (Black)")
                print(f"Format: {event.speed.upper()} | Game ID: {event.game_id}")
                print("=" * 84)
                analyzer.reset()
                director.reset(game_format=event.speed)
                continue

            elif isinstance(event, ParsedMoveEvent):
                if event.turn == "white" and event.acting_player:
                    white_username = event.acting_player
                elif event.turn == "black" and event.acting_player:
                    black_username = event.acting_player

                # CASE A: Fast-sync historical moves without running Stockfish or LLM
                if target_start_ply > 1 and event.ply < (target_start_ply - 1):
                    current_move = chess.Move.from_uci(event.uci)
                    analyzer.opening_tracker.process_move(
                        board_before=analyzer.board.copy(),
                        move=current_move,
                        move_san=event.san,
                        ply=event.ply,
                    )
                    if current_move in analyzer.board.legal_moves:
                        analyzer.board.push(current_move)
                    else:
                        analyzer.board.set_fen(event.fen)

                    print(f"\r{C_DIM}>>> Fast-syncing: {event.san:<6} (Ply {event.ply}/{target_start_ply})...{C_RESET}", end="", flush=True)
                    continue

                # CASE B: Prime Stockfish on the ply immediately preceding the latest move
                elif target_start_ply > 1 and event.ply == (target_start_ply - 1):
                    current_move = chess.Move.from_uci(event.uci)
                    analyzer.opening_tracker.process_move(
                        board_before=analyzer.board.copy(),
                        move=current_move,
                        move_san=event.san,
                        ply=event.ply,
                    )
                    if current_move in analyzer.board.legal_moves:
                        analyzer.board.push(current_move)
                    else:
                        analyzer.board.set_fen(event.fen)

                    print(f"\r{C_DIM}>>> Priming Stockfish baseline on Ply {event.ply}...{C_RESET}", end="", flush=True)
                    analyzer.previous_analysis = await analyzer.engine.analyze_position(event.fen)
                    analyzer.previous_move = current_move
                    continue

                # CASE C: Latest move and all live incoming moves (Evaluate + Generate Commentary)
                print(f"\r" + " " * 75 + "\r", end="", flush=True)

                evaluation = await analyzer.evaluate_move(event)

                context = director.assemble_context(
                    eval_data=evaluation,
                    event=event,
                    white_player=white_username,
                    black_player=black_username,
                    pending_audio_seconds=0.0,
                )

                t0 = time.perf_counter()
                exchange = await agent.generate_commentary(context)
                llm_elapsed_ms = (time.perf_counter() - t0) * 1000

                director.record_exchange(exchange)

                render_broadcast_screen(
                    eval_data=evaluation,
                    event=event,
                    exchange=exchange,
                    llm_elapsed_ms=llm_elapsed_ms,
                )

                if event.termination_reason:
                    print(f"\n[GAME OVER] Result: {event.termination_reason}\n")
                    break

    except asyncio.CancelledError:
        print("\nBroadcast stopped.")
    except Exception as exc:
        print(f"\nBroadcast error: {exc}")
    finally:
        print("\nShutting down commentary system...")
        paced_streamer.stop()
        await engine.close()
        book.close()
        print("Engine and resources closed cleanly.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Live dual-commentator broadcast test harness.")
    parser.add_argument("game_id", type=str, help="Lichess game ID or URL (e.g., https://lichess.org/kSc2w4MX)")
    parser.add_argument(
        "--replay-all",
        action="store_true",
        help="Generate commentary on all historical moves from move 1 instead of jumping to the latest move.",
    )
    args = parser.parse_args()

    try:
        asyncio.run(run_live_commentary(args.game_id, replay_all=args.replay_all))
    except KeyboardInterrupt:
        print("\nExited via user interrupt.")
        sys.exit(0)