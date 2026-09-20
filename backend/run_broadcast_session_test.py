import argparse
import asyncio
import sys
import time
from pathlib import Path

# Ensure project root and backend directory are in sys.path
CURRENT_DIR = Path(__file__).resolve().parent
sys.path.extend([
    str(CURRENT_DIR),
    str(CURRENT_DIR / "backend"),
])

from app.services.broadcast_session import (
    BroadcastEventType,
    BroadcastFrame,
    BroadcastSession,
)
from app.services.broadcast_session import BroadcastSession

# ANSI formatting for readability
C_RESET = "\033[0m"
C_BOLD = "\033[1m"
C_DIM = "\033[2m"
C_CYAN = "\033[96m"      # Host
C_GREEN = "\033[92m"     # Analyst
C_YELLOW = "\033[93m"    # Clocks & Audio
C_RED = "\033[91m"       # Blunders / Errors
C_MAGENTA = "\033[95m"   # Openings / Brilliancies


def format_clock(seconds):
    if seconds is None:
        return "--:--"
    m, s = divmod(int(seconds), 60)
    return f"{m:02d}:{s:02d}"


def render_frame(frame: BroadcastFrame):
    """Formats and prints incoming broadcast frames from the session."""
    if frame.event_type == BroadcastEventType.MATCH_CONNECTED:
        meta = frame.metadata
        event_title = getattr(meta, "event_name", None) or getattr(meta, "speed", "Live Match").capitalize()
        print("\n" + "═" * 84)
        print(f" {C_BOLD}[MATCH CONNECTED]{C_RESET} {meta.white_player.username} vs {meta.black_player.username}")
        print(f" Event: {event_title} | Format: {meta.speed.upper()} | Game ID: {frame.game_id}")
        print("═" * 84)

    elif frame.event_type == BroadcastEventType.FAST_FORWARD_PROGRESS:
        print(
            f"\r{C_DIM}>>> [FAST-SYNC] Ply {frame.ply:02d} | Move: {frame.played_san:<6} | Clocks: W {format_clock(frame.clock_white)} / B {format_clock(frame.clock_black)}{C_RESET}",
            end="",
            flush=True,
        )

    elif frame.event_type == BroadcastEventType.MOVE_EVALUATION:
        eval_data = frame.evaluation
        exchange = frame.commentary
        move_num = (frame.ply + 1) // 2
        prefix = f"{move_num}." if frame.turn == "white" else f"{move_num}..."

        print(f"\r" + " " * 80 + "\r", end="", flush=True)  # Clear fast-sync line
        print("\n" + "─" * 84)
        print(
            f" {C_BOLD}{prefix:<6} {frame.played_san:<7}{C_RESET} | "
            f"Turn: {frame.turn.capitalize():<5} | "
            f"Quality: {eval_data.classification.value:<10} | "
            f"Clocks: W {format_clock(frame.clock_white)} / B {format_clock(frame.clock_black)}"
        )

        if eval_data.opening_name:
            print(f" {C_MAGENTA}Opening : [{eval_data.eco_code or ''}] {eval_data.opening_name}{C_RESET}")

        eval_str = f"{eval_data.eval_cp_after / 100:+.2f}" if eval_data.eval_cp_after is not None else "0.00"
        print(f" Position: Eval {eval_str:>6} | Loss: {abs(eval_data.eval_swing_cp) / 100:.2f} pawns")

        # Commentary & TTS details
        if exchange and exchange.turns:
            print(f"\n 🎙️ {C_BOLD}COMMENTARY{C_RESET} {C_DIM}(Dynamic: {exchange.dynamic.value}){C_RESET}:")
            for turn in exchange.turns:
                speaker_color = C_CYAN if turn.speaker.value == "HOST" else C_GREEN
                print(f"   {speaker_color}{C_BOLD}[{turn.speaker.value}]{C_RESET} ({turn.emotion.value}): \"{turn.text}\"")
                if turn.audio_url:
                    print(f"      {C_YELLOW}↳ Audio: {turn.audio_url} ({turn.estimated_duration_seconds}s){C_RESET}")
            print(f"   {C_DIM}Pending Audio Queue: {frame.pending_audio_seconds:.1f}s{C_RESET}")
        else:
            print(f" 🎙️ {C_DIM}[Silent Pause - No audio generated]{C_RESET}")

        print("─" * 84)

    elif frame.event_type == BroadcastEventType.GAME_OVER:
        print(f"\n{C_BOLD}[GAME FINISHED]{C_RESET} Result: {frame.termination_reason}\n")

    elif frame.event_type == BroadcastEventType.ERROR:
        print(f"\n{C_RED}[SESSION ERROR]{C_RESET} {frame.termination_reason}\n")


async def run_test(
    game_id: str,
    round_id: str = None,
    replay_all: bool = True,
    enable_tts: bool = False,
    pace_delay: float = 2.0,
):
    session = BroadcastSession(
        game_id=game_id,
        round_id=round_id,
        replay_all=replay_all,
        enable_tts=enable_tts,
        max_paced_move_delay_seconds=pace_delay,
    )

    print(f"\n{'='*75}")
    if round_id:
        print(f" BROADCAST TEST: Round '{round_id}' | Game/Board '{game_id}'")
    else:
        print(f" MATCH TEST    : Game '{game_id}'")
    print(f" Pacing Delay  : Max {pace_delay}s per move")
    print(f" TTS Synthesis : {'ENABLED' if enable_tts else 'DISABLED'}")
    print(f"{'='*75}\n")

    try:
        async for frame in session.stream_broadcast():
            render_frame(frame)
    except KeyboardInterrupt:
        print("\nTest stopped by user.")
    finally:
        await session.stop()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Test BroadcastSession on FIDE / Lichess games.")
    parser.add_argument("game_id", type=str, help="Game ID, Board number, or Player name (e.g. 1HZnfDdq, 1, Gledura)")
    parser.add_argument("--round-id", "-r", type=str, default=None, help="Lichess broadcast round ID (e.g. HnCuRMmB)")
    parser.add_argument("--pace-delay", "-p", type=float, default=2.0, help="Max seconds to pause between moves (default: 2.0s)")
    parser.add_argument("--enable-tts", action="store_true", help="Enable ElevenLabs TTS audio generation")
    args = parser.parse_args()

    asyncio.run(
            run_test(
                game_id=args.game_id,
                round_id=args.round_id,
                replay_all=True,
                enable_tts=args.enable_tts,
                pace_delay=args.pace_delay,
            )
        )