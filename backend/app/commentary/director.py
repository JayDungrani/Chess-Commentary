# backend/app/commentary/director.py

import logging
from typing import List, Optional
from collections import deque

from app.engine.schemas import MoveEvaluation, MoveClassification
from app.commentary.schemas import (
    SpeakingDynamic,
    CommentaryContext,
    CommentaryExchange,
    DialogueTurn,
    CommentatorRole,
    ThinkCategory,
)
from app.lichess.pgn_parser import ParsedMoveEvent

logger = logging.getLogger(__name__)

FORMAT_TIME_TROUBLE_THRESHOLDS = {
    "bullet": 10.0,
    "blitz": 30.0,
    "rapid": 90.0,
    "classical": 300.0,
}

FORMAT_THINK_THRESHOLDS = {
    "bullet": {"instant": 0.8, "think": 2.5, "deep_think": 5.0},
    "blitz": {"instant": 1.5, "think": 7.0, "deep_think": 15.0},
    "rapid": {"instant": 2.5, "think": 12.0, "deep_think": 25.0},
    "classical": {"instant": 5.0, "think": 30.0, "deep_think": 90.0},
}

FORMAT_AUDIO_BACKPRESSURE_THRESHOLDS = {
    "bullet": 6.0,
    "blitz": 12.0,
    "rapid": 18.0,
    "classical": 25.0,
}


class BroadcastDirector:
    def __init__(self, history_limit: int = 6, game_format: str = "blitz"):
        self.history_limit = history_limit
        self.dialogue_history: deque[DialogueTurn] = deque(maxlen=history_limit)
        self.last_speaker: Optional[CommentatorRole] = None
        self.consecutive_silence_count: int = 0
        self.consecutive_book_moves: int = 0
        self.consecutive_fast_moves: int = 0
        self.game_format: str = game_format.lower()

    def reset(self, game_format: str = "blitz") -> None:
        """Resets commentator memory and tracking state for a new game."""
        self.dialogue_history.clear()
        self.last_speaker = None
        self.consecutive_silence_count = 0
        self.consecutive_book_moves = 0
        self.consecutive_fast_moves = 0
        self.game_format = game_format.lower()

    def is_format_time_trouble(self, clock_seconds: Optional[float]) -> bool:
        if clock_seconds is None:
            return False
        threshold = FORMAT_TIME_TROUBLE_THRESHOLDS.get(self.game_format, 30.0)
        return clock_seconds <= threshold

    def classify_think_time(self, think_seconds: float) -> ThinkCategory:
        """Classifies player think duration relative to the match format."""
        thresholds = FORMAT_THINK_THRESHOLDS.get(self.game_format, FORMAT_THINK_THRESHOLDS["blitz"])
        if think_seconds <= thresholds["instant"]:
            return ThinkCategory.INSTANT
        elif think_seconds >= thresholds["deep_think"]:
            return ThinkCategory.DEEP_THINK
        elif think_seconds >= thresholds["think"]:
            return ThinkCategory.THINK
        return ThinkCategory.NORMAL

    def determine_speaking_dynamic(
        self,
        eval_data: MoveEvaluation,
        is_time_trouble: bool,
        think_category: ThinkCategory = ThinkCategory.NORMAL,
        pending_audio_seconds: float = 0.0,
    ) -> SpeakingDynamic:
        """
        Production turn-taking logic:
        - Critical Tactical Swings (blunders, brilliancies, mistakes) trigger BANTER.
        - Deep Thinks in Rapid/Classical trigger BANTER or SOLO_ANALYST (never silence!).
        - Novelty / Time Trouble trigger SOLO_HOST.
        - Instant moves on quiet positions allow SILENCE to let audio buffer drain.
        - Book moves and routine developing moves balance between voices and natural pauses.
        """
        # Track consecutive fast moves
        if think_category == ThinkCategory.INSTANT:
            self.consecutive_fast_moves += 1
        elif think_category in (ThinkCategory.THINK, ThinkCategory.DEEP_THINK):
            self.consecutive_fast_moves = 0

        # Track consecutive book moves
        if eval_data.is_book:
            self.consecutive_book_moves += 1
        else:
            self.consecutive_book_moves = 0

        # 1. Critical Tactical Swings (Always two-voice BANTER)
        if eval_data.is_blunder or eval_data.classification == MoveClassification.BRILLIANT:
            self.consecutive_silence_count = 0
            return SpeakingDynamic.BANTER

        # 2. Inaccuracies and Mistakes -> Banter
        if eval_data.classification in (MoveClassification.MISTAKE, MoveClassification.INACCURACY):
            self.consecutive_silence_count = 0
            return SpeakingDynamic.BANTER

        # 3. Deep Thinks (Player paused significantly to calculate; critical narrative moment)
        if think_category == ThinkCategory.DEEP_THINK:
            self.consecutive_silence_count = 0
            # In Rapid/Blitz, single GM analyst takeaway prevents multi-turn audio backlog unless blunder/brilliant
            if self.game_format in ("rapid", "blitz") and not eval_data.is_blunder and eval_data.classification != MoveClassification.BRILLIANT:
                return SpeakingDynamic.SOLO_ANALYST
            if self.last_speaker == CommentatorRole.HOST or len(self.dialogue_history) == 0:
                return SpeakingDynamic.BANTER
            return SpeakingDynamic.SOLO_ANALYST

        # 4. Novelty Departure Point (Out of book)
        if eval_data.left_book_now:
            self.consecutive_silence_count = 0
            return SpeakingDynamic.SOLO_HOST

        # 5. Time Trouble Pressure
        if is_time_trouble:
            self.consecutive_silence_count = 0
            return SpeakingDynamic.SOLO_HOST

        # 6. Audio Backpressure Guard (Format-dependent threshold)
        max_audio_backpressure = FORMAT_AUDIO_BACKPRESSURE_THRESHOLDS.get(self.game_format, 12.0)
        if pending_audio_seconds > max_audio_backpressure:
            self.consecutive_silence_count += 1
            return SpeakingDynamic.SILENCE

        # 7. Book Moves
        if eval_data.is_book:
            if self.consecutive_book_moves >= 2:
                self.consecutive_book_moves = 0
                self.consecutive_silence_count = 0
                return SpeakingDynamic.SOLO_ANALYST

            if eval_data.ply <= 4 and self.consecutive_silence_count >= 1:
                self.consecutive_silence_count = 0
                return SpeakingDynamic.SOLO_HOST

            self.consecutive_silence_count += 1
            return SpeakingDynamic.SILENCE

        # 8. Fast Moves & Instant Sequences -> PLAY_BY_PLAY or SILENCE
        if think_category == ThinkCategory.INSTANT or self.consecutive_fast_moves >= 2:
            if pending_audio_seconds > 4.0:
                self.consecutive_silence_count += 1
                return SpeakingDynamic.SILENCE

            if self.consecutive_silence_count == 0 and len(self.dialogue_history) >= 1:
                self.consecutive_silence_count = 0
                return SpeakingDynamic.PLAY_BY_PLAY

            if self.consecutive_fast_moves >= 2:
                self.consecutive_silence_count = 0
                return SpeakingDynamic.PLAY_BY_PLAY

        # 9. Normal & Quiet Moves: Natural dialogue cadence
        if self.consecutive_silence_count == 0 and len(self.dialogue_history) >= 2:
            self.consecutive_silence_count += 1
            return SpeakingDynamic.SILENCE

        self.consecutive_silence_count = 0
        if self.last_speaker == CommentatorRole.ANALYST:
            return SpeakingDynamic.SOLO_HOST
        return SpeakingDynamic.SOLO_ANALYST

    def determine_word_range(
        self,
        eval_data: MoveEvaluation,
        dynamic: SpeakingDynamic,
        think_category: ThinkCategory,
        was_pondered: bool = False,
    ) -> str:
        """Determines the target spoken length for commentator dialogue, strictly combined."""
        if dynamic == SpeakingDynamic.PLAY_BY_PLAY:
            return "2-5 words total (Ultra-concise play-by-play move call, e.g. 'Bishop to e6.', 'Castles.')"
        if was_pondered:
            return "5-10 words total (Crisp confirmation of the played move)"
        if eval_data.is_blunder or eval_data.classification == MoveClassification.BRILLIANT:
            return "20-26 words total combined (Dramatic reaction, empathetic validation, and clear refutation)"
        if think_category == ThinkCategory.DEEP_THINK:
            if self.game_format in ("rapid", "blitz"):
                return "15-20 words total (Crisp single-takeaway summary to maintain broadcast pacing)"
            return "20-30 words total (In-depth strategic breakdown of the player's dilemma)"
        if think_category == ThinkCategory.THINK:
            return "14-20 words total"
        if think_category == ThinkCategory.INSTANT:
            return "5-10 words total (Snappy, punchy reaction to the instant move)"
        if dynamic == SpeakingDynamic.BANTER:
            return "16-22 words total combined"
        return "12-18 words total"

    def assemble_context(
        self,
        eval_data: MoveEvaluation,
        event: ParsedMoveEvent,
        white_player: str,
        black_player: str,
        pending_audio_seconds: float = 0.0,
        was_pondered: bool = False,
    ) -> CommentaryContext:
        """Constructs the fully enriched context contract ready for the LLM agent."""
        active_clock = event.white_clock_seconds if eval_data.turn == "white" else event.black_clock_seconds
        time_trouble = self.is_format_time_trouble(active_clock) or event.is_time_trouble

        think_seconds = max(0.0, getattr(event, "move_time_spent_seconds", 0.0) or 0.0)
        think_cat = self.classify_think_time(think_seconds)

        dynamic = self.determine_speaking_dynamic(
            eval_data=eval_data,
            is_time_trouble=time_trouble,
            think_category=think_cat,
            pending_audio_seconds=pending_audio_seconds,
        )

        word_range = self.determine_word_range(eval_data, dynamic, think_cat, was_pondered=was_pondered)

        return CommentaryContext(
            evaluation=eval_data,
            white_player=white_player,
            black_player=black_player,
            game_format=self.game_format,
            white_clock_seconds=event.white_clock_seconds,
            black_clock_seconds=event.black_clock_seconds,
            is_time_trouble=time_trouble,
            dynamic=dynamic,
            move_time_spent_seconds=think_seconds,
            think_category=think_cat,
            target_word_range=word_range,
            is_pondering=False,
            was_pondered=was_pondered,
            dialogue_history=list(self.dialogue_history),
        )

    def assemble_pondering_context(
        self,
        ply: int,
        turn: str,
        acting_player: str,
        fen: str,
        elapsed_think_seconds: float,
        candidate_suggestions: List[str],
        white_player: str,
        black_player: str,
        white_clock_seconds: Optional[float] = None,
        black_clock_seconds: Optional[float] = None,
    ) -> CommentaryContext:
        """Constructs an interim context when a player is calculating deep in the tank."""
        dummy_eval = MoveEvaluation(
            ply=ply,
            turn=turn,
            played_san="thinking...",
            played_uci="0000",
            fen_after=fen,
            eval_swing_cp=0,
            win_prob_before=0.5,
            win_prob_after=0.5,
            win_prob_loss=0.0,
            classification=MoveClassification.GOOD,
        )

        dynamic = (
            SpeakingDynamic.SOLO_ANALYST
            if self.last_speaker != CommentatorRole.ANALYST
            else SpeakingDynamic.SOLO_HOST
        )

        return CommentaryContext(
            evaluation=dummy_eval,
            white_player=white_player,
            black_player=black_player,
            game_format=self.game_format,
            white_clock_seconds=white_clock_seconds,
            black_clock_seconds=black_clock_seconds,
            is_time_trouble=self.is_format_time_trouble(
                white_clock_seconds if turn == "white" else black_clock_seconds
            ),
            dynamic=dynamic,
            move_time_spent_seconds=elapsed_think_seconds,
            think_category=ThinkCategory.DEEP_THINK,
            target_word_range="12-16 words total",
            is_pondering=True,
            was_pondered=False,
            candidate_suggestions=candidate_suggestions,
            dialogue_history=list(self.dialogue_history),
        )

    def record_exchange(self, exchange: CommentaryExchange) -> None:
        """Appends generated dialogue turns to the rolling history and updates speaker tracking."""
        for turn in exchange.turns:
            self.dialogue_history.append(turn)
            self.last_speaker = turn.speaker