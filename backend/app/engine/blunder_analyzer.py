# backend/app/engine/blunder_analyzer.py

from typing import List, Optional, Tuple
import chess

from app.engine.schemas import (
    PositionAnalysis,
    EngineLine,
    HumanMotivation,
    RefutationType,
    BlunderDossier,
)

PIECE_VALUES = {
    chess.PAWN: 100,
    chess.KNIGHT: 300,
    chess.BISHOP: 300,
    chess.ROOK: 500,
    chess.QUEEN: 900,
    chess.KING: 20000,
}

class BlunderAnalyzer:
    """
    Analyzes failed moves to extract human cognitive traps, optical illusions,
    and the concrete refutation mechanism executed by the opponent.
    """

    @classmethod
    def analyze(
        cls,
        board_before: chess.Board,
        played_move: chess.Move,
        before_analysis: Optional[PositionAnalysis],
        after_analysis: PositionAnalysis,
        previous_move: Optional[chess.Move] = None,
        shallow_analysis: Optional[PositionAnalysis] = None,
    ) -> BlunderDossier:
        """
        Coordinates optical illusion detection, impulse categorization,
        and refutation extraction.
        """
        board_after = board_before.copy()
        board_after.push(played_move)

        # 1. Check Dual-Depth Discrepancy (Shallow vs Deep)
        shallow_favored = cls._check_shallow_trap(played_move, shallow_analysis)

        # 2. Identify Human Psychological Impulse
        motivation, motivation_desc = cls._detect_human_motivation(
            board_before=board_before,
            played_move=played_move,
            previous_move=previous_move,
        )

        # 3. Extract Refutation Dynamics from Opponent's Top Line
        refutation, refutation_desc, punishment_san = cls._detect_refutation(
            board_after=board_after,
            played_move=played_move,
            after_analysis=after_analysis,
        )

        # 4. Determine if this constitutes an "Optical Illusion / Natural Trap"
        # A move is a natural trap if shallow search liked it OR it matched strong human heuristics
        is_natural = (
            shallow_favored
            or motivation in (
                HumanMotivation.AUTOMATIC_RECAPTURE,
                HumanMotivation.GREEDY_MATERIAL_GRAB,
                HumanMotivation.ATTACKING_QUEEN_OR_ROOK,
                HumanMotivation.PSEUDO_FORK,
            )
        )

        missed_san = None
        if before_analysis and before_analysis.best_line:
            missed_san = before_analysis.best_line.primary_move_san

        # 5. Build Narrative Conditioning Hint for LLM Agent
        punishment_preview = " ".join(punishment_san[:3]) if punishment_san else "tactical refutation"
        if is_natural:
            narrative_hint = (
                f"Validate the player's instinct first ({motivation_desc}). "
                f"Then dramatically reveal the blind spot ({refutation_desc}). "
                f"Highlight the refutation: {punishment_preview}."
            )
        else:
            narrative_hint = (
                f"Explain the blunder directly. The move fails to {refutation_desc}. "
                f"Punishment line: {punishment_preview}."
            )

        return BlunderDossier(
            is_natural_trap=is_natural,
            shallow_favored=shallow_favored,
            human_motivation=motivation,
            motivation_explanation=motivation_desc,
            refutation_type=refutation,
            refutation_explanation=refutation_desc,
            punishment_moves_san=punishment_san,
            missed_best_san=missed_san,
            narrative_prompt_hint=narrative_hint,
        )

    @staticmethod
    def _check_shallow_trap(
        played_move: chess.Move,
        shallow_analysis: Optional[PositionAnalysis],
    ) -> bool:
        """
        Returns True if the move evaluated well at low depth (depth 3-4),
        meaning it looked good on a 1-2 ply calculation horizon.
        """
        if not shallow_analysis or not shallow_analysis.lines:
            return False

        played_uci = played_move.uci()
        for line in shallow_analysis.lines[:2]:
            if line.primary_move_uci == played_uci:
                # If shallow evaluation thought it was winning/equal (>= -50 cp from player's POV)
                if line.score_cp is not None and line.score_cp >= -50:
                    return True
        return False

    @staticmethod
    def _detect_human_motivation(
        board_before: chess.Board,
        played_move: chess.Move,
        previous_move: Optional[chess.Move],
    ) -> Tuple[HumanMotivation, str]:
        """
        Examines board geometry to identify common human shortcuts.
        """
        to_sq = played_move.to_square
        moving_piece = board_before.piece_at(played_move.from_square)
        if not moving_piece:
            return HumanMotivation.TACTICAL_BLIND_SPOT, "An unclear tactical attempt"

        # A. Automatic Recapture Impulse
        if previous_move and to_sq == previous_move.to_square:
            return (
                HumanMotivation.AUTOMATIC_RECAPTURE,
                "an instinctive, automatic recapture on the contested square"
            )

        # B. Greedy Material Grab (Poisoned piece/pawn)
        if board_before.is_capture(played_move):
            dest_piece = board_before.piece_at(to_sq)
            piece_name = chess.piece_name(dest_piece.piece_type) if dest_piece else "pawn"
            return (
                HumanMotivation.GREEDY_MATERIAL_GRAB,
                f"an irresistible grab of what appeared to be a free {piece_name}"
            )

        # C. Aggressive Check
        board_after = board_before.copy()
        board_after.push(played_move)
        if board_after.is_check():
            return (
                HumanMotivation.AGGRESSIVE_CHECK,
                "giving a tempting check to put pressure on the enemy king"
            )

        # D. Attacking Queen or Rook with Tempo
        opp_color = not board_before.turn
        attacked_squares = board_after.attacks(to_sq)
        for sq in attacked_squares:
            piece = board_after.piece_at(sq)
            if piece and piece.color == opp_color:
                if piece.piece_type in (chess.QUEEN, chess.ROOK):
                    target_name = chess.piece_name(piece.piece_type)
                    return (
                        HumanMotivation.ATTACKING_QUEEN_OR_ROOK,
                        f"attacking the enemy {target_name} to win a tempo"
                    )

        # E. Pseudo-Fork Attempt
        opp_targets = [
            sq for sq in attacked_squares
            if board_after.piece_at(sq) and board_after.piece_at(sq).color == opp_color
        ]
        if len(opp_targets) >= 2 and moving_piece.piece_type in (chess.KNIGHT, chess.PAWN):
            return (
                HumanMotivation.PSEUDO_FORK,
                "jumping into what looked like a textbook double-attack fork"
            )

        # F. Natural Development / King Safety
        if board_before.is_castling(played_move):
            return (
                HumanMotivation.NATURAL_DEVELOPMENT,
                "tucking the king into castled safety without noticing tactical weaknesses"
            )

        return (
            HumanMotivation.TACTICAL_BLIND_SPOT,
            "a natural-looking continuation with a hidden tactical oversight"
        )

    @staticmethod
    def _detect_refutation(
        board_after: chess.Board,
        played_move: chess.Move,
        after_analysis: PositionAnalysis,
    ) -> Tuple[RefutationType, str, List[str]]:
        """
        Parses the opponent's winning line from Stockfish to classify why the blunder fails.
        """
        best_line = after_analysis.best_line
        if not best_line or not best_line.uci_moves:
            return RefutationType.TACTICAL_PUNISHMENT, "a standard tactical refutation", []

        punishment_san = best_line.san_moves[:4]
        opp_first_uci = best_line.uci_moves[0]
        opp_first_move = chess.Move.from_uci(opp_first_uci)

        # A. Counter-Attack Threatening Checkmate
        if best_line.mate_in is not None:
            return (
                RefutationType.CHECKMATE_COUNTER_ATTACK,
                "a lethal counter-attack terminating in a forced checkmate sequence",
                punishment_san,
            )

        # B. Zwischenzug (In-between move)
        # Opponent delivers check first rather than recapturing or responding passively
        if board_after.gives_check(opp_first_move):
            return (
                RefutationType.ZWISCHENZUG_CHECK,
                "a devastating intermediate check (zwischenzug) that shatters all defensive coordination",
                punishment_san,
            )

        # Opponent ignores the player's threat/recapture and counter-attacks an equal/higher piece
        if not board_after.is_capture(opp_first_move):
            # Check if opponent makes a quiet defensive resource or king escape
            moving_piece = board_after.piece_at(opp_first_move.from_square)
            if moving_piece and moving_piece.piece_type == chess.KING:
                return (
                    RefutationType.DEFENSIVE_RESOURCE,
                    "a simple, quiet king escape that completely neutralizes the attack",
                    punishment_san,
                )

            # Check if opponent attacks a major piece
            board_after_opp = board_after.copy()
            board_after_opp.push(opp_first_move)
            player_color = not board_after.turn
            attacks_from_reply = board_after_opp.attacks(opp_first_move.to_square)
            
            for target_sq in attacks_from_reply:
                piece = board_after_opp.piece_at(target_sq)
                if piece and piece.color == player_color and piece.piece_type in (chess.QUEEN, chess.ROOK):
                    return (
                        RefutationType.ZWISCHENZUG_COUNTER_THREAT,
                        "an in-between counter-attack on a high-value piece that ignores the initial threat",
                        punishment_san,
                    )

            # Quiet positional refutation
            return (
                RefutationType.QUIET_REFUTATION,
                "a quiet move that leaves the moving piece completely stranded",
                punishment_san,
            )

        # C. Default Tactical Punishment
        return (
            RefutationType.TACTICAL_PUNISHMENT,
            "a direct tactical sequence that wins decisive material",
            punishment_san,
        )