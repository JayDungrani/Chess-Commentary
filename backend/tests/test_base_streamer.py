import asyncio
import pytest
import httpx
from unittest.mock import AsyncMock, patch, MagicMock

from app.lichess.base_streamer import BaseLichessStreamer, NonRetryableStreamError


class MockStreamer(BaseLichessStreamer):
    """Concrete implementation for test validation."""
    def __init__(self, target_url="https://lichess.org/api/mock/stream", **kwargs):
        super().__init__(**kwargs)
        self.url = target_url

    def get_endpoint_url(self) -> str:
        return self.url


@pytest.mark.asyncio
async def test_successful_line_streaming():
    streamer = MockStreamer()
    mock_lines = ["\n", '{"id":"game1"}', "\n\n", '{"lm":"e2e4"}', ""]

    async def mock_aiter_lines():
        for line in mock_lines:
            yield line

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.raise_for_status = MagicMock()
    mock_response.aiter_lines = mock_aiter_lines

    # Context manager setup
    mock_stream_ctx = AsyncMock()
    mock_stream_ctx.__aenter__.return_value = mock_response
    mock_stream_ctx.__aexit__.return_value = None

    with patch("httpx.AsyncClient.stream", return_value=mock_stream_ctx):
        collected = []
        async for line in streamer.stream_lines():
            collected.append(line)
            if len(collected) == 2:
                streamer.stop()

        # Whitespaces and empty newlines must be filtered out
        assert collected == ['{"id":"game1"}', '{"lm":"e2e4"}']


@pytest.mark.asyncio
async def test_404_terminal_error():
    streamer = MockStreamer()

    mock_response = MagicMock()
    mock_response.status_code = 404

    mock_stream_ctx = AsyncMock()
    mock_stream_ctx.__aenter__.return_value = mock_response
    mock_stream_ctx.__aexit__.return_value = None

    with patch("httpx.AsyncClient.stream", return_value=mock_stream_ctx):
        with pytest.raises(NonRetryableStreamError):
            async for _ in streamer.stream_lines():
                pass


@pytest.mark.asyncio
async def test_reconnect_on_read_timeout():
    """Simulates a zombie socket timing out once, then yielding a move after reconnection."""
    streamer = MockStreamer(initial_backoff_seconds=0.01, max_backoff_seconds=0.02)
    attempts = 0

    class DynamicStreamCtx:
        async def __aenter__(self):
            nonlocal attempts
            attempts += 1
            if attempts == 1:
                # First attempt hangs and times out
                raise httpx.ReadTimeout("No keep-alive received")
            
            # Second attempt succeeds
            res = MagicMock()
            res.status_code = 200
            res.raise_for_status = MagicMock()
            
            async def lines():
                yield '{"lm":"d2d4"}'
            
            res.aiter_lines = lines
            return res

        async def __aexit__(self, exc_type, exc, tb):
            pass

    with patch("httpx.AsyncClient.stream", return_value=DynamicStreamCtx()):
        collected = []
        async for line in streamer.stream_lines():
            collected.append(line)
            streamer.stop()

        assert attempts == 2
        assert collected == ['{"lm":"d2d4"}']