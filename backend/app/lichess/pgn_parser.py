import io
import json
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Union
import chess
import chess.pgn


@dataclass
class PlayerInfo:
    username: str
    rating: Optional[int] = None
    title: Optional[str] = None


@dataclass
class GameMetadata:
    game_id: str
    speed: str
    variant: str
    rated: bool
    white_player: PlayerInfo
    black_player: PlayerInfo
    event_name: Optional[str] = None


@dataclass
class ParsedMoveEvent:
    ply: int
    turn: str                       # "white" | "black"
    uci: str                        # e.g., "g1f3"
    san: str                        # e.g., "Nf3"
    fen: str                        # Current board FEN
    move_time_spent_seconds: float  # Think time on this move
    white_clock_seconds: Optional[float]
    black_clock_seconds: Optional[float]
    is_check: bool
    is_checkmate: bool
    is_stalemate: bool
    is_draw: bool
    is_time_trouble: bool           # Clock fell below threshold
    termination_reason: Optional[str] = None
    acting_player: Optional[str] = None


@dataclass
class GameTerminationEvent:
    game_id: str
    status: str                     # "resign", "outoftime", "mate", "draw", etc.
    winner: Optional[str]           # "white", "black", or None
    termination_reason: str         # Human-readable conclusion summary
    fen: Optional[str] = None
    turns: Optional[int] = None


@dataclass
class PonderingEvent:
    ply: int
    turn: str                       # "white" | "black"
    acting_player: str
    fen: str                        # Current board FEN being contemplated
    elapsed_think_seconds: float
    white_clock_seconds: Optional[float] = None
    black_clock_seconds: Optional[float] = None


class ChessStateTracker:
    """
    Manages board state, move validation, clock delta tracking,
    and line-by-line parsing for Lichess live NDJSON streams and FIDE broadcasts.
    """

    CLOCK_REGEX = re.compile(r"\[%clk\s+(\d+):(\d+):([\d\.]+)\]")
    TERMINAL_STATUSES = {
        "resign",
        "mate",
        "outoftime",
        "timeout",
        "draw",
        "stalemate",
        "aborted",
        "cheat",
        "noStart",
        "unknownFinish",
    }

    def __init__(
        self,
        initial_fen: str = chess.STARTING_FEN,
        time_trouble_threshold_seconds: float = 30.0,
        increment_seconds: float = 0.0,
    ):
        self.board = chess.Board(fen=initial_fen)
        self.time_trouble_threshold = time_trouble_threshold_seconds
        self.increment_seconds = increment_seconds

        # Metadata
        self.metadata: Optional[GameMetadata] = None

        # State tracking
        self.processed_ply: int = 0
        self.last_white_clock: Optional[float] = None
        self.last_black_clock: Optional[float] = None

    def parse_lichess_line(
        self, raw_line: Union[str, Dict[str, Any]]
    ) -> Optional[Union[GameMetadata, ParsedMoveEvent, GameTerminationEvent]]:
        if isinstance(raw_line, str):
            line = raw_line.strip()
            if not line:
                return None
            data = json.loads(line)
        else:
            data = raw_line

        event_type = data.get("type")

        # 1. Detect Game Status / Termination
        status_data = data.get("status")
        status_name = None
        if isinstance(status_data, dict):
            status_name = status_data.get("name")
        elif isinstance(status_data, str):
            status_name = status_data

        # Initialize metadata if present on this payload
        if "players" in data and "id" in data and isinstance(data.get("players"), dict):
            if self.metadata is None:
                self.metadata = self._build_metadata(data)

        # If the packet contains a terminal state (resign, timeout, etc.)
        if status_name and status_name.lower() in self.TERMINAL_STATUSES:
            winner = data.get("winner")
            termination_reason = self._format_status_termination(status_name.lower(), winner)
            return GameTerminationEvent(
                game_id=data.get("id", self.metadata.game_id if self.metadata else ""),
                status=status_name,
                winner=winner,
                termination_reason=termination_reason,
                fen=data.get("fen", self.board.fen()),
                turns=data.get("turns", self.processed_ply),
            )

        # 2. Board API Initial Setup ("gameFull") or stream init line
        if event_type == "gameFull" or ("players" in data and "id" in data):
            initial_state = data.get("state") if isinstance(data.get("state"), dict) else {}
            wc = initial_state.get("wtime") or data.get("wc")
            bc = initial_state.get("btime") or data.get("bc")
            if wc is not None:
                self.last_white_clock = float(wc) / 1000.0 if float(wc) > 1000 else float(wc)
            if bc is not None:
                self.last_black_clock = float(bc) / 1000.0 if float(bc) > 1000 else float(bc)

            return self.metadata

        # 3. Board API Incremental Update ("gameState")
        if event_type == "gameState" or "moves" in data:
            moves_str = data.get("moves", "").strip()
            move_list = moves_str.split() if moves_str else []

            if len(move_list) > self.processed_ply:
                latest_uci = move_list[-1]
                wc, bc = self._extract_clocks(data)
                return self.push_uci(
                    uci_str=latest_uci,
                    white_clock_seconds=wc,
                    black_clock_seconds=bc,
                )
            return None

        # 4. Public Stream Move Chunks ("lm")
        if "lm" in data:
            uci_str = data["lm"]
            wc, bc = self._extract_clocks(data)
            return self.push_uci(
                uci_str=uci_str,
                white_clock_seconds=wc,
                black_clock_seconds=bc,
                authoritative_fen=data.get("fen"),
            )

        return None

    def push_uci(
        self,
        uci_str: str,
        white_clock_seconds: Optional[float] = None,
        black_clock_seconds: Optional[float] = None,
        authoritative_fen: Optional[str] = None,
    ) -> ParsedMoveEvent:
        """
        Pushes a single UCI move, calculates time deltas, checks for time-trouble,
        and resyncs internal board state against authoritative FEN if needed.
        """
        move = chess.Move.from_uci(uci_str)

        if move not in self.board.legal_moves:
            if authoritative_fen:
                self.board = chess.Board(authoritative_fen)
                if move not in self.board.legal_moves:
                    raise ValueError(f"Move '{uci_str}' remains illegal after FEN resync.")
            else:
                raise ValueError(f"Illegal move '{uci_str}' for board {self.board.fen()}")

        turn_color = "white" if self.board.turn == chess.WHITE else "black"
        san_str = self.board.san(move)

        move_time_spent = self._calculate_time_spent(
            turn_color=turn_color,
            curr_white_s=white_clock_seconds,
            curr_black_s=black_clock_seconds,
        )

        if white_clock_seconds is not None:
            self.last_white_clock = white_clock_seconds
        if black_clock_seconds is not None:
            self.last_black_clock = black_clock_seconds

        self.board.push(move)
        self.processed_ply += 1

        if authoritative_fen:
            if self.board.fen().split()[0] != authoritative_fen.split()[0]:
                self.board = chess.Board(authoritative_fen)

        active_clock = white_clock_seconds if turn_color == "white" else black_clock_seconds
        is_time_trouble = (
            active_clock is not None and active_clock <= self.time_trouble_threshold
        )

        acting_player = None
        if self.metadata:
            acting_player = (
                self.metadata.white_player.username
                if turn_color == "white"
                else self.metadata.black_player.username
            )

        return ParsedMoveEvent(
            ply=self.processed_ply,
            turn=turn_color,
            uci=uci_str,
            san=san_str,
            fen=self.board.fen(),
            move_time_spent_seconds=max(0.0, round(move_time_spent, 2)),
            white_clock_seconds=white_clock_seconds,
            black_clock_seconds=black_clock_seconds,
            is_check=self.board.is_check(),
            is_checkmate=self.board.is_checkmate(),
            is_stalemate=self.board.is_stalemate(),
            is_draw=self.board.is_game_over() and not self.board.is_checkmate(),
            is_time_trouble=is_time_trouble,
            termination_reason=self._detect_termination(),
            acting_player=acting_player,
        )

    def parse_pgn_stream_chunk(self, pgn_text: str) -> List[ParsedMoveEvent]:
        """Parses raw PGN broadcast relays."""
        game = chess.pgn.read_game(io.StringIO(pgn_text))
        if not game:
            return []

        board = game.board()
        events: List[ParsedMoveEvent] = []
        current_node = game
        current_ply = 0

        while current_node.variations:
            next_node = current_node.variation(0)
            move = next_node.move
            current_ply += 1

            turn_color = "white" if board.turn == chess.WHITE else "black"
            white_s, black_s = self._extract_clock_from_comment(next_node.comment, turn_color)

            if current_ply > self.processed_ply:
                san_str = board.san(move)
                move_time_spent = self._calculate_time_spent(
                    turn_color=turn_color,
                    curr_white_s=white_s,
                    curr_black_s=black_s,
                )

                board.push(move)
                self.board = board.copy()
                self.processed_ply = current_ply

                if white_s is not None:
                    self.last_white_clock = white_s
                if black_s is not None:
                    self.last_black_clock = black_s

                active_clock = white_s if turn_color == "white" else black_s
                is_time_trouble = (
                    active_clock is not None and active_clock <= self.time_trouble_threshold
                )

                events.append(
                    ParsedMoveEvent(
                        ply=self.processed_ply,
                        turn=turn_color,
                        uci=move.uci(),
                        san=san_str,
                        fen=board.fen(),
                        move_time_spent_seconds=max(0.0, round(move_time_spent, 2)),
                        white_clock_seconds=white_s,
                        black_clock_seconds=black_s,
                        is_check=board.is_check(),
                        is_checkmate=board.is_checkmate(),
                        is_stalemate=board.is_stalemate(),
                        is_draw=board.is_game_over() and not board.is_checkmate(),
                        is_time_trouble=is_time_trouble,
                        termination_reason=self._detect_termination(),
                    )
                )
            else:
                board.push(move)

            current_node = next_node

        return events

    def _build_metadata(self, data: Dict[str, Any]) -> GameMetadata:
        players_data = data.get("players", {})
        white_data = players_data.get("white", {}) if isinstance(players_data, dict) else {}
        black_data = players_data.get("black", {}) if isinstance(players_data, dict) else {}

        # Speed handling
        speed = data.get("speed")
        if not speed:
            perf = data.get("perf")
            if isinstance(perf, dict):
                speed = perf.get("name", "unknown")
            elif isinstance(perf, str):
                speed = perf
            else:
                speed = "unknown"

        # Variant handling
        variant_data = data.get("variant")
        if isinstance(variant_data, dict):
            variant_str = variant_data.get("key", "standard")
        elif isinstance(variant_data, str):
            variant_str = variant_data
        else:
            variant_str = "standard"

        # Event name resolution
        event_name = (
            data.get("event")
            or data.get("tournament")
            or f"Lichess {str(speed).capitalize()}"
        )

        return GameMetadata(
            game_id=str(data.get("id", "")),
            speed=str(speed),
            variant=str(variant_str),
            rated=bool(data.get("rated", False)),
            white_player=self._parse_player(white_data, fallback_name="White"),
            black_player=self._parse_player(black_data, fallback_name="Black"),
            event_name=event_name,
        )

    @staticmethod
    def _parse_player(player_data: Any, fallback_name: str) -> PlayerInfo:
        """Safely parses player structure whether AI, registered user, or guest."""
        if not isinstance(player_data, dict):
            return PlayerInfo(username=fallback_name)

        if "aiLevel" in player_data:
            return PlayerInfo(
                username=f"Stockfish Level {player_data['aiLevel']}",
                rating=None,
                title="BOT",
            )

        user_obj = player_data.get("user")
        if isinstance(user_obj, dict):
            return PlayerInfo(
                username=str(user_obj.get("name") or user_obj.get("id") or fallback_name),
                rating=player_data.get("rating"),
                title=user_obj.get("title") or player_data.get("title"),
            )

        username = player_data.get("name") or player_data.get("username") or fallback_name
        return PlayerInfo(
            username=str(username),
            rating=player_data.get("rating"),
            title=player_data.get("title"),
        )

    @staticmethod
    def _format_status_termination(status_name: str, winner: Optional[str]) -> str:
        winner_name = winner.capitalize() if winner else None
        loser_name = "Black" if winner == "white" else ("White" if winner == "black" else None)

        if status_name == "resign":
            if winner_name and loser_name:
                return f"{loser_name} resigned - {winner_name} wins"
            return f"{winner_name} won by resignation" if winner_name else "Game resigned"
        if status_name in ("outoftime", "timeout"):
            if winner_name and loser_name:
                return f"{loser_name} forfeited on time - {winner_name} wins"
            return f"{winner_name} won on time" if winner_name else "Time forfeit"
        if status_name == "mate":
            return f"Checkmate - {winner_name} wins" if winner_name else "Checkmate"
        if status_name == "draw":
            return "Draw by mutual agreement"
        if status_name == "stalemate":
            return "Draw by stalemate"
        if status_name == "aborted":
            return "Game aborted"
        if status_name == "cheat":
            return f"{winner_name} won - opponent cheat detected" if winner_name else "Cheat detected"

        detail = f" - {winner_name} wins" if winner_name else ""
        return f"Game concluded ({status_name}){detail}"

    def _extract_clocks(self, data: Dict[str, Any]) -> tuple[Optional[float], Optional[float]]:
        wc: Optional[float] = None
        bc: Optional[float] = None

        if "wc" in data:
            wc = float(data["wc"])
        elif "wtime" in data:
            wc = float(data["wtime"]) / 1000.0

        if "bc" in data:
            bc = float(data["bc"])
        elif "btime" in data:
            bc = float(data["btime"]) / 1000.0

        return wc, bc

    def _calculate_time_spent(
        self,
        turn_color: str,
        curr_white_s: Optional[float],
        curr_black_s: Optional[float],
    ) -> float:
        if turn_color == "white":
            if self.last_white_clock is not None and curr_white_s is not None:
                return (self.last_white_clock - curr_white_s) + self.increment_seconds
        else:
            if self.last_black_clock is not None and curr_black_s is not None:
                return (self.last_black_clock - curr_black_s) + self.increment_seconds
        return 0.0

    def _extract_clock_from_comment(
        self, comment: str, turn_color: str
    ) -> tuple[Optional[float], Optional[float]]:
        match = self.CLOCK_REGEX.search(comment)
        if not match:
            return self.last_white_clock, self.last_black_clock

        hours, minutes, seconds = match.groups()
        total_seconds = int(hours) * 3600 + int(minutes) * 60 + float(seconds)

        if turn_color == "white":
            return total_seconds, self.last_black_clock
        return self.last_white_clock, total_seconds

    def _detect_termination(self) -> Optional[str]:
        if self.board.is_checkmate():
            winner = "Black" if self.board.turn == chess.WHITE else "White"
            return f"Checkmate - {winner} wins"
        if self.board.is_stalemate():
            return "Draw by Stalemate"
        if self.board.is_insufficient_material():
            return "Draw by Insufficient Material"
        if self.board.is_fivefold_repetition():
            return "Draw by Fivefold Repetition"
        if self.board.is_seventyfive_moves():
            return "Draw by 75-move Rule"
        return None