# backend/tests/test_pacing_and_commentary.py
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.append(str(BACKEND_DIR))

from app.config import settings
from app.lichess.pacing_buffer import PacedMoveStreamer
from app.lichess.pgn_parser import ParsedMoveEvent
from app.engine.schemas import MoveEvaluation, MoveClassification
from app.commentary.director import BroadcastDirector
from app.commentary.schemas import (
    SpeakingDynamic,
    ThinkCategory,
    CommentatorRole,
    DialogueTurn,
    CommentaryExchange,
)
from app.commentary.prompts import build_commentary_prompt, san_to_spoken_move
from app.commentary.agent import CommentaryAgent
from app.services.tts_service import TTSService


def test_pacing_buffer_formats():
    print("--- 1. Testing PacedMoveStreamer Format Adaptation ---")
    streamer = PacedMoveStreamer(streamer=None, game_format="blitz")
    assert streamer.max_paced_move_delay == settings.pacing_buffer_max_delay_blitz, f"Expected {settings.pacing_buffer_max_delay_blitz}, got {streamer.max_paced_move_delay}"

    streamer.set_game_format("rapid")
    assert streamer.max_paced_move_delay == settings.pacing_buffer_max_delay_rapid, f"Expected {settings.pacing_buffer_max_delay_rapid}, got {streamer.max_paced_move_delay}"
    print(f"[PASS] Rapid pacing max delay correctly set to {streamer.max_paced_move_delay}s")

    streamer.set_game_format("bullet")
    assert streamer.max_paced_move_delay == settings.pacing_buffer_max_delay_bullet
    print(f"[PASS] Bullet pacing max delay correctly set to {streamer.max_paced_move_delay}s")

    streamer.set_game_format("classical")
    assert streamer.max_paced_move_delay == settings.pacing_buffer_max_delay_classical
    print(f"[PASS] Classical pacing max delay correctly set to {streamer.max_paced_move_delay}s")


def test_director_think_classification():
    print("\n--- 2. Testing BroadcastDirector Think Classification in Rapid ---")
    director = BroadcastDirector(game_format="rapid")

    assert director.classify_think_time(0.5) == ThinkCategory.INSTANT
    assert director.classify_think_time(6.0) == ThinkCategory.NORMAL
    assert director.classify_think_time(16.0) == ThinkCategory.THINK
    assert director.classify_think_time(35.0) == ThinkCategory.DEEP_THINK
    print("[PASS] Rapid think times correctly classified: 0.5s->INSTANT, 6s->NORMAL, 16s->THINK, 35s->DEEP_THINK")

    # In Blitz
    director_blitz = BroadcastDirector(game_format="blitz")
    assert director_blitz.classify_think_time(1.0) == ThinkCategory.INSTANT
    assert director_blitz.classify_think_time(16.0) == ThinkCategory.DEEP_THINK
    print("[PASS] Blitz think times correctly classified: 1.0s->INSTANT, 16s->DEEP_THINK")


def test_director_dynamic_and_word_budget():
    print("\n--- 3. Testing Director Speaking Dynamic & Word Budget on Rapid Deep Think ---")
    director = BroadcastDirector(game_format="rapid")

    eval_data = MoveEvaluation(
        ply=24,
        turn="white",
        played_uci="d2d4",
        played_san="d4",
        fen_after="rnbqkbnr/pppppppp/8/8/3P4/8/PPP1PPPP/RNBQKBNR b KQkq - 0 1",
        eval_cp_after=30,
        eval_swing_cp=0,
        classification=MoveClassification.GOOD,
        win_prob_before=0.54,
        win_prob_after=0.54,
        win_prob_loss=0.0,
    )

    event_deep_think = ParsedMoveEvent(
        ply=24,
        turn="white",
        uci="d2d4",
        san="d4",
        fen="rnbqkbnr/pppppppp/8/8/3P4/8/PPP1PPPP/RNBQKBNR b KQkq - 0 1",
        move_time_spent_seconds=32.5,
        white_clock_seconds=420.0,
        black_clock_seconds=450.0,
        is_check=False,
        is_checkmate=False,
        is_stalemate=False,
        is_draw=False,
        is_time_trouble=False,
    )

    context = director.assemble_context(
        eval_data=eval_data,
        event=event_deep_think,
        white_player="Alice",
        black_player="Bob",
    )

    assert context.think_category == ThinkCategory.DEEP_THINK
    assert context.move_time_spent_seconds == 32.5
    assert context.dynamic in (SpeakingDynamic.BANTER, SpeakingDynamic.SOLO_ANALYST)
    assert "15-20 words" in context.target_word_range
    print(f"[PASS] Deep Think produced dynamic '{context.dynamic.value}' and budget '{context.target_word_range}'")

    prompt = build_commentary_prompt(context)
    assert "DEEP THINK SPOTLIGHT" in prompt
    assert "32.5s" in prompt
    assert "Target Word Budget: 15-20 words" in prompt
    print("[PASS] build_commentary_prompt includes DEEP THINK SPOTLIGHT and word budget")


def test_director_instant_move_rapid():
    print("\n--- 4. Testing Director Instant Move in Rapid ---")
    director = BroadcastDirector(game_format="rapid")
    eval_data = MoveEvaluation(
        ply=10,
        turn="black",
        played_uci="g8f6",
        played_san="Nf6",
        fen_after="rnbqkb1r/pppppppp/5n2/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 1 2",
        eval_cp_after=10,
        eval_swing_cp=0,
        classification=MoveClassification.GOOD,
        win_prob_before=0.51,
        win_prob_after=0.51,
        win_prob_loss=0.0,
    )
    event_instant = ParsedMoveEvent(
        ply=10,
        turn="black",
        uci="g8f6",
        san="Nf6",
        fen="rnbqkb1r/pppppppp/5n2/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 1 2",
        move_time_spent_seconds=0.4,
        white_clock_seconds=580.0,
        black_clock_seconds=595.0,
        is_check=False,
        is_checkmate=False,
        is_stalemate=False,
        is_draw=False,
        is_time_trouble=False,
    )

    context = director.assemble_context(
        eval_data=eval_data,
        event=event_instant,
        white_player="Alice",
        black_player="Bob",
    )

    assert context.think_category == ThinkCategory.INSTANT
    assert context.dynamic == SpeakingDynamic.PLAY_BY_PLAY
    assert "2-5 words" in context.target_word_range
    print(f"[PASS] Instant move produced dynamic '{context.dynamic.value}' and target word budget '{context.target_word_range}'")

    prompt = build_commentary_prompt(context)
    assert "INSTANT MOVE" in prompt
    assert "PLAY_BY_PLAY" in prompt
    print("[PASS] build_commentary_prompt includes INSTANT MOVE guidance")


def test_agent_fallback():
    print("\n--- 5. Testing CommentaryAgent Fallback on Deep Think ---")
    agent = CommentaryAgent()
    eval_data = MoveEvaluation(
        ply=20,
        turn="white",
        played_uci="c2c4",
        played_san="c4",
        fen_after="rnbqkbnr/pp1ppppp/8/2p5/2P5/8/PP1PPPPP/RNBQKBNR w KQkq - 0 2",
        eval_cp_after=20,
        eval_swing_cp=0,
        classification=MoveClassification.GOOD,
        win_prob_before=0.52,
        win_prob_after=0.52,
        win_prob_loss=0.0,
    )
    director = BroadcastDirector(game_format="rapid")
    event = ParsedMoveEvent(
        ply=20,
        turn="white",
        uci="c2c4",
        san="c4",
        fen="rnbqkbnr/pp1ppppp/8/2p5/2P5/8/PP1PPPPP/RNBQKBNR w KQkq - 0 2",
        move_time_spent_seconds=28.0,
        white_clock_seconds=400.0,
        black_clock_seconds=410.0,
        is_check=False,
        is_checkmate=False,
        is_stalemate=False,
        is_draw=False,
        is_time_trouble=False,
    )
    context = director.assemble_context(eval_data, event, "Alice", "Bob")
    fallback = agent._generate_fallback_turns(context, priority=2)
    assert len(fallback) == 2
    assert "deep think of 28 seconds" in fallback[0].text
    print(f"[PASS] Fallback turn acknowledges deep think: \"{fallback[0].text}\"")


def test_pondering_context_and_prompt():
    print("\n--- 6. Testing Pondering Context & Phrasing Rules ---")
    director = BroadcastDirector(game_format="rapid")
    context = director.assemble_pondering_context(
        ply=14,
        turn="white",
        acting_player="Laura",
        fen="rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
        elapsed_think_seconds=14.5,
        candidate_suggestions=["c4", "Nf3"],
        white_player="Laura",
        black_player="Peter",
    )
    assert context.is_pondering is True
    assert context.target_word_range == "12-16 words total"
    assert context.candidate_suggestions == ["c4", "Nf3"]

    prompt = build_commentary_prompt(context)
    assert "IN THE TANK / PONDERING" in prompt
    assert "SPECULATE CONDITIONALLY" in prompt
    assert "REQUIRED PHRASING STYLE" in prompt
    assert "DO NOT claim you know what they ARE thinking" in prompt
    assert "c4, Nf3" in prompt
    print("[PASS] Pondering prompt strictly enforces conditional speculation & candidate suggestions")


def test_post_pondered_move_budget():
    print("\n--- 7. Testing Post-Pondered Move Punchy Reaction ---")
    director = BroadcastDirector(game_format="rapid")
    eval_data = MoveEvaluation(
        ply=15,
        turn="white",
        played_uci="c2c4",
        played_san="c4",
        fen_after="rnbqkbnr/pppppppp/8/8/2P5/8/PP1PPPPP/RNBQKBNR b KQkq - 0 1",
        eval_cp_after=15,
        eval_swing_cp=0,
        classification=MoveClassification.GOOD,
        win_prob_before=0.52,
        win_prob_after=0.52,
        win_prob_loss=0.0,
    )
    event = ParsedMoveEvent(
        ply=15,
        turn="white",
        uci="c2c4",
        san="c4",
        fen="rnbqkbnr/pppppppp/8/8/2P5/8/PP1PPPPP/RNBQKBNR b KQkq - 0 1",
        move_time_spent_seconds=18.0,
        white_clock_seconds=500.0,
        black_clock_seconds=520.0,
        is_check=False,
        is_checkmate=False,
        is_stalemate=False,
        is_draw=False,
        is_time_trouble=False,
    )
    context = director.assemble_context(eval_data, event, "Laura", "Peter", was_pondered=True)
    assert context.was_pondered is True
    assert "5-10 words total" in context.target_word_range

    prompt = build_commentary_prompt(context)
    assert "Target Word Budget: 5-10 words total" in prompt
    assert "POST-PONDERED MOVE:" in prompt
    assert "You already discussed candidate ideas while White was in the tank!" in prompt
    print("[PASS] Post-pondered move correctly assigned 5-10 words ultra-crisp budget")


def test_stream_paced_events_yields_pondering():
    import asyncio
    from unittest.mock import patch, AsyncMock
    from app.lichess.pgn_parser import PonderingEvent

    print("\n--- 8. Testing PacedMoveStreamer Pondering Event Emission ---")
    class MockStreamer:
        async def stream_game_events(self):
            yield ParsedMoveEvent(
                ply=10,
                turn="white",
                uci="d2d4",
                san="d4",
                fen="rnbqkbnr/pppppppp/8/8/3P4/8/PPP1PPPP/RNBQKBNR b KQkq - 0 1",
                move_time_spent_seconds=18.0,
                white_clock_seconds=500.0,
                black_clock_seconds=500.0,
                is_check=False,
                is_checkmate=False,
                is_stalemate=False,
                is_draw=False,
                is_time_trouble=False,
                acting_player="Laura",
            )

    async def run_test():
        streamer = PacedMoveStreamer(
            streamer=MockStreamer(),
            fast_forward_initial_history=False,
            game_format="rapid",
            enable_pondering=True,
        )
        emitted = []
        with patch("asyncio.sleep", new_callable=AsyncMock):
            async for ev in streamer.stream_paced_events():
                emitted.append(ev)
        return emitted

    emitted = asyncio.run(run_test())
    assert len(emitted) == 2, f"Expected 2 events (PonderingEvent + ParsedMoveEvent), got {len(emitted)}"
    assert isinstance(emitted[0], PonderingEvent)
    assert emitted[0].acting_player == "Laura"
    assert emitted[0].turn == "white"
    assert isinstance(emitted[1], ParsedMoveEvent)
    assert emitted[1].san == "d4"
    print(f"[PASS] Streamer emitted PonderingEvent ({emitted[0].acting_player} calculating) followed by ParsedMoveEvent ({emitted[1].san})")


def test_agent_pondering_fallback():
    print("\n--- 9. Testing CommentaryAgent Fallback for Pondering & Was Pondered ---")
    agent = CommentaryAgent()
    director = BroadcastDirector(game_format="rapid")
    pondering_ctx = director.assemble_pondering_context(
        ply=10,
        turn="black",
        acting_player="Bob",
        fen="rnbqkbnr/pppppppp/8/8/3P4/8/PPP1PPPP/RNBQKBNR b KQkq - 0 1",
        elapsed_think_seconds=15.0,
        candidate_suggestions=["Nf6", "d5"],
        white_player="Alice",
        black_player="Bob",
    )
    fallback_ponder = agent._generate_fallback_turns(pondering_ctx, priority=1)
    assert len(fallback_ponder) == 1
    assert "might be weighing options" in fallback_ponder[0].text
    assert "Nf6, d5" in fallback_ponder[0].text
    assert fallback_ponder[0].speaker == CommentatorRole.ANALYST

    eval_data = MoveEvaluation(
        ply=10,
        turn="black",
        played_uci="g8f6",
        played_san="Nf6",
        fen_after="rnbqkb1r/pppppppp/5n2/8/3P4/8/PPP1PPPP/RNBQKBNR w KQkq - 1 2",
        eval_cp_after=10,
        eval_swing_cp=0,
        classification=MoveClassification.GOOD,
        win_prob_before=0.5,
        win_prob_after=0.5,
        win_prob_loss=0.0,
    )
    event = ParsedMoveEvent(
        ply=10,
        turn="black",
        uci="g8f6",
        san="Nf6",
        fen="rnbqkb1r/pppppppp/5n2/8/3P4/8/PPP1PPPP/RNBQKBNR w KQkq - 1 2",
        move_time_spent_seconds=15.0,
        white_clock_seconds=500.0,
        black_clock_seconds=500.0,
        is_check=False,
        is_checkmate=False,
        is_stalemate=False,
        is_draw=False,
        is_time_trouble=False,
    )
    post_ctx = director.assemble_context(eval_data, event, "Alice", "Bob", was_pondered=True)
    fallback_post = agent._generate_fallback_turns(post_ctx, priority=1)
    assert len(fallback_post) == 1
    assert "And the decision is Nf6." in fallback_post[0].text
    print(f"[PASS] Pondering and Post-Pondered fallbacks verified: \"{fallback_ponder[0].text}\" and \"{fallback_post[0].text}\"")


def test_san_to_spoken_move():
    print("\n--- 10. Testing SAN to Spoken Move Converter ---")
    from app.commentary.agent import san_to_spoken_move

    assert san_to_spoken_move("Be6") == "Bishop to e6."
    assert san_to_spoken_move("O-O") == "Castles."
    assert san_to_spoken_move("O-O-O") == "Castles queenside."
    assert san_to_spoken_move("Nxd5") == "Knight takes on d5."
    assert san_to_spoken_move("exd5") == "Takes on d5."
    assert san_to_spoken_move("c4") == "c4."
    assert san_to_spoken_move("Qh5+") == "Queen to h5, check!"
    assert san_to_spoken_move("Qxf7#") == "Queen takes on f7, checkmate!"
    assert san_to_spoken_move("e8=Q") == "Pawn promotes to Queen."
    print("[PASS] san_to_spoken_move handles castling, piece moves, captures, checks, and mates")


def test_play_by_play_dynamic():
    print("\n--- 11. Testing PLAY_BY_PLAY Dynamic in Fast Sequences ---")
    director = BroadcastDirector(game_format="rapid")
    director.dialogue_history.append(
        DialogueTurn(speaker=CommentatorRole.HOST, text="Welcome to the game.")
    )

    eval_data = MoveEvaluation(
        ply=12,
        turn="white",
        played_uci="c1e3",
        played_san="Be6",
        fen_after="rnbqk2r/pp1pbppp/4pn2/2p5/2P5/4PN2/PP1PBPPP/RNBQK2R w KQkq - 2 5",
        eval_cp_after=10,
        eval_swing_cp=0,
        classification=MoveClassification.GOOD,
        win_prob_before=0.5,
        win_prob_after=0.5,
        win_prob_loss=0.0,
    )
    event = ParsedMoveEvent(
        ply=12,
        turn="white",
        uci="c1e3",
        san="Be6",
        fen="rnbqk2r/pp1pbppp/4pn2/2p5/2P5/4PN2/PP1PBPPP/RNBQK2R w KQkq - 2 5",
        move_time_spent_seconds=0.8,
        white_clock_seconds=500.0,
        black_clock_seconds=500.0,
        is_check=False,
        is_checkmate=False,
        is_stalemate=False,
        is_draw=False,
        is_time_trouble=False,
    )

    context = director.assemble_context(eval_data, event, "Alice", "Bob")
    assert context.dynamic == SpeakingDynamic.PLAY_BY_PLAY
    assert "2-5 words total" in context.target_word_range
    print(f"[PASS] Fast sequence triggered dynamic '{context.dynamic.value}' with budget '{context.target_word_range}'")

    prompt = build_commentary_prompt(context)
    assert "FORMAT: PLAY_BY_PLAY" in prompt
    assert "Target Word Budget: 2-5 words total" in prompt
    assert "Simply call the played move cleanly" in prompt
    print("[PASS] build_commentary_prompt generates PLAY_BY_PLAY directives")

    agent = CommentaryAgent()
    fallback = agent._generate_fallback_turns(context, priority=2)
    assert len(fallback) == 1
    assert fallback[0].text == "Bishop to e6."
    print(f"[PASS] Agent fallback produced spoken call: \"{fallback[0].text}\"")


def test_pondering_cooldown_and_guards():
    import asyncio
    from unittest.mock import patch, AsyncMock
    from app.lichess.pgn_parser import PonderingEvent

    print("\n--- 12. Testing Pondering Cooldown & Opening/Time Guards ---")
    class ConsecutiveMockStreamer:
        async def stream_game_events(self):
            # Move 1: Ply 12 (White) - 20s think -> SHOULD ponder
            yield ParsedMoveEvent(
                ply=12,
                turn="white",
                uci="e2e4",
                san="e4",
                fen="rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1",
                move_time_spent_seconds=20.0,
                white_clock_seconds=500.0,
                black_clock_seconds=500.0,
                is_check=False,
                is_checkmate=False,
                is_stalemate=False,
                is_draw=False,
                is_time_trouble=False,
                acting_player="White",
            )
            # Move 2: Ply 13 (Black) - 20s think -> COOLDOWN ACTIVE (ply 13 - 12 = 1 < 4), should NOT ponder
            yield ParsedMoveEvent(
                ply=13,
                turn="black",
                uci="e7e5",
                san="e5",
                fen="rnbqkbnr/pppp1ppp/8/4p3/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 2",
                move_time_spent_seconds=20.0,
                white_clock_seconds=500.0,
                black_clock_seconds=500.0,
                is_check=False,
                is_checkmate=False,
                is_stalemate=False,
                is_draw=False,
                is_time_trouble=False,
                acting_player="Black",
            )
            # Move 3: Ply 16 (White) - 20s think -> COOLDOWN PASSED (ply 16 - 12 = 4 >= 4), SHOULD ponder
            yield ParsedMoveEvent(
                ply=16,
                turn="white",
                uci="g1f3",
                san="Nf3",
                fen="rnbqkbnr/pppp1ppp/8/4p3/4P3/5N2/PPPP1PPP/RNBQKB1R b KQkq - 1 2",
                move_time_spent_seconds=20.0,
                white_clock_seconds=500.0,
                black_clock_seconds=500.0,
                is_check=False,
                is_checkmate=False,
                is_stalemate=False,
                is_draw=False,
                is_time_trouble=False,
                acting_player="White",
            )

    async def run_test():
        streamer = PacedMoveStreamer(
            streamer=ConsecutiveMockStreamer(),
            fast_forward_initial_history=False,
            game_format="rapid",
            enable_pondering=True,
            cooldown_plies=4,
            min_ponder_ply=8,
        )
        emitted = []
        with patch("asyncio.sleep", new_callable=AsyncMock):
            async for ev in streamer.stream_paced_events():
                emitted.append(ev)
        return emitted

    emitted = asyncio.run(run_test())
    ponder_events = [ev for ev in emitted if isinstance(ev, PonderingEvent)]
    move_events = [ev for ev in emitted if isinstance(ev, ParsedMoveEvent)]
    assert len(move_events) == 3
    assert len(ponder_events) == 2, f"Expected exactly 2 ponder events, got {len(ponder_events)}"
    print("[PASS] Pondering cooldown successfully prevented consecutive back-to-back pondering events!")


def test_temporal_phrasing_sanitizer():
    print("\n--- 13. Testing Prospective Temporal Phrasing Sanitizer ---")
    raw_text_1 = "Greedy. Missed knight to e4; White now plays a4."
    cleaned_1 = CommentaryAgent._sanitize_temporal_phrasing(raw_text_1, opponent_color="White")
    assert cleaned_1 == "Greedy. Missed knight to e4; White can now play a4."

    raw_text_2 = "Greedy. Missed knight to e4. White plays a4."
    cleaned_2 = CommentaryAgent._sanitize_temporal_phrasing(raw_text_2, opponent_color="White")
    assert "White plays" not in cleaned_2
    assert "a4" in cleaned_2

    raw_text_3 = "White now strikes with bishop to c4."
    cleaned_3 = CommentaryAgent._sanitize_temporal_phrasing(raw_text_3, opponent_color="White")
    assert cleaned_3 == "White can now strike with bishop to c4."

    # Verify 'now eyes' formulaic crutch is stripped
    raw_text_eyes = "White spent nearly a minute weighing the pawn to d3 tension. Black now eyes rook to e8."
    cleaned_eyes = CommentaryAgent._sanitize_temporal_phrasing(raw_text_eyes, opponent_color="Black")
    assert "now eyes" not in cleaned_eyes
    assert "rook to e8" in cleaned_eyes

    # Verify 'plays [move]' without leading punctuation is converted
    raw_text_unplayed = "Black plays e4."
    cleaned_unplayed = CommentaryAgent._sanitize_temporal_phrasing(raw_text_unplayed, opponent_color="Black")
    assert "Black plays" not in cleaned_unplayed
    assert "e4" in cleaned_unplayed

    # Active player who actually moved should NOT be rewritten
    active_player_text = "Black plays bishop to g7."
    kept_active = CommentaryAgent._sanitize_temporal_phrasing(active_player_text, opponent_color="White")
    assert kept_active == "Black plays bishop to g7."
    print("[PASS] Temporal phrasing correctly converts false present tense for upcoming opponent to modal 'can play'!")


def test_broadcast_pacing_buffer_zero_delay():
    print("\n--- 14. Testing Broadcast Zero Time Buffer across all categories ---")
    # Broadcast streamer initialized with is_broadcast=True
    streamer = PacedMoveStreamer(streamer=None, game_format="classical", is_broadcast=True)
    assert streamer.max_paced_move_delay == 0.0, f"Expected 0.0s for broadcast, got {streamer.max_paced_move_delay}"
    assert streamer.enable_pondering is False, f"Expected enable_pondering=False, got {streamer.enable_pondering}"

    # Verify set_game_format does NOT override zero delay
    for fmt in ("classical", "rapid", "blitz", "bullet"):
        streamer.set_game_format(fmt)
        assert streamer.max_paced_move_delay == 0.0, f"Expected 0.0s after setting {fmt}, got {streamer.max_paced_move_delay}"
        assert streamer.enable_pondering is False

    print("[PASS] Broadcast streamer enforces zero delay and disables pondering across all formats")


def test_initial_moves_parsing_and_status():
    print("\n--- 15. Testing InitialGameStatus and ParsedMoveEvent instantiation ---")
    import io
    import chess.pgn
    from app.services.broadcast_session import InitialGameStatus, matches_broadcast_game
    from app.lichess.pgn_parser import GameMetadata, PlayerInfo, ParsedMoveEvent

    pgn_sample = """[Event "Test Round"]
[Site "https://lichess.org/broadcast/test/game1234"]
[Round "1.1"]
[Board "1"]
[White "Player One"]
[Black "Player Two"]
[Result "1-0"]

1. e4 { [%clk 0:15:00] } 1... e5 { [%clk 0:14:55] } 2. Nf3 { [%clk 0:14:50] } 1-0
"""
    game = chess.pgn.read_game(io.StringIO(pgn_sample))
    assert matches_broadcast_game(game, "game1234") is True
    assert matches_broadcast_game(game, "1") is True

    mv = ParsedMoveEvent(
        ply=1,
        turn="white",
        uci="e2e4",
        san="e4",
        fen="rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1",
    )
    assert mv.is_time_trouble is False

    status = InitialGameStatus(
        is_ended=True,
        metadata=GameMetadata(
            game_id="game1234",
            speed="classical",
            variant="standard",
            rated=True,
            white_player=PlayerInfo(username="Player One"),
            black_player=PlayerInfo(username="Player Two"),
        ),
        current_ply=3,
        current_fen="rnbqkbnr/pppp1ppp/8/4p3/4P3/5N2/PPPP1PPP/RNBQKB1R b KQkq - 1 2",
        winner="white",
        result_code="1-0",
        termination_reason="1-0 - Player One wins",
        initial_moves=[mv],
    )
    assert len(status.initial_moves) == 1
    print("[PASS] InitialGameStatus and ParsedMoveEvent instantiated successfully!")


def test_opening_phase_prompt_and_director():
    print("\n--- 16. Testing Opening Phase Prompt Guidance & Director Recaptures ---")
    director = BroadcastDirector(game_format="rapid")

    # 1. Opening Book Move Prompt: suppresses prospective continuations, provides opening guidance
    book_eval = MoveEvaluation(
        ply=2,
        turn="black",
        played_uci="c7c5",
        played_san="c5",
        fen_after="rnbqkbnr/pp1ppppp/8/2p5/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 2",
        eval_cp_after=20,
        eval_swing_cp=0,
        classification=MoveClassification.BOOK,
        is_book=True,
        opening_name="Sicilian Defense",
        win_prob_before=0.52,
        win_prob_after=0.52,
        win_prob_loss=0.0,
    )
    book_event = ParsedMoveEvent(
        ply=2,
        turn="black",
        uci="c7c5",
        san="c5",
        fen="rnbqkbnr/pp1ppppp/8/2p5/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 2",
        move_time_spent_seconds=0.5,
        white_clock_seconds=600.0,
        black_clock_seconds=600.0,
    )
    book_context = director.assemble_context(book_eval, book_event, "Alice", "Bob")
    prompt = build_commentary_prompt(book_context)

    assert "OPENING PHASE GUIDANCE" in prompt
    assert "PROSPECTIVE CONTINUATIONS" not in prompt
    assert "DO NOT predict routine theoretical next moves" in prompt
    assert "can now look to" not in prompt
    assert "—" not in prompt
    assert "–" not in prompt
    print("[PASS] Opening book move suppressed prospective continuations and injected strategic opening guidance with zero em-dashes")

    # 2. Routine Opening Book Recapture: triggers SILENCE
    recapture_eval = MoveEvaluation(
        ply=6,
        turn="black",
        played_uci="c5d4",
        played_san="cxd4",
        fen_after="rnbqkbnr/pp1ppppp/8/8/3pP3/5N2/PPP2PPP/RNBQKB1R w KQkq - 0 3",
        eval_cp_after=20,
        eval_swing_cp=0,
        classification=MoveClassification.BOOK,
        is_book=True,
        opening_name="Sicilian Defense",
        win_prob_before=0.52,
        win_prob_after=0.52,
        win_prob_loss=0.0,
    )
    recapture_event = ParsedMoveEvent(
        ply=6,
        turn="black",
        uci="c5d4",
        san="cxd4",
        fen="rnbqkbnr/pp1ppppp/8/8/3pP3/5N2/PPP2PPP/RNBQKB1R w KQkq - 0 3",
        move_time_spent_seconds=0.3,
        white_clock_seconds=595.0,
        black_clock_seconds=598.0,
    )
    recapture_dynamic = director.determine_speaking_dynamic(
        eval_data=recapture_eval,
        is_time_trouble=False,
        think_category=ThinkCategory.INSTANT,
    )
    assert recapture_dynamic == SpeakingDynamic.PLAY_BY_PLAY
    assert san_to_spoken_move(recapture_eval.played_san) == "Takes on d4."
    print("[PASS] Universal floor: routine book recapture 'cxd4' voiced cleanly as PLAY_BY_PLAY ('Takes on d4.')")

    # 3. Opening Inaccuracy: produces single-voice commentary, not forced two-voice banter
    inaccuracy_eval = MoveEvaluation(
        ply=8,
        turn="white",
        played_uci="d1d2",
        played_san="Qd2",
        fen_after="r1bqkbnr/pp1ppppp/2n5/8/3NP3/8/PPP2PPP/RNBQKB1R b KQkq - 1 4",
        eval_cp_after=-40,
        eval_swing_cp=-60,
        classification=MoveClassification.INACCURACY,
        is_book=False,
        win_prob_before=0.52,
        win_prob_after=0.48,
        win_prob_loss=0.04,
    )
    inaccuracy_dynamic = director.determine_speaking_dynamic(
        eval_data=inaccuracy_eval,
        is_time_trouble=False,
        think_category=ThinkCategory.NORMAL,
    )
    assert inaccuracy_dynamic in (SpeakingDynamic.SOLO_ANALYST, SpeakingDynamic.SOLO_HOST)
    assert inaccuracy_dynamic != SpeakingDynamic.BANTER
    print(f"[PASS] Opening inaccuracy produced single-voice dynamic '{inaccuracy_dynamic.value}' instead of forced banter")


def test_long_audio_guard_and_play_by_play_continuity():
    print("\n--- 17. Testing Long Audio Guard vs Play-by-Play Continuity ---")
    director = BroadcastDirector(game_format="blitz")
    normal_eval = MoveEvaluation(
        ply=12,
        turn="black",
        played_uci="e7e6",
        played_san="e6",
        fen_after="r1bqkb1r/pp1p1ppp/2n1pn2/8/3NP3/2N5/PPP2PPP/R1BQKB1R w KQkq - 0 6",
        eval_cp_after=15,
        eval_swing_cp=0,
        classification=MoveClassification.GOOD,
        win_prob_before=0.50,
        win_prob_after=0.50,
        win_prob_loss=0.0,
        is_book=False,
    )

    # 1. Long audio is playing when next move is played: must return SILENCE
    # Case A: Explicit is_long_audio_playing=True
    dynamic_silent = director.determine_speaking_dynamic(
        eval_data=normal_eval,
        is_time_trouble=False,
        think_category=ThinkCategory.NORMAL,
        is_long_audio_playing=True,
    )
    assert dynamic_silent == SpeakingDynamic.SILENCE
    print("[PASS] Long audio playing while next move is played returned SILENCE")

    # Case B: Recorded exchange was long audio (SOLO_HOST) with pending audio
    long_exchange = CommentaryExchange(
        ply=11,
        move_san="d4",
        turn_color="white",
        dynamic=SpeakingDynamic.SOLO_HOST,
        turns=[
            DialogueTurn(
                speaker=CommentatorRole.HOST,
                text="Magnus launches a classic pawn strike, opening up central diagonals for the bishop.",
                estimated_duration_seconds=4.5,
            )
        ],
    )
    director.record_exchange(long_exchange)
    dynamic_recorded = director.determine_speaking_dynamic(
        eval_data=normal_eval,
        is_time_trouble=False,
        think_category=ThinkCategory.NORMAL,
        pending_audio_seconds=3.0,
    )
    assert dynamic_recorded == SpeakingDynamic.SILENCE
    print("[PASS] Director automatically recognized active long audio and kept next move SILENCE")

    # 2. Play-by-play audio is going on: must keep continuing speaking
    pbp_exchange = CommentaryExchange(
        ply=11,
        move_san="d4",
        turn_color="white",
        dynamic=SpeakingDynamic.PLAY_BY_PLAY,
        turns=[
            DialogueTurn(
                speaker=CommentatorRole.HOST,
                text="Takes on d4.",
                estimated_duration_seconds=1.2,
            )
        ],
    )
    director.record_exchange(pbp_exchange)
    dynamic_pbp = director.determine_speaking_dynamic(
        eval_data=normal_eval,
        is_time_trouble=False,
        think_category=ThinkCategory.NORMAL,
        pending_audio_seconds=0.8,
        is_long_audio_playing=False,
        is_play_by_play_playing=True,
    )
    assert dynamic_pbp != SpeakingDynamic.SILENCE
    assert dynamic_pbp in (SpeakingDynamic.SOLO_HOST, SpeakingDynamic.SOLO_ANALYST, SpeakingDynamic.PLAY_BY_PLAY)
    print(f"[PASS] Play-by-play audio going on kept continuing speaking as '{dynamic_pbp.value}'")

    # 3. Blunder occurs while long audio is playing: emergency interrupt triggers BANTER
    blunder_eval = MoveEvaluation(
        ply=14,
        turn="white",
        played_uci="d1d8",
        played_san="Qxd8??",
        fen_after="r1bQkb1r/pp1p1ppp/2n1pn2/8/4P3/2N5/PPP2PPP/R1B1KB1R b KQkq - 0 7",
        eval_cp_after=-800,
        eval_swing_cp=-850,
        classification=MoveClassification.BLUNDER,
        win_prob_before=0.60,
        win_prob_after=0.02,
        win_prob_loss=0.58,
        is_blunder=True,
    )
    dynamic_blunder = director.determine_speaking_dynamic(
        eval_data=blunder_eval,
        is_time_trouble=False,
        think_category=ThinkCategory.NORMAL,
        is_long_audio_playing=True,
    )
    assert dynamic_blunder == SpeakingDynamic.BANTER
    print("[PASS] Blunder during long audio triggered emergency BANTER interrupt")

    # 4. TTSService time-aware tracking
    tts = TTSService()
    assert not tts.is_long_audio_playing
    assert not tts.is_play_by_play_audio_playing
    # Manually set pending audio as long
    tts.pending_audio_seconds = 5.0
    tts.current_audio_type = "long"
    assert tts.is_long_audio_playing
    assert not tts.is_play_by_play_audio_playing

    # Switch to play-by-play
    tts.current_audio_type = "play_by_play"
    assert tts.is_play_by_play_audio_playing
    assert not tts.is_long_audio_playing

    # Trigger interrupt clears state
    tts.trigger_interrupt()
    assert tts.pending_audio_seconds == 0.0
    assert not tts.is_long_audio_playing
    assert not tts.is_play_by_play_audio_playing
    print("[PASS] TTSService audio classification and interrupt tracking verified")


def test_live_sync_catchup_and_chess_state_tracker():
    print("\n--- 18. Testing Live Sync Catchup and ChessStateTracker Sync ---")
    from app.lichess.pgn_parser import ChessStateTracker, ParsedMoveEvent
    from app.services.broadcast_session import BroadcastFrame, BroadcastEventType

    # 1. Test gameFull packet synchronizes internal board state to pre-existing moves
    tracker = ChessStateTracker()
    game_full_packet = {
        "type": "gameFull",
        "id": "gameTest123",
        "players": {
            "white": {"user": {"name": "Magnus"}, "rating": 2850},
            "black": {"user": {"name": "Hikaru"}, "rating": 2820},
        },
        "state": {
            "moves": "e2e4 e7e5 g1f3 b8c6",
            "wtime": 180000,
            "btime": 178000,
        },
    }
    meta = tracker.parse_lichess_line(game_full_packet)
    assert meta is not None
    assert meta.white_player.username == "Magnus"
    assert meta.black_player.username == "Hikaru"
    assert tracker.processed_ply == 4
    assert tracker.board.ply() == 4
    print("[PASS] gameFull synchronized internal board and advanced processed_ply to 4")

    # 2. Test incremental gameState parsing after gameFull
    game_state_packet = {
        "type": "gameState",
        "moves": "e2e4 e7e5 g1f3 b8c6 f1c4",
        "wtime": 175000,
        "btime": 178000,
    }
    event_5 = tracker.parse_lichess_line(game_state_packet)
    assert isinstance(event_5, ParsedMoveEvent)
    assert event_5.ply == 5
    assert event_5.san == "Bc4"
    assert event_5.turn == "white"
    assert tracker.processed_ply == 5
    print("[PASS] gameState parsed move 5 (Bc4) cleanly without re-processing earlier moves")

    # 3. Test mid-stream jump / catchup where internal board is behind stream
    tracker_lag = ChessStateTracker()
    # Simulate tracker having only processed move 1
    tracker_lag.push_uci("e2e4")
    assert tracker_lag.processed_ply == 1

    # Incoming gameState with 6 moves (jumped ahead by 5 moves)
    jump_state = {
        "type": "gameState",
        "moves": "e2e4 e7e5 g1f3 b8c6 f1c4 g8f6",
        "wtime": 160000,
        "btime": 170000,
    }
    event_jump = tracker_lag.parse_lichess_line(jump_state)
    assert isinstance(event_jump, ParsedMoveEvent)
    assert event_jump.ply == 6
    assert event_jump.san == "Nf6"
    assert event_jump.turn == "black"
    assert tracker_lag.processed_ply == 6
    assert tracker_lag.board.ply() == 6
    print("[PASS] ChessStateTracker successfully caught up internal board across multiple moves")

    # 4. Test Live Sync frame evaluation contract:
    # Historical moves (ply < target_start_ply) have evaluation and visual cues, but NO commentary.
    historical_eval = MoveEvaluation(
        ply=1,
        turn="white",
        played_uci="e2e4",
        played_san="e4",
        fen_after="rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1",
        eval_cp_after=25,
        eval_swing_cp=0,
        classification=MoveClassification.BOOK,
        win_prob_before=0.50,
        win_prob_after=0.50,
        win_prob_loss=0.0,
    )
    historical_frame = BroadcastFrame(
        event_type=BroadcastEventType.MOVE,
        game_id="gameTest123",
        ply=1,
        fen=historical_eval.fen_after,
        turn="white",
        move=event_5,
        evaluation=historical_eval,
        commentary=None,
        visual_cues=historical_eval.visual_cues,
    )
    assert historical_frame.commentary is None
    assert historical_frame.evaluation is not None
    assert historical_frame.evaluation.eval_cp_after == 25

    # Latest live move has evaluation AND commentary
    exchange = CommentaryExchange(
        ply=6,
        move_san="Nf6",
        turn_color="black",
        dynamic=SpeakingDynamic.PLAY_BY_PLAY,
        turns=[
            DialogueTurn(
                speaker=CommentatorRole.HOST,
                text="Knight to f6.",
                estimated_duration_seconds=1.0,
            )
        ],
    )
    live_frame = BroadcastFrame(
        event_type=BroadcastEventType.MOVE,
        game_id="gameTest123",
        ply=6,
        fen=tracker_lag.board.fen(),
        turn="black",
        move=event_jump,
        evaluation=historical_eval,
        commentary=exchange,
        visual_cues=historical_eval.visual_cues,
    )
    assert live_frame.commentary is not None
    assert len(live_frame.commentary.turns) == 1
    assert live_frame.commentary.turns[0].text == "Knight to f6."
    print("[PASS] Live sync frames verified: historical moves have engine eval without commentary; live move has commentary")


if __name__ == "__main__":
    test_pacing_buffer_formats()
    test_director_think_classification()
    test_director_dynamic_and_word_budget()
    test_director_instant_move_rapid()
    test_agent_fallback()
    test_pondering_context_and_prompt()
    test_post_pondered_move_budget()
    test_stream_paced_events_yields_pondering()
    test_agent_pondering_fallback()
    test_san_to_spoken_move()
    test_play_by_play_dynamic()
    test_pondering_cooldown_and_guards()
    test_temporal_phrasing_sanitizer()
    test_broadcast_pacing_buffer_zero_delay()
    test_initial_moves_parsing_and_status()
    test_opening_phase_prompt_and_director()
    test_long_audio_guard_and_play_by_play_continuity()
    test_live_sync_catchup_and_chess_state_tracker()
    print("\nALL VERIFICATION TESTS PASSED SUCCESSFULLY!")

