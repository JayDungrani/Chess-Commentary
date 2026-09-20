# backend/app/engine/schemas.py

from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field


class MoveClassification(str, Enum):
    """Evaluation categories based on centipawn and win probability loss."""
    BRILLIANT = "BRILLIANT"
    BEST = "BEST"
    EXCELLENT = "EXCELLENT"
    GOOD = "GOOD"
    INACCURACY = "INACCURACY"
    NORMAL = "NORMAL"
    MISTAKE = "MISTAKE"
    BLUNDER = "BLUNDER"
    BOOK = "BOOK"


class HumanMotivation(str, Enum):
    """The psychological or tactical impulse behind a natural-looking move."""
    AUTOMATIC_RECAPTURE = "AUTOMATIC_RECAPTURE"
    GREEDY_MATERIAL_GRAB = "GREEDY_MATERIAL_GRAB"
    ATTACKING_QUEEN_OR_ROOK = "ATTACKING_QUEEN_OR_ROOK"
    PSEUDO_FORK = "PSEUDO_FORK"
    AGGRESSIVE_CHECK = "AGGRESSIVE_CHECK"
    NATURAL_DEVELOPMENT = "NATURAL_DEVELOPMENT"
    TACTICAL_BLIND_SPOT = "TACTICAL_BLIND_SPOT"


class RefutationType(str, Enum):
    """The tactical or positional mechanism that punishes the blunder."""
    ZWISCHENZUG_CHECK = "ZWISCHENZUG_CHECK"
    ZWISCHENZUG_COUNTER_THREAT = "ZWISCHENZUG_COUNTER_THREAT"
    QUIET_REFUTATION = "QUIET_REFUTATION"
    CHECKMATE_COUNTER_ATTACK = "CHECKMATE_COUNTER_ATTACK"
    DEFENSIVE_RESOURCE = "DEFENSIVE_RESOURCE"
    OVERLOADED_DEFENDER = "OVERLOADED_DEFENDER"
    TACTICAL_PUNISHMENT = "TACTICAL_PUNISHMENT"


class BlunderDossier(BaseModel):
    """
    Detailed psychological breakdown of a mistake or blunder,
    used to prime the GM Commentator agent with an empathetic narrative.
    """
    is_natural_trap: bool = Field(
        ...,
        description="True if the move appears intuitive/tempting at shallow depth or follows human heuristics"
    )
    shallow_favored: bool = Field(
        default=False,
        description="True if shallow search (depth 3-4) evaluated this move significantly higher than deep search"
    )
    human_motivation: HumanMotivation = Field(
        ...,
        description="The instinctive goal the player thought they were accomplishing"
    )
    motivation_explanation: str = Field(
        ...,
        description="Plain-English summary of the move's visual temptation"
    )
    refutation_type: RefutationType = Field(
        ...,
        description="The tactical reason the move fails"
    )
    refutation_explanation: str = Field(
        ...,
        description="Plain-English explanation of the opponent's counter-punch"
    )
    punishment_moves_san: List[str] = Field(
        default_factory=list,
        description="The immediate tactical refutation line in SAN (first 2-4 moves)"
    )
    missed_best_san: Optional[str] = Field(
        default=None,
        description="The sound alternative move the player missed"
    )
    narrative_prompt_hint: str = Field(
        ...,
        description="Pre-formatted directive for LLM system prompt conditioning"
    )


class EngineLine(BaseModel):
    """Represents a single Stockfish Principal Variation (PV) candidate line."""
    rank: int = Field(..., description="MultiPV rank index (1-based, 1 = best line)")
    score_cp: Optional[int] = Field(
        default=None,
        description="Centipawn evaluation from White's perspective (+100 = +1.0 pawn)"
    )
    mate_in: Optional[int] = Field(
        default=None,
        description="Moves until mate from White's perspective (+3 = White mates in 3, -2 = Black mates in 2)"
    )
    win_probability: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Estimated win probability for White (0.0 to 1.0)"
    )
    uci_moves: List[str] = Field(default_factory=list, description="Sequence of moves in UCI notation")
    san_moves: List[str] = Field(default_factory=list, description="Sequence of moves in SAN notation")
    depth: int = Field(..., description="Engine search depth reached for this line")

    @property
    def primary_move_san(self) -> Optional[str]:
        return self.san_moves[0] if self.san_moves else None

    @property
    def primary_move_uci(self) -> Optional[str]:
        return self.uci_moves[0] if self.uci_moves else None


class PositionAnalysis(BaseModel):
    """Snapshot analysis of a board position (FEN)."""
    fen: str = Field(..., description="Analyzed FEN string")
    depth: int = Field(..., description="Target or achieved search depth")
    lines: List[EngineLine] = Field(
        default_factory=list,
        description="Top MultiPV candidate lines sorted by strength"
    )
    score_cp: Optional[int] = Field(
        default=None,
        description="Best line centipawn evaluation from White's perspective"
    )
    mate_in: Optional[int] = Field(
        default=None,
        description="Best line forced mate distance from White's perspective"
    )
    win_probability: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Calculated win probability for White on the top line"
    )

    @property
    def best_line(self) -> Optional[EngineLine]:
        return self.lines[0] if self.lines else None


class VisualCue(BaseModel):
    """Visual arrows and square highlights sent to the frontend overlay."""
    arrows: List[List[str]] = Field(
        default_factory=list,
        description="List of arrows as [from_square, to_square, color] e.g. [['e2', 'e4', 'green']]"
    )
    highlights: List[str] = Field(
        default_factory=list,
        description="List of square coordinate strings e.g. ['f7', 'e8']"
    )


class MoveEvaluation(BaseModel):
    """
    Enriched evaluation payload connecting move context, tactical shifts,
    retrospective alternatives, prospective candidate responses, and opening theory.
    """
    ply: int = Field(..., description="Ply counter of the played move")
    turn: str = Field(..., description="'white' or 'black'")
    played_san: str = Field(..., description="Move executed on the board in SAN (e.g. 'Bb4+')")
    played_uci: str = Field(..., description="Move executed on the board in UCI (e.g. 'f8b4')")
    fen_after: str = Field(..., description="Board FEN resulting from this move")

    # Opening Book & ECO Context
    is_book: bool = Field(
        default=False,
        description="True if the move is an established theoretical opening move from the book"
    )
    left_book_now: bool = Field(
        default=False,
        description="True if this move marked the transition out of book theory (novelty point)"
    )
    eco_code: Optional[str] = Field(
        default=None,
        description="Identified ECO code (e.g. 'C65')"
    )
    opening_name: Optional[str] = Field(
        default=None,
        description="Identified opening or variation name (e.g. 'Ruy Lopez, Berlin Defense')"
    )

    # Quantitative Shifts
    eval_cp_after: Optional[int] = Field(default=None, description="Score after move (White perspective)")
    mate_in_after: Optional[int] = Field(default=None, description="Mate score after move (White perspective)")
    eval_swing_cp: int = Field(
        ...,
        description="Centipawn loss experienced by the moving player (negative = loss)"
    )
    win_prob_before: float = Field(..., ge=0.0, le=1.0)
    win_prob_after: float = Field(..., ge=0.0, le=1.0)
    win_prob_loss: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Win percentage drop for the player who just moved (0.0 to 1.0)"
    )

    # Classification & Flags
    classification: MoveClassification = Field(..., description="Move quality category")
    is_blunder: bool = Field(default=False, description="Flag for priority audio interrupt")

    # Psychological Blunder Dossier (populated only on mistakes/blunders)
    blunder_dossier: Optional[BlunderDossier] = Field(
        default=None,
        description="Human impulse breakdown and refutation details if move was a blunder/mistake"
    )

    # Retrospective (What the player should have played)
    should_have_played: Optional[EngineLine] = Field(
        default=None,
        description="The top PV line the player missed from the previous position"
    )

    # Prospective (What the opponent should play next)
    candidate_responses: List[EngineLine] = Field(
        default_factory=list,
        description="Stockfish top candidate lines for the next player to move"
    )

    # Frontend Visuals
    visual_cues: VisualCue = Field(default_factory=VisualCue)