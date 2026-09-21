# backend/app/commentary/schemas.py

import time
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field

from app.engine.schemas import MoveEvaluation


class CommentatorRole(str, Enum):
    """Broadcast roles for the dual-commentator presentation."""
    HOST = "HOST"        # Play-by-play announcer: energetic, concise, tracks clocks and board flow
    ANALYST = "ANALYST"  # Grandmaster analyst: tactical insight, psychological empathy, refutations


class CommentaryEmotion(str, Enum):
    """Emotional delivery tags consumed by TTS synthesis and visual broadcast widgets."""
    NEUTRAL = "neutral"
    EXCITED = "excited"
    SHOCKED = "shocked"
    ANALYTICAL = "analytical"
    TENSE = "tense"
    HUMOROUS = "humorous"


class SpeakingDynamic(str, Enum):
    """Determines which commentator speaks and the format of the exchange."""
    SOLO_HOST = "SOLO_HOST"        # Host reports book move, clock scramble, or quick recap
    SOLO_ANALYST = "SOLO_ANALYST"  # GM explains positional nuance or quiet maneuvers
    BANTER = "BANTER"              # Host tees up a question or reacts -> GM explains the position
    SILENCE = "SILENCE"            # Deliberate pause on trivial moves to allow audio buffer draining
    PLAY_BY_PLAY = "PLAY_BY_PLAY"  # Rapid play-by-play move call (e.g., 'Bishop to e6.', 'Castles.')


class ThinkCategory(str, Enum):
    """Categorization of how long the player took to calculate their move."""
    INSTANT = "instant"        # Blitzed out, premove, or automatic (< threshold)
    NORMAL = "normal"          # Standard comfortable think
    THINK = "think"            # Noticeable pause / calculation
    DEEP_THINK = "deep_think"  # Deep tank / major time investment


class CommentaryPriority(int, Enum):
    """Priority thresholds for audio queue dispatch and playback interruption."""
    BACKGROUND = 1    # Routine book moves and quiet trades
    NORMAL = 2        # Standard developing or equalizing moves
    TACTICAL = 4      # Inaccuracies, minor threats, tempo moves
    TIME_TROUBLE = 6  # Severe clock scrambles (< 30 seconds)
    HIGH_DRAMA = 8    # Serious mistakes, missed wins, queen counter-attacks
    INTERRUPT = 10    # Catastrophic blunders, brilliant sacrifices, checkmates


class DialogueTurn(BaseModel):
    """A single utterance by one commentator."""
    speaker: CommentatorRole = Field(..., description="Active speaker for this turn")
    text: str = Field(
        ...,
        description="Spoken dialogue script optimized for natural TTS narration (no raw algebraic trees)"
    )
    emotion: CommentaryEmotion = Field(
        default=CommentaryEmotion.NEUTRAL,
        description="Emotional posture for speech tone modulation"
    )
    priority: int = Field(
        default=CommentaryPriority.NORMAL.value,
        ge=1,
        le=10,
        description="Queue scheduling priority (1-10)"
    )
    estimated_duration_seconds: Optional[float] = Field(
        default=None,
        description="Estimated spoken audio duration based on syllable or word count"
    )
    audio_url: Optional[str] = Field(
        default=None,
        description="Path or URL to generated speech file once processed by TTS"
    )


class LLMCommentaryOutput(BaseModel):
    """Target schema for structured LLM function calling / JSON output."""
    turns: List[DialogueTurn] = Field(
        default_factory=list,
        description="Sequence of spoken turns between the Host and Analyst for the current move"
    )


class CommentaryExchange(BaseModel):
    """Full conversational unit generated for a single ply."""
    ply: int = Field(..., description="Move ply number matching MoveEvaluation")
    move_san: str = Field(..., description="Move notation (e.g., 'Bxh7+')")
    turn_color: str = Field(..., description="'white' or 'black'")
    dynamic: SpeakingDynamic = Field(..., description="The chosen communication format")
    priority: int = Field(
        default=CommentaryPriority.NORMAL.value,
        ge=1,
        le=10,
        description="Highest priority among dialogue turns"
    )
    turns: List[DialogueTurn] = Field(
        default_factory=list,
        description="Chronological dialogue turns in this exchange"
    )
    is_interrupt: bool = Field(
        default=False,
        description="True if this exchange aborts currently playing lower-priority audio"
    )
    interrupted: bool = Field(
        default=False,
        description="True if this exchange was cut short by a subsequent priority move"
    )
    created_at: float = Field(
        default_factory=time.time,
        description="Epoch timestamp when the exchange was generated"
    )

    @property
    def total_words(self) -> int:
        return sum(len(turn.text.split()) for turn in self.turns)


class CommentaryContext(BaseModel):
    """Full broadcast context assembled by the Director to prime the LLM prompt."""
    evaluation: MoveEvaluation = Field(..., description="Quantitative and heuristic analysis of the move")
    white_player: str = Field(..., description="Username of White player")
    black_player: str = Field(..., description="Username of Black player")
    game_format: str = Field(default="blitz", description="Match format: bullet, blitz, rapid, classical")
    white_clock_seconds: Optional[float] = Field(default=None, description="White's remaining clock time")
    black_clock_seconds: Optional[float] = Field(default=None, description="Black's remaining clock time")
    is_time_trouble: bool = Field(default=False, description="True if active player is in critical time trouble")
    dynamic: SpeakingDynamic = Field(..., description="Director's selected speaking dynamic")
    move_time_spent_seconds: float = Field(default=0.0, description="Duration in seconds spent thinking on this move")
    think_category: ThinkCategory = Field(default=ThinkCategory.NORMAL, description="Think tempo classification relative to game format")
    target_word_range: str = Field(default="12-20 words total", description="Adaptive word budget directive for commentators")
    is_pondering: bool = Field(default=False, description="True if generating interim mid-think commentary")
    was_pondered: bool = Field(default=False, description="True if an interim pondering frame was already delivered for this move")
    candidate_suggestions: List[str] = Field(default_factory=list, description="Top prospective candidate moves for pondering")
    ponder_style_hint: Optional[str] = Field(default=None, description="Rotating archetype style for natural pondering commentary")
    dialogue_history: List[DialogueTurn] = Field(
        default_factory=list,
        description="Recent dialogue history to ensure flow and prevent repetition"
    )