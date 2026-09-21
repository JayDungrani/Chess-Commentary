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
)
from app.commentary.prompts import build_commentary_prompt
from app.commentary.agent import CommentaryAgent


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
    assert "5-10 words" in context.target_word_range
    print(f"[PASS] Instant move produced target word budget '{context.target_word_range}'")

    prompt = build_commentary_prompt(context)
    assert "INSTANT MOVE" in prompt
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
    assert cleaned_2 == "Greedy. Missed knight to e4. White can play a4."

    raw_text_3 = "White now strikes with bishop to c4."
    cleaned_3 = CommentaryAgent._sanitize_temporal_phrasing(raw_text_3, opponent_color="White")
    assert cleaned_3 == "White can now strike with bishop to c4."

    # Active player who actually moved should NOT be rewritten
    active_player_text = "Black plays bishop to g7."
    kept_active = CommentaryAgent._sanitize_temporal_phrasing(active_player_text, opponent_color="White")
    assert kept_active == "Black plays bishop to g7."
    print("[PASS] Temporal phrasing correctly converts false present tense for upcoming opponent to modal 'can play'!")


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
    print("\nALL VERIFICATION TESTS PASSED SUCCESSFULLY!")
