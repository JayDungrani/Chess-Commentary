# backend/app/lichess/broadcast_streamer.py

import argparse
import asyncio
import io
import logging
import re
import sys
import time
from pathlib import Path
from typing import AsyncGenerator, List, Optional, Tuple, Union

import aiohttp
import chess
import chess.pgn
from pydantic import BaseModel, Field

CURRENT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = CURRENT_DIR.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.append(str(BACKEND_DIR))

from app.lichess.pgn_parser import GameMetadata, PlayerInfo, ParsedMoveEvent

try:
    from app.config import settings
    DEFAULT_USER_AGENT = getattr(settings, "lichess_user_agent", "LiveChessCommentary/1.0")
except ImportError:
    DEFAULT_USER_AGENT = "LiveChessCommentary/1.0"

logger = logging.getLogger(__name__)


class BroadcastGameSummary(BaseModel):
    game_id: str
    board: Optional[int] = None
    white_name: str
    white_title: Optional[str] = None
    white_elo: Optional[int] = None
    white_team: Optional[str] = None
    black_name: str
    black_title: Optional[str] = None
    black_elo: Optional[int] = None
    black_team: Optional[str] = None
    result: str = "*"
    status: str = "live"
    ply_count: int = 0
    current_fen: str = chess.STARTING_FEN
    url: Optional[str] = None
    event_name: Optional[str] = None
    round_name: Optional[str] = None


def extract_broadcast_ids(url_or_id: str) -> Tuple[str, Optional[str]]:
    clean = url_or_id.strip()
    if "lichess.org/broadcast" in clean:
        parts = [p for p in clean.split("/") if p and p not in ("https:", "http:", "lichess.org", "broadcast")]
        ids = [p for p in parts if re.match(r"^[a-zA-Z0-9]{8}$", p)]
        if len(ids) >= 2:
            return ids[0], ids[1]
        elif len(ids) == 1:
            return ids[0], None

    match = re.search(r"([a-zA-Z0-9]{8})", clean)
    if match:
        return match.group(1), None

    return clean, None


def parse_clock_seconds(comment: str) -> Optional[float]:
    match = re.search(r"\[%clk\s+([\d:.]+)\]", comment)
    if not match:
        return None
    raw_time = match.group(1)
    parts = raw_time.split(":")
    try:
        if len(parts) == 3:
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
        elif len(parts) == 2:
            return int(parts[0]) * 60 + float(parts[1])
        elif len(parts) == 1:
            return float(parts[0])
    except ValueError:
        return None
    return None


def extract_game_id_from_game(game: chess.pgn.Game) -> str:
    game_url = game.headers.get("GameURL", "")
    if game_url:
        tokens = game_url.rstrip("/").split("/")
        if tokens and len(tokens[-1]) == 8:
            return tokens[-1]

    site = game.headers.get("Site", "")
    if site and "http" in site:
        tokens = site.rstrip("/").split("/")
        if tokens and len(tokens[-1]) == 8:
            return tokens[-1]

    board = game.headers.get("Board")
    if board:
        return f"board-{board}"

    round_str = game.headers.get("Round", "")
    if round_str:
        return f"round-{round_str}"

    return f"{game.headers.get('White', 'white')}-{game.headers.get('Black', 'black')}".lower().replace(" ", "_")


def split_pgn_blocks(pgn_text: str) -> List[str]:
    """Splits a multi-game PGN cleanly between game blocks."""
    raw_blocks = re.split(r'\n+(?=\[Event\s+)', pgn_text.strip())
    return [b.strip() for b in raw_blocks if b.strip()]


class LichessBroadcastStreamer:
    BASE_URL = "https://lichess.org"

    def __init__(
        self,
        round_id: str,
        game_id: Optional[str] = None,
        poll_interval_seconds: float = 3.0,
        time_trouble_threshold_seconds: float = 30.0,
        user_agent: str = DEFAULT_USER_AGENT,
    ):
        extracted_round, extracted_game = extract_broadcast_ids(round_id)
        self._is_stopped = False
        self.round_id = extracted_round
        self.game_id = game_id or extracted_game
        self.poll_interval = poll_interval_seconds
        self.time_trouble_threshold = time_trouble_threshold_seconds
        self.user_agent = user_agent
        self._cached_initial_pgn: Optional[str] = None
        self._headers = {
            "User-Agent": self.user_agent,
            "Accept": "application/x-chess-pgn, text/plain",
        }

    def stop(self) -> None:
        self._is_stopped = True

    async def stream_events(self, *args, **kwargs):
        async for event in self.stream_game_events(*args, **kwargs):
            yield event

    async def stream_moves(self, *args, **kwargs):
        async for event in self.stream_game_events(*args, **kwargs):
            yield event

    def __aiter__(self):
        return self.stream_game_events()

    async def _fetch_round_pgn(self) -> str:
        """Fetches round PGN with generous timeout and caching."""
        if self._cached_initial_pgn:
            return self._cached_initial_pgn

        url = f"{self.BASE_URL}/api/broadcast/round/{self.round_id}.pgn"
        timeout = aiohttp.ClientTimeout(total=20.0)
        async with aiohttp.ClientSession(headers=self._headers, timeout=timeout) as session:
            async with session.get(url) as resp:
                if resp.status != 200:
                    text = await resp.text()
                    raise RuntimeError(f"Failed to fetch round PGN (HTTP {resp.status}): {text[:200]}")
                self._cached_initial_pgn = await resp.text()
                return self._cached_initial_pgn

    async def get_current_ply(self) -> int:
        """Finds target game in round PGN and returns its live ply count."""
        try:
            content = await self._fetch_round_pgn()
            target_clean = (self.game_id or "").strip().rstrip("/").split("/")[-1]

            for block in split_pgn_blocks(content):
                if target_clean.lower() in block.lower():
                    g = chess.pgn.read_game(io.StringIO(block))
                    if g and self._matches_target_game(g, target_clean):
                        return sum(1 for _ in g.mainline_moves())

            # Fallback if board number or player name was used
            for block in split_pgn_blocks(content):
                g = chess.pgn.read_game(io.StringIO(block))
                if g and self._matches_target_game(g, target_clean):
                    return sum(1 for _ in g.mainline_moves())

        except Exception as exc:
            logger.warning(f"Could not determine broadcast start ply ({exc}). Defaulting to move 1.")
        return 0

    async def list_games(self) -> List[BroadcastGameSummary]:
        pgn_content = await self._fetch_round_pgn()
        games_list: List[BroadcastGameSummary] = []
        for block in split_pgn_blocks(pgn_content):
            game = chess.pgn.read_game(io.StringIO(block))
            if not game:
                continue

            headers = game.headers
            gid = extract_game_id_from_game(game)
            board_num = None
            if headers.get("Board", "").isdigit():
                board_num = int(headers["Board"])
            elif headers.get("Round", ""):
                r_parts = headers["Round"].split(".")
                if len(r_parts) > 1 and r_parts[-1].isdigit():
                    board_num = int(r_parts[-1])

            board = game.board()
            ply = sum(1 for _ in game.mainline_moves())
            result = headers.get("Result", "*")
            status = "completed" if result in ("1-0", "0-1", "1/2-1/2") else "live"

            w_elo = int(headers["WhiteElo"]) if headers.get("WhiteElo", "").isdigit() else None
            b_elo = int(headers["BlackElo"]) if headers.get("BlackElo", "").isdigit() else None

            games_list.append(
                BroadcastGameSummary(
                    game_id=gid,
                    board=board_num,
                    white_name=headers.get("White", "Unknown"),
                    white_title=headers.get("WhiteTitle"),
                    white_elo=w_elo,
                    white_team=headers.get("WhiteTeam"),
                    black_name=headers.get("Black", "Unknown"),
                    black_title=headers.get("BlackTitle"),
                    black_elo=b_elo,
                    black_team=headers.get("BlackTeam"),
                    result=result,
                    status=status,
                    ply_count=ply,
                    current_fen=board.fen(),
                    url=headers.get("GameURL") or headers.get("Site"),
                    event_name=headers.get("Event"),
                    round_name=headers.get("Round"),
                )
            )

        games_list.sort(key=lambda g: g.board if g.board is not None else 9999)
        return games_list

    def _matches_target_game(self, game: chess.pgn.Game, target: str) -> bool:
        target_clean = target.strip().rstrip("/").split("/")[-1]
        target_lower = target_clean.lower()

        game_url = game.headers.get("GameURL", "").lower()
        if target_lower in game_url:
            return True

        site = game.headers.get("Site", "").lower()
        if target_lower in site:
            return True

        board = game.headers.get("Board", "")
        if target_clean == board or target_clean == f"board-{board}":
            return True

        round_val = game.headers.get("Round", "")
        if target_clean == round_val or round_val.endswith(f".{target_clean}"):
            return True

        white = game.headers.get("White", "").lower()
        black = game.headers.get("Black", "").lower()
        w_team = game.headers.get("WhiteTeam", "").lower()
        b_team = game.headers.get("BlackTeam", "").lower()

        return target_lower in white or target_lower in black or target_lower in w_team or target_lower in b_team

    async def stream_game_events(
        self,
        game_id: Optional[str] = None,
    ) -> AsyncGenerator[Union[GameMetadata, ParsedMoveEvent], None]:
        target = game_id or self.game_id
        if not target:
            raise ValueError("A game_id or board number must be specified to stream moves.")

        target_clean = target.strip().rstrip("/").split("/")[-1]
        initial_pgn = await self._fetch_round_pgn()

        target_game: Optional[chess.pgn.Game] = None
        for block in split_pgn_blocks(initial_pgn):
            if target_clean.lower() in block.lower():
                g = chess.pgn.read_game(io.StringIO(block))
                if g and self._matches_target_game(g, target_clean):
                    target_game = g
                    break

        if not target_game:
            for block in split_pgn_blocks(initial_pgn):
                g = chess.pgn.read_game(io.StringIO(block))
                if g and self._matches_target_game(g, target_clean):
                    target_game = g
                    break

        if not target_game:
            raise ValueError(f"Game matching '{target}' not found in round '{self.round_id}'.")

        headers = target_game.headers
        w_elo = int(headers["WhiteElo"]) if headers.get("WhiteElo", "").isdigit() else None
        b_elo = int(headers["BlackElo"]) if headers.get("BlackElo", "").isdigit() else None

        board_num = None
        if headers.get("Board", "").isdigit():
            board_num = int(headers["Board"])
        elif headers.get("Round", ""):
            r_parts = headers["Round"].split(".")
            if len(r_parts) > 1 and r_parts[-1].isdigit():
                board_num = int(r_parts[-1])

        metadata = GameMetadata(
            game_id=extract_game_id_from_game(target_game),
            speed="classical",
            variant="standard",
            rated=True,
            white_player=PlayerInfo(
                username=headers.get("White", "White"),
                title=headers.get("WhiteTitle"),
                rating=w_elo,
            ),
            black_player=PlayerInfo(
                username=headers.get("Black", "Black"),
                title=headers.get("BlackTitle"),
                rating=b_elo,
            ),
            event_name=headers.get("Event", headers.get("BroadcastName", "Lichess Broadcast")),
        )
        yield metadata

        # Emit moves from initial snapshot
        last_emitted_ply = 0
        white_player_name = metadata.white_player.username
        black_player_name = metadata.black_player.username

        async for event in self._extract_new_events(target_game, last_emitted_ply, white_player_name, black_player_name):
            last_emitted_ply = event.ply
            yield event

        result = target_game.headers.get("Result", "*")
        if result in ("1-0", "0-1", "1/2-1/2"):
            # Ensure the last event flags the game's official conclusion
            logger.info(f"Game {metadata.game_id} concluded with result: {result}")
            return

        async for event in self._poll_game_loop(target_clean, last_emitted_ply, white_player_name, black_player_name):
            yield event
        

    async def _poll_game_loop(
        self,
        target: str,
        last_emitted_ply: int,
        white_player: str,
        black_player: str,
    ) -> AsyncGenerator[ParsedMoveEvent, None]:
        poll_headers = {
            **self._headers,
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
        }

        async with aiohttp.ClientSession(headers=poll_headers) as session:
            while not self._is_stopped:
                await asyncio.sleep(self.poll_interval)
                try:
                    url = f"{self.BASE_URL}/api/broadcast/round/{self.round_id}.pgn?_={int(time.time() * 1000)}"
                    async with session.get(url, timeout=aiohttp.ClientTimeout(total=15.0)) as resp:
                        if resp.status != 200:
                            continue
                        content = await resp.text()

                    for block in split_pgn_blocks(content):
                        if target.lower() in block.lower():
                            game = chess.pgn.read_game(io.StringIO(block))
                            if game and self._matches_target_game(game, target):
                                async for event in self._extract_new_events(
                                    game, last_emitted_ply, white_player, black_player
                                ):
                                    last_emitted_ply = event.ply
                                    yield event

                                result = game.headers.get("Result", "*")
                                if result in ("1-0", "0-1", "1/2-1/2"):
                                    return
                                break
                except Exception as exc:
                    logger.debug(f"Poll error: {exc}")

    async def _extract_new_events(
        self,
        game: chess.pgn.Game,
        last_ply: int,
        white_player: str,
        black_player: str,
    ) -> AsyncGenerator[ParsedMoveEvent, None]:
        board = game.board()
        current_node = game
        ply = 0

        prev_w_clk: Optional[float] = None
        prev_b_clk: Optional[float] = None

        while current_node.variations:
            next_node = current_node.variation(0)
            move = next_node.move
            ply += 1

            turn_str = "white" if board.turn == chess.WHITE else "black"
            acting = white_player if turn_str == "white" else black_player

            san = board.san(move)
            uci = move.uci()
            board.push(move)

            clk = parse_clock_seconds(next_node.comment)
            w_clk = clk if turn_str == "white" else prev_w_clk
            b_clk = clk if turn_str == "black" else prev_b_clk

            move_time = 0.0
            if turn_str == "white" and prev_w_clk is not None and clk is not None:
                move_time = max(0.0, prev_w_clk - clk)
            elif turn_str == "black" and prev_b_clk is not None and clk is not None:
                move_time = max(0.0, prev_b_clk - clk)

            if turn_str == "white" and clk is not None:
                prev_w_clk = clk
            elif turn_str == "black" and clk is not None:
                prev_b_clk = clk

            if ply > last_ply:
                is_check = board.is_check()
                is_checkmate = board.is_checkmate()
                is_stalemate = board.is_stalemate()
                is_draw = board.is_game_over() and not is_checkmate

                active_clock = w_clk if turn_str == "white" else b_clk
                is_time_trouble = (
                    active_clock is not None and active_clock <= self.time_trouble_threshold
                )

                termination = None
                if not next_node.variations:
                    result = game.headers.get("Result", "*")
                    if result and result != "*":
                        termination = f"Game concluded ({result})"

                yield ParsedMoveEvent(
                    ply=ply,
                    turn=turn_str,
                    uci=uci,
                    san=san,
                    fen=board.fen(),
                    move_time_spent_seconds=round(move_time, 1),
                    white_clock_seconds=w_clk,
                    black_clock_seconds=b_clk,
                    is_check=is_check,
                    is_checkmate=is_checkmate,
                    is_stalemate=is_stalemate,
                    is_draw=is_draw,
                    is_time_trouble=is_time_trouble,
                    termination_reason=termination,
                    acting_player=acting,
                )

            current_node = next_node