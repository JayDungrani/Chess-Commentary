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
)
from app.lichess.pgn_parser import ParsedMoveEvent

logger = logging.getLogger(__name__)

FORMAT_TIME_TROUBLE_THRESHOLDS = {
    "bullet": 10.0,
    "blitz": 30.0,
    "rapid": 90.0,
    "classical": 300.0,
}


class BroadcastDirector:
    def __init__(self, history_limit: int = 6, game_format: str = "blitz"):
        self.history_limit = history_limit
        self.dialogue_history: deque[DialogueTurn] = deque(maxlen=history_limit)
        self.last_speaker: Optional[CommentatorRole] = None
        self.consecutive_silence_count: int = 0
        self.consecutive_book_moves: int = 0
        self.game_format: str = game_format.lower()

    def reset(self, game_format: str = "blitz") -> None:
        """Resets commentator memory and tracking state for a new game."""
        self.dialogue_history.clear()
        self.last_speaker = None
        self.consecutive_silence_count = 0
        self.consecutive_book_moves = 0
        self.game_format = game_format.lower()

    def is_format_time_trouble(self, clock_seconds: Optional[float]) -> bool:
        if clock_seconds is None:
            return False
        threshold = FORMAT_TIME_TROUBLE_THRESHOLDS.get(self.game_format, 30.0)
        return clock_seconds <= threshold

    def determine_speaking_dynamic(
        self,
        eval_data: MoveEvaluation,
        is_time_trouble: bool,
        pending_audio_seconds: float = 0.0,
    ) -> SpeakingDynamic:
        """
        Production turn-taking logic:
        - Blunders, Brilliancies, Inaccuracies, and Mistakes trigger BANTER.
        - Novelty / Time Trouble trigger SOLO_HOST.
        - Sequences of 3-4 book moves trigger SOLO_ANALYST.
        - Routine / Developing moves alternate between SOLO_HOST, SOLO_ANALYST, and SILENCE.
        """
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

        # 3. Novelty Departure Point (Out of book)
        if eval_data.left_book_now:
            self.consecutive_silence_count = 0
            return SpeakingDynamic.SOLO_HOST

        # 4. Time Trouble Pressure
        if is_time_trouble:
            self.consecutive_silence_count = 0
            return SpeakingDynamic.SOLO_HOST

        # 5. Audio Backpressure Guard
        if pending_audio_seconds > 12.0:
            self.consecutive_silence_count += 1
            return SpeakingDynamic.SILENCE

        # 6. Book Moves
        if eval_data.is_book:
            # Speak every 2 book moves instead of every 3+
            if self.consecutive_book_moves >= 2:
                self.consecutive_book_moves = 0
                self.consecutive_silence_count = 0
                return SpeakingDynamic.SOLO_ANALYST

            # Opening greeting on ply <= 4
            if eval_data.ply <= 4 and self.consecutive_silence_count >= 1:
                self.consecutive_silence_count = 0
                return SpeakingDynamic.SOLO_HOST

            self.consecutive_silence_count += 1
            return SpeakingDynamic.SILENCE

        # 7. Normal & Quiet Moves
        # OPTION A: Allow 2 spoken moves before 1 pause (recommended)
        if self.consecutive_silence_count == 0 and len(self.dialogue_history) >= 2:
            # Check if last 2 moves both had commentary
            self.consecutive_silence_count += 1
            return SpeakingDynamic.SILENCE

        # OPTION B: Never force silence on normal moves (maximum commentary)
        # (Simply remove the `if self.consecutive_silence_count == 0: return SpeakingDynamic.SILENCE` block entirely)

        self.consecutive_silence_count = 0
        if self.last_speaker == CommentatorRole.ANALYST:
            return SpeakingDynamic.SOLO_HOST
        return SpeakingDynamic.SOLO_ANALYST

    def assemble_context(
        self,
        eval_data: MoveEvaluation,
        event: ParsedMoveEvent,
        white_player: str,
        black_player: str,
        pending_audio_seconds: float = 0.0,
    ) -> CommentaryContext:
        """Constructs the fully enriched context contract ready for the LLM agent."""
        active_clock = event.white_clock_seconds if eval_data.turn == "white" else event.black_clock_seconds
        time_trouble = self.is_format_time_trouble(active_clock) or event.is_time_trouble

        dynamic = self.determine_speaking_dynamic(
            eval_data=eval_data,
            is_time_trouble=time_trouble,
            pending_audio_seconds=pending_audio_seconds,
        )

        return CommentaryContext(
            evaluation=eval_data,
            white_player=white_player,
            black_player=black_player,
            game_format=self.game_format,
            white_clock_seconds=event.white_clock_seconds,
            black_clock_seconds=event.black_clock_seconds,
            is_time_trouble=time_trouble,
            dynamic=dynamic,
            dialogue_history=list(self.dialogue_history),
        )

    def record_exchange(self, exchange: CommentaryExchange) -> None:
        """Appends generated dialogue turns to the rolling history and updates speaker tracking."""
        for turn in exchange.turns:
            self.dialogue_history.append(turn)
            self.last_speaker = turn.speaker