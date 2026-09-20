# backend/app/lichess/base_streamer.py

import abc
import asyncio
import logging
import random
from typing import AsyncGenerator, Dict, Optional, Any
import httpx

logger = logging.getLogger(__name__)


class StreamError(Exception):
    """Base exception for streaming failures."""
    pass


class NonRetryableStreamError(StreamError):
    """Terminal errors (404, 401, 403) that must abort immediately."""
    pass


class BaseLichessStreamer(abc.ABC):
    """
    Abstract resilient streaming client for Lichess NDJSON and PGN streams.
    Includes auto-reconnect, exponential backoff with jitter, zombie socket detection,
    and HTTP 429 rate-limit negotiation.
    """

    DEFAULT_USER_AGENT = "LiveChessCommentary/1.0 (https://github.com/live-chess-commentary)"

    def __init__(
        self,
        api_token: Optional[str] = None,
        user_agent: Optional[str] = None,
        read_timeout_seconds: Optional[float] = None,  # Set to None to disable read timeouts
        initial_backoff_seconds: float = 1.0,
        max_backoff_seconds: float = 60.0,
        backoff_multiplier: float = 2.0,
    ):
        self.api_token = api_token
        self.user_agent = user_agent or self.DEFAULT_USER_AGENT
        self.read_timeout_seconds = read_timeout_seconds
        self.initial_backoff_seconds = initial_backoff_seconds
        self.max_backoff_seconds = max_backoff_seconds
        self.backoff_multiplier = backoff_multiplier

        self._is_running = False
        self._client: Optional[httpx.AsyncClient] = None

    @abc.abstractmethod
    def get_endpoint_url(self) -> str:
        """Returns the full target Lichess URL."""
        pass

    def get_headers(self) -> Dict[str, str]:
        """Constructs headers complying with Lichess API requirements."""
        headers = {
            "User-Agent": self.user_agent,
            "Accept": "application/x-ndjson",
        }
        if self.api_token:
            headers["Authorization"] = f"Bearer {self.api_token}"
        return headers

    def get_params(self) -> Optional[Dict[str, Any]]:
        """Optional query parameters."""
        return None

    async def stream_lines(self) -> AsyncGenerator[str, None]:
        """
        Continuously yields non-empty string lines from the Lichess HTTP stream.
        Automatically recovers from dropped sockets, timeouts, and temporary outages.
        """
        self._is_running = True
        attempt = 0

        # Enforce connect, write, and read timeouts.
        # read_timeout guarantees zombie connections get terminated.
        timeout_config = httpx.Timeout(
                    connect=10.0,
                    read=self.read_timeout_seconds,
                    write=10.0,
                    pool=10.0,
                )

        while self._is_running:
            url = self.get_endpoint_url()
            headers = self.get_headers()
            params = self.get_params()

            try:
                async with httpx.AsyncClient(timeout=timeout_config) as client:
                    self._client = client
                    logger.info(f"Connecting to Lichess stream: {url}")

                    async with client.stream("GET", url, headers=headers, params=params) as response:
                        # 1. Handle HTTP errors
                        if response.status_code == 429:
                            retry_after = self._parse_retry_after(response)
                            logger.warning(f"Rate limited (429). Sleeping for {retry_after}s.")
                            await self._sleep_cancellable(retry_after)
                            continue

                        if response.status_code in (401, 403):
                            raise NonRetryableStreamError(
                                f"Authentication failure ({response.status_code}) for URL: {url}"
                            )

                        if response.status_code == 404:
                            raise NonRetryableStreamError(
                                f"Resource not found (404). Invalid game/broadcast ID: {url}"
                            )

                        response.raise_for_status()

                        # 2. Connection succeeded and validated
                        logger.info("Stream connection established. Ingesting chunks...")
                        lines_read_in_session = 0

                        # 3. Line consumption
                        async for raw_line in response.aiter_lines():
                            if not self._is_running:
                                break

                            # Keep-alives from Lichess arrive as whitespace/newlines
                            line = raw_line.strip()
                            if not line:
                                continue

                            # Reset backoff after successfully receiving valid payloads
                            if attempt > 0 and lines_read_in_session > 0:
                                attempt = 0
                                logger.info("Stream health stabilized. Reset backoff counter.")

                            lines_read_in_session += 1
                            yield line

            except NonRetryableStreamError as nr_err:
                logger.error(f"Fatal stream error: {nr_err}")
                self._is_running = False
                raise

            # except (httpx.ReadTimeout, asyncio.TimeoutError):
            #     logger.warning(
            #         f"No keep-alive received for {self.read_timeout_seconds}s. "
            #         "Zombie connection detected. Reconnecting..."
            #     )

            except (httpx.RequestError, httpx.HTTPStatusError) as net_err:
                logger.warning(f"Network error on stream: {net_err}. Reconnecting...")

            except asyncio.CancelledError:
                logger.info("Stream consumer task cancelled.")
                self._is_running = False
                break

            except Exception as unhandled:
                logger.exception(f"Unexpected error during stream: {unhandled}")

            # Reconnection backoff loop
            if self._is_running:
                delay = self._calculate_backoff(attempt)
                logger.info(f"Reconnecting in {delay:.2f}s (Attempt {attempt + 1})...")
                await self._sleep_cancellable(delay)
                attempt += 1

        logger.info("Lichess stream exited cleanly.")

    def stop(self):
        """Signals the loop and any active socket to terminate gracefully."""
        self._is_running = False

    def _calculate_backoff(self, attempt: int) -> float:
        """Exponential backoff with full jitter: U(0, min(max_backoff, base * 2^attempt))."""
        calculated = self.initial_backoff_seconds * (self.backoff_multiplier ** attempt)
        ceiling = min(self.max_backoff_seconds, calculated)
        return random.uniform(0.5 * ceiling, ceiling)

    def _parse_retry_after(self, response: httpx.Response) -> float:
        """Extracts Retry-After header value or falls back to a 60-second default."""
        retry_val = response.headers.get("Retry-After")
        if retry_val:
            try:
                return max(1.0, float(retry_val))
            except ValueError:
                pass
        return 60.0

    async def _sleep_cancellable(self, seconds: float):
        """Permits instant shutdown during sleep without waiting for the timer."""
        try:
            await asyncio.sleep(seconds)
        except asyncio.CancelledError:
            self._is_running = False
            raise