# backend/app/engine/analyzer.py

import logging
from typing import Optional
import chess

from app.config import settings
from app.engine.schemas import (
    MoveEvaluation,
    PositionAnalysis,
    MoveClassification,
    EngineLine,
    BlunderDossier,
)
from app.engine.heuristics import (
    calculate_player_loss,
    classify_move,
    generate_visual_cues,
)
from app.engine.blunder_analyzer import BlunderAnalyzer
from app.engine.stockfish_pool import StockfishEngine
from app.engine.opening_book import GameOpeningTracker
from app.lichess.pgn_parser import ParsedMoveEvent

logger = logging.getLogger(__name__)


class MoveAnalyzer:
    """
    Coordinates chess engine evaluation and opening tracking across successive plies.
    Maintains retrospective analysis (Ply N-1) to evaluate the quality of the
    move played on Ply N, tracks opening theory via Polyglot books, detects
    tactical blunders/illusions, and identifies prospective candidate responses.
    """

    def __init__(
        self,
        engine: Optional[StockfishEngine] = None,
        opening_tracker: Optional[GameOpeningTracker] = None,
        shallow_depth: int = 4,
        shallow_movetime_ms: int = 40,
    ):
        self.engine = engine or StockfishEngine()
        self.opening_tracker = opening_tracker or GameOpeningTracker()
        self.shallow_depth = shallow_depth
        self.shallow_movetime_ms = shallow_movetime_ms

        # State tracking across plies
        self.previous_analysis: Optional[PositionAnalysis] = None
        self.board: chess.Board = chess.Board()
        self.previous_move: Optional[chess.Move] = None

    def reset(self, initial_fen: Optional[str] = None) -> None:
        """Resets board state, analysis cache, and opening tracker for a new game."""
        self.board = chess.Board(initial_fen) if initial_fen else chess.Board()
        self.previous_analysis = None
        self.previous_move = None
        self.opening_tracker.reset()

    async def evaluate_move(self, event: ParsedMoveEvent) -> MoveEvaluation:
        """
        Processes a parsed move event:
        1. Checks opening book membership and tracks novelty transitions.
        2. Analyzes post-move position with Stockfish (MultiPV=3).
        3. Computes retrospective eval swings and move classifications.
        4. Bypasses blunder checks if in book; triggers shallow pass if blunder occurs.
        5. Packages visual cues, prospective opponent lines, and opening metadata.
        """
        board_before = self.board.copy()
        current_move = chess.Move.from_uci(event.uci)

        # 1. Opening Book & ECO Classification Check
        is_book, left_book_now, eco_code, opening_name = self.opening_tracker.process_move(
            board_before=board_before,
            move=current_move,
            move_san=event.san,
            ply=event.ply,
        )

        # Synchronize internal board to post-move position
        if current_move in self.board.legal_moves:
            self.board.push(current_move)
        else:
            logger.warning(
                f"Move {event.uci} illegal on internal board. Resyncing to FEN: {event.fen}"
            )
            self.board.set_fen(event.fen)

        # 2. Deep Stockfish Analysis on post-move position
        current_analysis = await self.engine.analyze_position(event.fen)

        # 3. Retrospective Metrics & Classification
        loss_cp = 0
        win_prob_loss = 0.0
        classification = MoveClassification.BOOK if is_book else MoveClassification.GOOD
        should_have_played: Optional[EngineLine] = None
        blunder_dossier: Optional[BlunderDossier] = None

        win_prob_before = (
            self.previous_analysis.win_probability
            if self.previous_analysis
            else 0.5
        )
        win_prob_after = current_analysis.win_probability

        if not is_book and self.previous_analysis:
            loss_cp, win_prob_loss = calculate_player_loss(
                before_analysis=self.previous_analysis,
                after_analysis=current_analysis,
                turn=event.turn,
            )

            classification = classify_move(
                played_uci=event.uci,
                before_analysis=self.previous_analysis,
                loss_cp=loss_cp,
                win_prob_loss=win_prob_loss,
                is_book=False,
            )

            best_prev_line = self.previous_analysis.best_line
            if best_prev_line and best_prev_line.primary_move_uci != event.uci:
                should_have_played = best_prev_line

            # 4. Blunder & Optical Illusion Inspection
            is_mistake_or_blunder = classification in (
                MoveClassification.BLUNDER,
                MoveClassification.MISTAKE,
            )

            if is_mistake_or_blunder:
                shallow_analysis = None
                try:
                    shallow_analysis = await self.engine.analyze_position(
                        fen=board_before.fen(),
                        depth=self.shallow_depth,
                        movetime_ms=self.shallow_movetime_ms,
                    )
                except Exception as exc:
                    logger.warning(f"Shallow blunder pass failed: {exc}")

                blunder_dossier = BlunderAnalyzer.analyze(
                    board_before=board_before,
                    played_move=current_move,
                    before_analysis=self.previous_analysis,
                    after_analysis=current_analysis,
                    previous_move=self.previous_move,
                    shallow_analysis=shallow_analysis,
                )

        is_blunder_flag = classification == MoveClassification.BLUNDER

        # 5. Generate Visual Cues
        visual_cues = generate_visual_cues(
            played_uci=event.uci,
            classification=classification,
            should_have_played=should_have_played,
            candidate_responses=current_analysis.lines,
        )

        # 6. Assemble Enriched MoveEvaluation Contract
        evaluation = MoveEvaluation(
            ply=event.ply,
            turn=event.turn,
            played_san=event.san,
            played_uci=event.uci,
            fen_after=event.fen,
            is_book=is_book,
            left_book_now=left_book_now,
            eco_code=eco_code,
            opening_name=opening_name,
            eval_cp_after=current_analysis.score_cp,
            mate_in_after=current_analysis.mate_in,
            eval_swing_cp=-loss_cp,
            win_prob_before=win_prob_before,
            win_prob_after=win_prob_after,
            win_prob_loss=win_prob_loss,
            classification=classification,
            is_blunder=is_blunder_flag,
            blunder_dossier=blunder_dossier,
            should_have_played=should_have_played,
            candidate_responses=current_analysis.lines,
            visual_cues=visual_cues,
        )

        # 7. Cycle State Cache
        self.previous_analysis = current_analysis
        self.previous_move = current_move

        return evaluation