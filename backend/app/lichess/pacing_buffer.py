# backend/app/lichess/pacing_buffer.py

import asyncio
import logging
import time
from typing import AsyncGenerator, Optional, Union

from app.lichess.pgn_parser import GameMetadata, ParsedMoveEvent

logger = logging.getLogger(__name__)


class PacedMoveStreamer:
    """
    Buffers incoming Lichess moves and releases them according to player think times.
    For live tournament broadcasts (max_delay=0), moves emit instantly without delay.
    """

    def __init__(
        self,
        streamer,
        fast_forward_initial_history: bool = True,
        max_paced_move_delay_seconds: float = 120.0,
        target_live_ply: Optional[int] = None,
    ):
        self.streamer = streamer
        self.fast_forward_initial = fast_forward_initial_history
        self.max_paced_move_delay = max_paced_move_delay_seconds
        self.target_live_ply = target_live_ply

        self._queue: asyncio.Queue[Optional[Union[GameMetadata, ParsedMoveEvent, Exception]]] = asyncio.Queue()
        self._producer_task: Optional[asyncio.Task] = None
        self._is_running = False

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
    ) -> AsyncGenerator[Union[GameMetadata, ParsedMoveEvent], None]:
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
                    yield event
                    last_emit_wall_time = time.monotonic()
                    continue

                if isinstance(event, ParsedMoveEvent) or type(event).__name__ == "ParsedMoveEvent":
                    # 1. Fast-forward moves strictly BEFORE target_live_ply
                    if is_initial_catchup and self.target_live_ply and self.target_live_ply > 0:
                        if event.ply < self.target_live_ply:
                            yield event
                            last_emit_wall_time = time.monotonic()
                            continue
                        elif event.ply == self.target_live_ply:
                            # Render current live move immediately, then exit catch-up mode
                            is_initial_catchup = False
                            last_emit_wall_time = time.monotonic()
                            yield event
                            continue

                    # Catch-up complete: all subsequent buffered moves MUST be paced
                    is_initial_catchup = False

                    # For FIDE broadcasts (max_delay <= 0), emit immediately
                    if self.max_paced_move_delay <= 0.0:
                        last_emit_wall_time = time.monotonic()
                        yield event
                        continue

                    # 2. Pace moves based on player think time (even if pre-buffered in _queue)
                    raw_delay = event.move_time_spent_seconds
                    target_delay = min(raw_delay, self.max_paced_move_delay)
                    elapsed_wall_time = time.monotonic() - last_emit_wall_time
                    remaining_delay = target_delay - elapsed_wall_time

                    if remaining_delay > 0:
                        await asyncio.sleep(remaining_delay)

                    # 3. Timestamp right before yielding so commentary duration credits toward think time
                    last_emit_wall_time = time.monotonic()
                    yield event

        finally:
            self.stop()

    def stop(self):
        self._is_running = False
        if self._producer_task and not self._producer_task.done():
            self._producer_task.cancel()
        if hasattr(self.streamer, "stop"):
            self.streamer.stop()