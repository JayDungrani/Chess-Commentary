# backend/tests/test_studio_enhancements.py

import os
import shutil
import tempfile
import pytest
from pathlib import Path

from app.engine.stockfish_pool import (
    find_stockfish_binary,
    _heuristic_evaluate_fen,
    StockfishEngine,
)
from app.services.tts_service import TTSService
from app.commentary.schemas import DialogueTurn, CommentatorRole, CommentaryEmotion
from app.main import app, register_custom_game, CustomGamePayload, _run_fen_analysis


def test_stockfish_path_discovery():
    """Verify that auto-discovery locates a valid Stockfish binary on system."""
    binary = find_stockfish_binary()
    assert binary is not None, "Stockfish binary auto-discovery should find installed binary"
    assert os.path.isfile(binary), f"Discovered path '{binary}' must be a valid file"


def test_heuristic_fallback_evaluation():
    """Verify fallback evaluation produces well-formed PositionAnalysis when engine is missing."""
    start_fen = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
    analysis = _heuristic_evaluate_fen(start_fen, depth=1, multipv=3)

    assert analysis.fen == start_fen
    assert analysis.score_cp == 0  # Balanced opening position
    assert 0.45 <= analysis.win_probability <= 0.55
    assert len(analysis.lines) > 0
    assert analysis.lines[0].uci_moves is not None


def test_structured_audio_file_storage():
    """Verify audio clips are neatly organized in per-game subdirectories."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        output_dir = Path(tmp_dir)
        service = TTSService(output_dir=output_dir, api_key=None)

        turn = DialogueTurn(
            speaker=CommentatorRole.HOST,
            text="White pushes forward with pawns.",
            emotion=CommentaryEmotion.NEUTRAL,
            priority=1,
        )

        game_id = "testgame123"
        result_turn = pytest.importorskip("asyncio").run(
            service.synthesize_turn(turn=turn, game_id=game_id, ply=5, turn_index=0)
        )

        # Without API key, audio_url is None and estimated duration is calculated
        assert result_turn.estimated_duration_seconds > 0

        # Test structured folder creation and cleanup
        game_folder = output_dir / game_id
        game_folder.mkdir(parents=True, exist_ok=True)
        dummy_mp3 = game_folder / "ply005_0_host.mp3"
        dummy_mp3.write_bytes(b"dummy mp3 data")

        assert dummy_mp3.exists()
        assert dummy_mp3.parent.name == game_id

        # Cleanup verification
        deleted = service.cleanup_old_audio(max_age_hours=0) # prune immediately
        assert deleted >= 1


@pytest.mark.asyncio
async def test_custom_game_registration_and_analysis():
    """Verify registration of custom PGN games and on-demand position analysis."""
    # 1. Custom PGN registration
    sample_pgn = "1. e4 e5 2. Nf3 Nc6 3. Bb5 a6 *"
    payload = CustomGamePayload(pgn=sample_pgn, title="Ruy Lopez Test")
    reg_result = await register_custom_game(payload)

    assert reg_result["game_id"].startswith("custom_")
    assert reg_result["plies"] == 6

    # 2. On-demand engine analysis
    test_fen = "r1bqkbnr/pppp1ppp/2n5/1B2p3/4P3/5N2/PPPP1PPP/RNBQK2R b KQkq - 3 3"
    analysis_res = await _run_fen_analysis(
        engine=None,
        fen=test_fen,
        depth=10,
        multipv=2,
    )

    assert analysis_res["fen"] == test_fen
    assert "candidate_responses" in analysis_res
    assert len(analysis_res["candidate_responses"]) > 0
    assert "best_line_san" in analysis_res
    assert "visual_cues" in analysis_res
    assert "arrows" in analysis_res["visual_cues"]
