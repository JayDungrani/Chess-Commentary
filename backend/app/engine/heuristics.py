# backend/app/engine/heuristics.py

import math
from typing import Optional, List, Tuple
import chess

from app.config import settings
from app.engine.schemas import MoveClassification, EngineLine, PositionAnalysis, VisualCue

# Centipawn piece valuations
PIECE_VALUES = {
    chess.PAWN: 100,
    chess.KNIGHT: 300,
    chess.BISHOP: 300,
    chess.ROOK: 500,
    chess.QUEEN: 900,
    chess.KING: 20000,
}


def cp_to_win_prob(
    score_cp: Optional[int],
    mate_in: Optional[int] = None,
    scaling: float = settings.win_prob_scaling,
) -> float:
    if mate_in is not None:
        if mate_in > 0:
            return max(0.99, 1.0 - (mate_in * 0.001))
        elif mate_in < 0:
            return min(0.01, abs(mate_in) * 0.001)
        else:
            return 0.5

    if score_cp is None:
        return 0.5

    clamped_cp = max(-3000, min(3000, score_cp))
    prob = 1.0 / (1.0 + math.pow(10.0, -clamped_cp / scaling))
    return round(prob, 4)


def player_win_prob(white_win_prob: float, turn: str) -> float:
    return white_win_prob if turn.lower() == "white" else round(1.0 - white_win_prob, 4)


def calculate_player_loss(
    before_analysis: Optional[PositionAnalysis],
    after_analysis: PositionAnalysis,
    turn: str,
) -> Tuple[int, float]:
    if not before_analysis or not before_analysis.best_line:
        return 0, 0.0

    prob_before_white = before_analysis.win_probability
    prob_before_player = player_win_prob(prob_before_white, turn)

    prob_after_white = after_analysis.win_probability
    prob_after_player = player_win_prob(prob_after_white, turn)

    win_prob_loss = max(0.0, round(prob_before_player - prob_after_player, 4))

    def normalize_cp(cp: Optional[int], mate: Optional[int]) -> int:
        if mate is not None:
            return 10000 - (mate * 10) if mate > 0 else -10000 - (mate * 10)
        return cp if cp is not None else 0

    cp_before_white = normalize_cp(before_analysis.score_cp, before_analysis.mate_in)
    cp_after_white = normalize_cp(after_analysis.score_cp, after_analysis.mate_in)

    cp_before_player = cp_before_white if turn.lower() == "white" else -cp_before_white
    cp_after_player = cp_after_white if turn.lower() == "white" else -cp_after_white

    cp_loss = max(0, cp_before_player - cp_after_player)
    return cp_loss, win_prob_loss


def get_sacrifice_net_loss(board_before: chess.Board, move: chess.Move) -> int:
    moving_piece = board_before.piece_at(move.from_square)
    if not moving_piece or moving_piece.piece_type == chess.PAWN:
        return 0

    moving_val = PIECE_VALUES.get(moving_piece.piece_type, 0)
    dest_piece = board_before.piece_at(move.to_square)
    captured_val = PIECE_VALUES.get(dest_piece.piece_type, 0) if dest_piece else 0

    board_after = board_before.copy()
    board_after.push(move)

    opp_captures = [
        m for m in board_after.legal_moves
        if m.to_square == move.to_square
    ]
    if not opp_captures:
        return 0

    def get_attacker_val(m: chess.Move) -> int:
        p = board_after.piece_at(m.from_square)
        return PIECE_VALUES.get(p.piece_type, 0) if p else 0

    opp_captures.sort(key=get_attacker_val)
    cheapest_capture = opp_captures[0]
    cheapest_attacker_val = get_attacker_val(cheapest_capture)

    board_after_opp = board_after.copy()
    board_after_opp.push(cheapest_capture)

    player_recaptures = [
        m for m in board_after_opp.legal_moves
        if m.to_square == move.to_square
    ]

    if not player_recaptures:
        return max(0, moving_val - captured_val)

    net_loss = moving_val - (captured_val + cheapest_attacker_val)
    return max(0, net_loss)


def left_piece_hanging(board_before: chess.Board, move: chess.Move) -> int:
    board_after = board_before.copy()
    board_after.push(move)
    opponent = board_after.turn
    player = not opponent

    for sq, piece in board_after.piece_map().items():
        if piece.color != player or piece.piece_type in (chess.PAWN, chess.KING):
            continue
        if sq == move.to_square:
            continue

        piece_val = PIECE_VALUES[piece.piece_type]
        opp_captures = [m for m in board_after.legal_moves if m.to_square == sq]
        if not opp_captures:
            continue

        cheapest_opp_val = min(
            PIECE_VALUES.get(board_after.piece_at(m.from_square).piece_type, 0)
            for m in opp_captures
        )

        player_defenders = board_after.attackers(player, sq)
        if len(player_defenders) == 0 and piece_val >= 300:
            return piece_val
        elif cheapest_opp_val < piece_val:
            net = piece_val - cheapest_opp_val
            if net >= 200:
                return net

    return 0


def is_piece_sacrifice(board_before: chess.Board, move: chess.Move) -> bool:
    if get_sacrifice_net_loss(board_before, move) >= 180:
        return True
    if left_piece_hanging(board_before, move) >= 200:
        return True
    return False


def is_move_sacrifice_or_brilliant(
    played_uci: str,
    before_analysis: PositionAnalysis,
    loss_cp: int,
) -> bool:
    if loss_cp > 5:
        return False

    best_line = before_analysis.best_line
    if not best_line or best_line.primary_move_uci != played_uci:
        return False

    board_before = chess.Board(before_analysis.fen)
    turn = "white" if board_before.turn == chess.WHITE else "black"
    player_prob_before = player_win_prob(before_analysis.win_probability, turn)

    if not (0.40 <= player_prob_before <= 0.82):
        return False

    player_prob_after = player_win_prob(best_line.win_probability, turn)
    if player_prob_after < 0.55:
        return False

    if len(before_analysis.lines) > 1:
        second_line = before_analysis.lines[1]
        line1_player_prob = player_win_prob(best_line.win_probability, turn)
        line2_player_prob = player_win_prob(second_line.win_probability, turn)
        prob_gap = line1_player_prob - line2_player_prob

        cp_gap = 0
        if best_line.score_cp is not None and second_line.score_cp is not None:
            cp1 = best_line.score_cp if turn == "white" else -best_line.score_cp
            cp2 = second_line.score_cp if turn == "white" else -second_line.score_cp
            cp_gap = cp1 - cp2

        if prob_gap < 0.10 and cp_gap < 100:
            return False

    try:
        move = chess.Move.from_uci(played_uci)
        if move not in board_before.legal_moves:
            return False
    except ValueError:
        return False

    return is_piece_sacrifice(board_before, move)


def classify_move(
    played_uci: str,
    before_analysis: Optional[PositionAnalysis],
    loss_cp: int,
    win_prob_loss: float,
    is_book: bool = False,
) -> MoveClassification:
    if is_book:
        return MoveClassification.BOOK

    if not before_analysis:
        return MoveClassification.GOOD

    if loss_cp >= settings.blunder_threshold_cp or win_prob_loss >= 0.20:
        return MoveClassification.BLUNDER
    if loss_cp >= settings.mistake_threshold_cp or win_prob_loss >= 0.10:
        return MoveClassification.MISTAKE
    if loss_cp >= settings.inaccuracy_threshold_cp or win_prob_loss >= 0.05:
        return MoveClassification.INACCURACY

    if is_move_sacrifice_or_brilliant(played_uci, before_analysis, loss_cp):
        return MoveClassification.BRILLIANT

    if loss_cp <= 10:
        return MoveClassification.BEST
    elif loss_cp <= 25:
        return MoveClassification.EXCELLENT

    return MoveClassification.GOOD


def generate_visual_cues(
    played_uci: str,
    classification: MoveClassification,
    should_have_played: Optional[EngineLine],
    candidate_responses: List[EngineLine],
) -> VisualCue:
    arrows: List[List[str]] = []
    highlights: List[str] = []

    if len(played_uci) >= 4:
        from_sq = played_uci[:2]
        to_sq = played_uci[2:4]
        if classification == MoveClassification.BLUNDER:
            arrows.append([from_sq, to_sq, "red"])
            highlights.append(to_sq)
        elif classification == MoveClassification.MISTAKE:
            arrows.append([from_sq, to_sq, "orange"])
        elif classification == MoveClassification.BRILLIANT:
            arrows.append([from_sq, to_sq, "cyan"])

    # Green arrow is displayed only if the move was an inaccuracy, mistake, or blunder
    is_suboptimal = classification in (
        MoveClassification.BLUNDER,
        MoveClassification.MISTAKE,
        MoveClassification.INACCURACY,
    )
    if is_suboptimal and should_have_played and should_have_played.primary_move_uci:
        best_uci = should_have_played.primary_move_uci
        arrows.append([best_uci[:2], best_uci[2:4], "green"])

    # Blue prospective arrow for the top candidate reply of the next player
    if candidate_responses and candidate_responses[0].primary_move_uci:
        next_uci = candidate_responses[0].primary_move_uci
        arrows.append([next_uci[:2], next_uci[2:4], "blue"])

    return VisualCue(arrows=arrows, highlights=highlights)