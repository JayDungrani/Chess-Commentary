# backend/app/lichess/game_streamer.py

import logging
import re
from typing import AsyncGenerator, Optional, Union

from app.lichess.base_streamer import BaseLichessStreamer
from app.lichess.pgn_parser import (
    ChessStateTracker,
    GameMetadata,
    GameTerminationEvent,
    ParsedMoveEvent,
)

logger = logging.getLogger(__name__)


class LichessGameStreamer(BaseLichessStreamer):
    """
    Consumes live NDJSON game streams from Lichess for a specific game ID
    (GET https://lichess.org/api/stream/game/{gameId}).

    Parses incoming chunks via ChessStateTracker and yields structured
    GameMetadata, ParsedMoveEvent, and GameTerminationEvent objects.
    """

    LICHESS_BASE_URL = "https://lichess.org/api/stream/game"
    GAME_ID_REGEX = re.compile(r"([a-zA-Z0-9]{8})")

    def __init__(
        self,
        game_id: str,
        tracker: Optional[ChessStateTracker] = None,
        time_trouble_threshold_seconds: float = 30.0,
        increment_seconds: float = 0.0,
        **streamer_kwargs,
    ):
        super().__init__(**streamer_kwargs)
        self.raw_game_id = game_id
        self.game_id = self._extract_clean_game_id(game_id)

        # State tracker instance
        self.tracker = tracker or ChessStateTracker(
            time_trouble_threshold_seconds=time_trouble_threshold_seconds,
            increment_seconds=increment_seconds,
        )

    def get_endpoint_url(self) -> str:
        """Constructs endpoint URL for the public game NDJSON stream."""
        return f"{self.LICHESS_BASE_URL}/{self.game_id}"

    async def stream_game_events(
        self,
    ) -> AsyncGenerator[Union[GameMetadata, ParsedMoveEvent, GameTerminationEvent], None]:
        """
        Main consumer generator.
        Streams raw NDJSON lines, feeds them into ChessStateTracker,
        and yields verified metadata, move, and termination events.
        """
        logger.info(f"Starting game stream for ID: {self.game_id}")

        async for line in self.stream_lines():
            try:
                event = self.tracker.parse_lichess_line(line)
                if event is not None:
                    yield event

                    # Stop streaming cleanly if out-of-band termination occurs (resignation, timeout)
                    if isinstance(event, GameTerminationEvent):
                        logger.info(
                            f"Game {self.game_id} concluded: {event.termination_reason}"
                        )
                        self.stop()
                        break

                    # Stop streaming if board reached terminal state (checkmate, stalemate)
                    if isinstance(event, ParsedMoveEvent) and event.termination_reason:
                        logger.info(
                            f"Game {self.game_id} reached termination: {event.termination_reason}"
                        )
                        self.stop()
                        break

            except Exception as parse_exc:
                logger.error(f"Error parsing game stream line: {line} | Error: {parse_exc}")
                continue

    @classmethod
    def _extract_clean_game_id(cls, raw_id_or_url: str) -> str:
        """
        Normalizes input strings to an 8-character Lichess game ID.
        Handles full URLs (e.g., https://lichess.org/kSc2w4MX/white)
        or 12-character player-specific IDs (e.g., kSc2w4MXabc1).
        """
        cleaned = raw_id_or_url.strip().rstrip("/")
        match = cls.GAME_ID_REGEX.search(cleaned.split("/")[-1])
        if not match:
            raise ValueError(f"Invalid Lichess Game ID or URL provided: '{raw_id_or_url}'")
        return match.group(1)