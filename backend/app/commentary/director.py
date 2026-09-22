# backend/app/commentary/director.py

import logging
import time
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
        self.ponder_style_index: int = 0
        self.last_exchange_time: float = 0.0
        self.last_exchange_duration: float = 0.0
        self.last_exchange_dynamic: Optional[SpeakingDynamic] = None

    def reset(self, game_format: str = "blitz") -> None:
        """Resets commentator memory and tracking state for a new game."""
        self.dialogue_history.clear()
        self.last_speaker = None
        self.consecutive_silence_count = 0
        self.consecutive_book_moves = 0
        self.consecutive_fast_moves = 0
        self.game_format = game_format.lower()
        self.ponder_style_index = 0
        self.last_exchange_time = 0.0
        self.last_exchange_duration = 0.0
        self.last_exchange_dynamic = None

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

    def is_long_audio_active(self, pending_audio_seconds: float = 0.0) -> bool:
        """
        Determines whether long audio commentary (banter, solo host/analyst breakdown)
        is currently actively playing or queued.
        """
        if pending_audio_seconds > 0.1:
            if self.last_exchange_dynamic and self.last_exchange_dynamic != SpeakingDynamic.PLAY_BY_PLAY:
                return True
            if pending_audio_seconds > 2.5:
                return True
            return False

        if self.last_exchange_duration > 0 and self.last_exchange_dynamic:
            elapsed = time.time() - self.last_exchange_time
            remaining = self.last_exchange_duration - elapsed
            if remaining > 0.1:
                return self.last_exchange_dynamic != SpeakingDynamic.PLAY_BY_PLAY

        return False

    def is_play_by_play_active(self, pending_audio_seconds: float = 0.0) -> bool:
        """
        Determines whether play-by-play audio (crisp spoken move call) is currently active.
        """
        if pending_audio_seconds > 0.1:
            if self.last_exchange_dynamic == SpeakingDynamic.PLAY_BY_PLAY:
                return True
            return False

        if self.last_exchange_duration > 0 and self.last_exchange_dynamic == SpeakingDynamic.PLAY_BY_PLAY:
            elapsed = time.time() - self.last_exchange_time
            return (self.last_exchange_duration - elapsed) > 0.1

        return False

    def determine_speaking_dynamic(
        self,
        eval_data: MoveEvaluation,
        is_time_trouble: bool,
        think_category: ThinkCategory = ThinkCategory.NORMAL,
        pending_audio_seconds: float = 0.0,
        is_long_audio_playing: Optional[bool] = None,
        is_play_by_play_playing: Optional[bool] = None,
    ) -> SpeakingDynamic:
        """
        Production turn-taking logic:
        - Critical Tactical Swings (blunders, brilliancies) trigger BANTER (priority interrupt).
        - If long commentary audio is currently playing when next move is played: return SILENCE.
        - Otherwise, if play-by-play audio is going on: keep continuing speaking.
        - Deep Thinks in Rapid/Classical trigger BANTER or SOLO_ANALYST.
        - Novelty / Time Trouble trigger SOLO_HOST.
        - Routine book recaptures and fast moves trigger PLAY_BY_PLAY.
        - Normal and quiet moves alternate between SOLO_HOST and SOLO_ANALYST.
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

        # 1. Critical Tactical Swings (Always two-voice BANTER - emergency interrupt)
        if eval_data.is_blunder or eval_data.classification == MoveClassification.BRILLIANT:
            self.consecutive_silence_count = 0
            return SpeakingDynamic.BANTER

        # Resolve whether long audio or play-by-play audio is active
        if is_long_audio_playing is None:
            is_long_audio = self.is_long_audio_active(pending_audio_seconds)
        else:
            is_long_audio = is_long_audio_playing

        # 2. Long Audio Playing Guard:
        # If long audio commentary is currently playing when the next move arrives, keep it silent
        # so the active breakdown finishes cleanly without talking over it or stacking up.
        # Otherwise, if it is play-by-play audio going on, keep continuing speaking.
        if is_long_audio:
            self.consecutive_silence_count += 1
            return SpeakingDynamic.SILENCE

        # 3. Inaccuracies and Mistakes
        if eval_data.classification == MoveClassification.MISTAKE:
            self.consecutive_silence_count = 0
            return SpeakingDynamic.BANTER
        elif eval_data.classification == MoveClassification.INACCURACY:
            self.consecutive_silence_count = 0
            if eval_data.ply <= 10 or eval_data.is_book:
                # In the opening, minor inaccuracies are natural development choices; keep it to a single voice
                return SpeakingDynamic.SOLO_ANALYST if self.last_speaker != CommentatorRole.ANALYST else SpeakingDynamic.SOLO_HOST
            return SpeakingDynamic.BANTER

        # 4. Deep Thinks (Player paused significantly to calculate; critical narrative moment)
        if think_category == ThinkCategory.DEEP_THINK:
            self.consecutive_silence_count = 0
            # In Rapid/Blitz, single GM analyst takeaway prevents multi-turn audio backlog unless blunder/brilliant
            if self.game_format in ("rapid", "blitz") and not eval_data.is_blunder and eval_data.classification != MoveClassification.BRILLIANT:
                return SpeakingDynamic.SOLO_ANALYST
            if self.last_speaker == CommentatorRole.HOST or len(self.dialogue_history) == 0:
                return SpeakingDynamic.BANTER
            return SpeakingDynamic.SOLO_ANALYST

        # 5. Novelty Departure Point (Out of book)
        if eval_data.left_book_now:
            self.consecutive_silence_count = 0
            return SpeakingDynamic.SOLO_HOST

        # 6. Time Trouble Pressure
        if is_time_trouble:
            self.consecutive_silence_count = 0
            return SpeakingDynamic.SOLO_HOST

        # 7. Audio Backpressure Guard: Drop to crisp play-by-play rather than complete silence
        max_audio_backpressure = FORMAT_AUDIO_BACKPRESSURE_THRESHOLDS.get(self.game_format, 12.0)
        if pending_audio_seconds > max_audio_backpressure:
            self.consecutive_silence_count = 0
            return SpeakingDynamic.PLAY_BY_PLAY

        # 8. Book Moves: 100% voiced coverage (Opening framing, GM analysis, or crisp move calls)
        if eval_data.is_book:
            self.consecutive_silence_count = 0
            # Routine opening recaptures (e.g. cxd4, Nxd4) get crisp play-by-play calls
            if "x" in eval_data.played_san:
                return SpeakingDynamic.PLAY_BY_PLAY

            # First moves get immediate broadcast framing
            if eval_data.ply <= 2:
                return SpeakingDynamic.SOLO_HOST
            elif self.consecutive_book_moves % 2 == 0:
                return SpeakingDynamic.SOLO_ANALYST
            elif think_category == ThinkCategory.INSTANT:
                return SpeakingDynamic.PLAY_BY_PLAY
            return SpeakingDynamic.SOLO_HOST if self.last_speaker == CommentatorRole.ANALYST else SpeakingDynamic.SOLO_ANALYST

        # 9. Fast Moves & Instant Sequences -> Crisp zero-latency PLAY_BY_PLAY (never silence)
        if think_category == ThinkCategory.INSTANT or self.consecutive_fast_moves >= 2:
            self.consecutive_silence_count = 0
            return SpeakingDynamic.PLAY_BY_PLAY

        # 10. Normal & Quiet Moves: Alternating Host and Analyst (Universal Spoken Floor)
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
            return "2-5 words total (Ultra-concise play-by-play move call, e.g. 'Bishop to e2.', 'Castles.')"
        if was_pondered:
            return "5-10 words total (Crisp confirmation of the played move)"
        if eval_data.is_blunder or eval_data.classification == MoveClassification.BRILLIANT:
            return "18-24 words total combined (Dramatic reaction and refutation)"
        if think_category == ThinkCategory.DEEP_THINK:
            if self.game_format in ("rapid", "blitz"):
                return "15-20 words total (Deep think breakdown: analyze complications weighed during the long pause)"
            return "20-28 words total (In-depth strategic breakdown of the player's dilemma)"
        if think_category == ThinkCategory.THINK:
            return "12-16 words total (Focused strategic takeaway matching the player's calculation pause)"
        if think_category == ThinkCategory.INSTANT:
            return "2-5 words total (Clean play-by-play move call)"
        if dynamic == SpeakingDynamic.BANTER:
            return "14-20 words total combined"
        return "10-15 words total"

    def assemble_context(
        self,
        eval_data: MoveEvaluation,
        event: ParsedMoveEvent,
        white_player: str,
        black_player: str,
        pending_audio_seconds: float = 0.0,
        is_long_audio_playing: Optional[bool] = None,
        is_play_by_play_playing: Optional[bool] = None,
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
            is_long_audio_playing=is_long_audio_playing,
            is_play_by_play_playing=is_play_by_play_playing,
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

        ponder_styles = [
            "TACTICAL_QUESTION: Pose a sharp, direct rhetorical question about candidate moves or threats (e.g., 'Can White get away with c5 right now, or is e4 too fast?')",
            "STRATEGIC_TRADEOFF: Highlight positional trade-offs (e.g., 'Tough call, trading minor pieces relieves the squeeze, but concedes the d4 outpost.')",
            "PIECE_ACTIVITY: Spotlight a key piece's struggle or mobility (e.g., 'That bishop on e2 needs breathing room, a central pawn break feels mandatory.')",
            "INSTINCT_VS_ENGINE: Contrast natural human over-the-board desire with cold engine truth (e.g., 'Human instinct screams to counterpunch, though computers favor quiet defense.')",
            "TENSION_ATMOSPHERE: Capture the atmospheric tension and ticking clock (e.g., 'Heavy silence over the board, this next pawn move dictates the entire flow of the endgame.')",
        ]
        style_hint = ponder_styles[self.ponder_style_index % len(ponder_styles)]
        self.ponder_style_index += 1

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
            ponder_style_hint=style_hint,
            dialogue_history=list(self.dialogue_history),
        )

    def record_exchange(self, exchange: CommentaryExchange) -> None:
        """Appends generated dialogue turns to the rolling history and updates speaker tracking."""
        if exchange.dynamic != SpeakingDynamic.SILENCE and exchange.turns:
            self.last_exchange_time = time.time()
            self.last_exchange_dynamic = exchange.dynamic
            self.last_exchange_duration = sum(
                getattr(turn, "estimated_duration_seconds", 0.0) or max(1.2, len(turn.text.split()) / 2.5)
                for turn in exchange.turns
            )
            for turn in exchange.turns:
                self.dialogue_history.append(turn)
                self.last_speaker = turn.speaker