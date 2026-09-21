# backend/app/lichess/pacing_buffer.py

import asyncio
import logging
import time
from typing import AsyncGenerator, Optional, Union

import chess

from app.config import settings
from app.lichess.pgn_parser import (
    GameMetadata,
    ParsedMoveEvent,
    GameTerminationEvent,
    PonderingEvent,
)

logger = logging.getLogger(__name__)

PONDER_THRESHOLDS = {
    "bullet": 999.0,
    "ultra_bullet": 999.0,
    "blitz": 15.0,
    "rapid": 18.0,
    "classical": 45.0,
}


class PacedMoveStreamer:
    """
    Buffers incoming Lichess moves and releases them according to player think times.
    Adapts buffer limits dynamically based on game speed (e.g. Rapid vs Blitz)
    and emits interim PonderingEvent frames during deep calculations.
    """

    def __init__(
        self,
        streamer,
        fast_forward_initial_history: bool = True,
        max_paced_move_delay_seconds: float = 45.0,
        target_live_ply: Optional[int] = None,
        game_format: Optional[str] = None,
        enable_pondering: bool = True,
        cooldown_plies: int = 4,
        min_ponder_ply: int = 8,
    ):
        self.streamer = streamer
        self.fast_forward_initial = fast_forward_initial_history
        self.max_paced_move_delay = max_paced_move_delay_seconds
        self.target_live_ply = target_live_ply
        self.game_format = game_format
        self.enable_pondering = enable_pondering
        self.cooldown_plies = cooldown_plies
        self.min_ponder_ply = min_ponder_ply
        self.last_pondered_ply: Optional[int] = None
        self._last_fen = chess.STARTING_FEN

        if game_format:
            self.set_game_format(game_format)

        self._queue: asyncio.Queue[Optional[Union[GameMetadata, ParsedMoveEvent, GameTerminationEvent, PonderingEvent, Exception]]] = asyncio.Queue()
        self._producer_task: Optional[asyncio.Task] = None
        self._is_running = False

    def set_game_format(self, game_format: str) -> None:
        """Dynamically adapts the maximum buffer delay based on game speed."""
        fmt = (game_format or "").lower()
        self.game_format = fmt
        if fmt in ("bullet", "ultra_bullet"):
            self.max_paced_move_delay = getattr(settings, "pacing_buffer_max_delay_bullet", 4.0)
        elif fmt == "blitz":
            self.max_paced_move_delay = getattr(settings, "pacing_buffer_max_delay_blitz", 15.0)
        elif fmt == "rapid":
            self.max_paced_move_delay = getattr(settings, "pacing_buffer_max_delay_rapid", 45.0)
        elif fmt == "classical":
            self.max_paced_move_delay = getattr(settings, "pacing_buffer_max_delay_classical", 120.0)
        else:
            self.max_paced_move_delay = getattr(settings, "max_paced_move_delay_seconds", 45.0)
        logger.info(f"PacedMoveStreamer format set to '{game_format}', max pace delay: {self.max_paced_move_delay}s")

    async def _get_stream_generator(self):
        if hasattr(self.streamer, "stream_game_events"):
            return self.streamer.stream_game_events()
        elif hasattr(self.streamer, "stream_events"):
            return self.streamer.stream_events()
        elif hasattr(self.streamer, "stream_moves"):
            return self.streamer.stream_moves()
        elif hasattr(self.streamer, "__aiter__"):
            return self.streamer
        raise AttributeError(f"Streamer {type(self.streamer)} has no supported async stream method.")

    async def _producer_loop(self):
        try:
            stream = await self._get_stream_generator()
            async for event in stream:
                if not self._is_running:
                    break
                await self._queue.put(event)
        except asyncio.CancelledError:
            pass
        except Exception as exc:
            logger.error(f"Producer error: {exc}", exc_info=True)
            await self._queue.put(exc)
        finally:
            await self._queue.put(None)

    async def stream_paced_events(
        self,
    ) -> AsyncGenerator[Union[GameMetadata, ParsedMoveEvent, GameTerminationEvent, PonderingEvent], None]:
        self._is_running = True
        self._producer_task = asyncio.create_task(self._producer_loop())

        last_emit_wall_time = time.monotonic()
        is_initial_catchup = self.fast_forward_initial

        try:
            while self._is_running:
                event = await self._queue.get()

                if event is None:
                    break

                if isinstance(event, Exception):
                    raise event

                # Emit metadata or termination packets without pacing
                if type(event).__name__ in ("GameMetadata", "GameTerminationEvent"):
                    if type(event).__name__ == "GameMetadata":
                        if getattr(event, "speed", None):
                            self.set_game_format(event.speed)
                        if getattr(event, "initial_fen", None):
                            self._last_fen = event.initial_fen
                    yield event
                    last_emit_wall_time = time.monotonic()
                    continue

                if isinstance(event, ParsedMoveEvent) or type(event).__name__ == "ParsedMoveEvent":
                    # 1. Fast-forward moves strictly BEFORE target_live_ply
                    if is_initial_catchup and self.target_live_ply and self.target_live_ply > 0:
                        if event.ply < self.target_live_ply:
                            self._last_fen = event.fen
                            yield event
                            last_emit_wall_time = time.monotonic()
                            continue
                        elif event.ply == self.target_live_ply:
                            # Render current live move immediately, then exit catch-up mode
                            is_initial_catchup = False
                            self._last_fen = event.fen
                            last_emit_wall_time = time.monotonic()
                            yield event
                            continue

                    # Catch-up complete: all subsequent buffered moves MUST be paced
                    is_initial_catchup = False

                    # For FIDE broadcasts (max_delay <= 0), emit immediately
                    if self.max_paced_move_delay <= 0.0:
                        last_emit_wall_time = time.monotonic()
                        self._last_fen = event.fen
                        yield event
                        continue

                    # 2. Pace moves based on player think time (even if pre-buffered in _queue)
                    raw_delay = event.move_time_spent_seconds
                    target_delay = min(raw_delay, self.max_paced_move_delay)
                    move_start_wall_time = last_emit_wall_time
                    elapsed_wall_time = time.monotonic() - move_start_wall_time
                    remaining_delay = target_delay - elapsed_wall_time
                    ponder_threshold = PONDER_THRESHOLDS.get(self.game_format or "rapid", 18.0)

                    # Cooldown guard: require at least cooldown_plies between consecutive pondering moments
                    ply_cooldown_ok = (
                        self.last_pondered_ply is None
                        or (event.ply - self.last_pondered_ply) >= self.cooldown_plies
                    )

                    # Opening guard: don't speculate in the tank during standard opening development
                    opening_ok = event.ply >= self.min_ponder_ply

                    # Time trouble guard: scrambling players low on clock are not deep in strategic planning
                    active_clock = event.white_clock_seconds if event.turn == "white" else event.black_clock_seconds
                    is_in_time_trouble = False
                    if active_clock is not None:
                        if self.game_format in ("bullet", "ultra_bullet"):
                            is_in_time_trouble = active_clock <= 10.0
                        elif self.game_format == "blitz":
                            is_in_time_trouble = active_clock <= 15.0
                        elif self.game_format == "rapid":
                            is_in_time_trouble = active_clock <= 25.0
                        else:
                            is_in_time_trouble = active_clock <= 45.0

                    should_ponder = (
                        self.enable_pondering
                        and target_delay >= ponder_threshold
                        and remaining_delay > 4.0
                        and ply_cooldown_ok
                        and opening_ok
                        and not is_in_time_trouble
                    )

                    if should_ponder:
                        self.last_pondered_ply = event.ply
                        # Yield interim pondering event mid-think
                        trigger_delay = max(2.0, min(8.0, remaining_delay * 0.45))
                        await asyncio.sleep(trigger_delay)

                        ponder_event = PonderingEvent(
                            ply=max(0, event.ply - 1),
                            turn=event.turn,
                            acting_player=event.acting_player or ("White" if event.turn == "white" else "Black"),
                            fen=self._last_fen,
                            elapsed_think_seconds=round(time.monotonic() - move_start_wall_time, 2),
                            white_clock_seconds=event.white_clock_seconds,
                            black_clock_seconds=event.black_clock_seconds,
                        )
                        yield ponder_event

                        # Sleep remainder of target think time
                        remaining_delay = target_delay - (time.monotonic() - move_start_wall_time)
                        if remaining_delay > 0:
                            await asyncio.sleep(remaining_delay)
                    else:
                        if remaining_delay > 0:
                            await asyncio.sleep(remaining_delay)

                    # 3. Timestamp right before yielding so commentary duration credits toward think time
                    last_emit_wall_time = time.monotonic()
                    self._last_fen = event.fen
                    yield event

        finally:
            self.stop()

    def stop(self):
        self._is_running = False
        if self._producer_task and not self._producer_task.done():
            self._producer_task.cancel()
        if hasattr(self.streamer, "stop"):
            self.streamer.stop()