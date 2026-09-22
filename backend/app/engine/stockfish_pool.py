# backend/app/engine/stockfish_pool.py

import asyncio
import logging
import os
import shutil
from pathlib import Path
from typing import Optional, List
import chess
import chess.engine

from app.config import settings, PROJECT_ROOT, BACKEND_DIR
from app.engine.schemas import EngineLine, PositionAnalysis
from app.engine.heuristics import cp_to_win_prob

logger = logging.getLogger(__name__)

# Global singleton storage
_global_engine_instance: Optional["StockfishEngine"] = None
_instance_init_lock = asyncio.Lock()

PIECE_VALUES = {
    chess.PAWN: 100,
    chess.KNIGHT: 320,
    chess.BISHOP: 330,
    chess.ROOK: 500,
    chess.QUEEN: 900,
    chess.KING: 0,
}


def find_stockfish_binary(configured_path: Optional[str] = None) -> Optional[str]:
    """
    Auto-discovers the Stockfish chess engine binary across platforms:
    1. Explicit configured path or STOCKFISH_PATH environment variable
    2. System PATH via shutil.which
    3. Common directory locations on Linux/Docker, macOS, and Windows
    """
    # 1. Check explicit path
    target = configured_path or os.getenv("STOCKFISH_PATH") or getattr(settings, "stockfish_path", None)
    if target:
        try:
            p = Path(target).expanduser().resolve()
            if p.is_file():
                return str(p)
        except Exception:
            pass

    # 2. Check system PATH
    bin_names = [
        "stockfish",
        "stockfish.exe",
        "stockfish-windows-x86-64-universal.exe",
        "stockfish-windows-x86-64-avx2.exe",
        "stockfish-windows-x86-64-modern.exe",
        "stockfish-ubuntu-x86-64-avx2",
        "stockfish-ubuntu-x86-64-modern",
    ]
    for name in bin_names:
        found = shutil.which(name)
        if found and os.path.isfile(found):
            return str(Path(found).resolve())

    # 3. Known platform locations
    candidate_locations = [
        # Linux / Docker
        Path("/usr/games/stockfish"),
        Path("/usr/bin/stockfish"),
        Path("/usr/local/bin/stockfish"),
        Path("/snap/bin/stockfish"),
        # macOS Homebrew
        Path("/opt/homebrew/bin/stockfish"),
        Path("/usr/local/bin/stockfish"),
        # Project-relative directories
        PROJECT_ROOT / "chess_engine",
        PROJECT_ROOT / "bin",
        BACKEND_DIR / "bin",
        # Windows user desktop or system roots
        Path.home() / "Desktop" / "RAG" / "chess_engine",
        Path(r"C:\stockfish"),
        Path(os.environ.get("PROGRAMFILES", r"C:\Program Files")) / "Stockfish",
    ]

    for loc in candidate_locations:
        if loc.is_file():
            return str(loc.resolve())
        elif loc.is_dir():
            for pattern in ["stockfish*", "*stockfish*.exe"]:
                for match in loc.rglob(pattern):
                    if match.is_file():
                        return str(match.resolve())

    return None


def _heuristic_evaluate_fen(fen: str, depth: int = 1, multipv: int = 3) -> PositionAnalysis:
    """Fallback static heuristic evaluation when Stockfish binary is unavailable."""
    board = chess.Board(fen)
    if board.is_checkmate():
        mate_in = 0 if board.turn == chess.WHITE else 1
        score_cp = None
    elif board.is_game_over():
        mate_in = None
        score_cp = 0
    else:
        mate_in = None
        white_mat = sum(len(board.pieces(p, chess.WHITE)) * val for p, val in PIECE_VALUES.items())
        black_mat = sum(len(board.pieces(p, chess.BLACK)) * val for p, val in PIECE_VALUES.items())
        score_cp = white_mat - black_mat

    win_prob = cp_to_win_prob(score_cp=score_cp, mate_in=mate_in)

    parsed_lines: List[EngineLine] = []
    legal_moves = list(board.legal_moves)
    for idx, move in enumerate(legal_moves[:multipv]):
        temp_b = board.copy()
        san = temp_b.san(move)
        temp_b.push(move)
        parsed_lines.append(
            EngineLine(
                rank=idx + 1,
                score_cp=score_cp,
                mate_in=mate_in,
                win_probability=win_prob,
                uci_moves=[move.uci()],
                san_moves=[san],
                depth=depth,
            )
        )

    top_line = parsed_lines[0] if parsed_lines else None
    return PositionAnalysis(
        fen=fen,
        depth=depth,
        lines=parsed_lines,
        score_cp=score_cp,
        mate_in=mate_in,
        win_probability=win_prob,
    )


class StockfishEngine:
    def __init__(
        self,
        binary_path: Optional[str] = None,
        multipv: int = settings.stockfish_multipv,
        depth: int = settings.stockfish_depth,
        movetime_ms: int = settings.stockfish_movetime_ms,
        threads: int = settings.stockfish_threads,
        hash_mb: int = settings.stockfish_hash_mb,
    ):
        self.binary_path = binary_path or find_stockfish_binary()
        self.multipv = multipv
        self.depth = depth
        self.movetime_ms = movetime_ms
        self.threads = threads
        self.hash_mb = hash_mb

        self._engine: Optional[chess.engine.SimpleEngine] = None
        self._lock = asyncio.Lock()
        self.is_available: bool = False

    @property
    def is_alive(self) -> bool:
        """Returns True if the engine process is running and responsive."""
        if not self.is_available or self._engine is None:
            return False
        try:
            # 1. Check asyncio subprocess transport exit code
            if hasattr(self._engine, "transport") and self._engine.transport is not None:
                return self._engine.transport.get_returncode() is None
            
            # 2. Check python-chess protocol returncode Future
            if hasattr(self._engine, "protocol") and hasattr(self._engine.protocol, "returncode"):
                return not self._engine.protocol.returncode.done()

            return True
        except Exception:
            return True

    async def start(self) -> None:
        """Launches the Stockfish engine process with non-crashing fallback."""
        if self.is_alive:
            return

        # Clean up any dead/zombie process reference before spawning
        if self._engine is not None:
            try:
                await asyncio.to_thread(self._engine.quit)
            except Exception:
                pass
            self._engine = None

        if not self.binary_path:
            self.binary_path = find_stockfish_binary()

        if not self.binary_path or not os.path.exists(self.binary_path):
            logger.warning(
                "Stockfish binary not located on system. StockfishEngine will operate in heuristic fallback mode."
            )
            self.is_available = False
            return

        try:
            logger.info(f"Spawning persistent Stockfish instance from '{self.binary_path}'...")
            self._engine = await asyncio.to_thread(
                chess.engine.SimpleEngine.popen_uci, self.binary_path
            )
            await asyncio.to_thread(
                self._engine.configure,
                {
                    "Threads": self.threads,
                    "Hash": self.hash_mb,
                },
            )
            self.is_available = True
            logger.info(
                f"Stockfish online: Threads={self.threads}, Hash={self.hash_mb}MB, MultiPV={self.multipv}"
            )
        except Exception as exc:
            logger.warning(
                f"Failed to start Stockfish process at '{self.binary_path}': {exc}. Switching to heuristic fallback mode."
            )
            self._engine = None
            self.is_available = False

    async def close(self) -> None:
        """Gracefully terminates the Stockfish process with fallback force kill."""
        if self._engine:
            try:
                await asyncio.wait_for(
                    asyncio.to_thread(self._engine.quit),
                    timeout=1.0
                )
            except Exception:
                try:
                    self._engine.close()
                except Exception:
                    pass
            finally:
                self._engine = None
                self.is_available = False
                logger.info("Stockfish engine shutdown complete.")

    async def analyze_position(
        self,
        fen: str,
        depth: Optional[int] = None,
        movetime_ms: Optional[int] = None,
    ) -> PositionAnalysis:
        target_depth = depth or self.depth
        time_limit = (movetime_ms or self.movetime_ms) / 1000.0

        if not self.is_alive:
            try:
                await self.start()
            except Exception:
                pass

        if not self.is_alive or self._engine is None:
            return _heuristic_evaluate_fen(fen, target_depth, self.multipv)

        board = chess.Board(fen=fen)
        limit = chess.engine.Limit(depth=target_depth, time=time_limit)

        # Mutex lock ensures concurrent LLM / AFC calls do not interleave UCI commands
        try:
            async with self._lock:
                assert self._engine is not None
                results = await asyncio.to_thread(
                    self._engine.analyse,
                    board,
                    limit,
                    multipv=self.multipv,
                )
        except Exception as exc:
            logger.warning(f"Engine analysis encountered error: {exc}. Using fallback.")
            return _heuristic_evaluate_fen(fen, target_depth, self.multipv)

        raw_lines = results if isinstance(results, list) else [results]
        parsed_lines: List[EngineLine] = []

        for idx, item in enumerate(raw_lines):
            score_obj = item.get("score")
            pv_moves = item.get("pv", [])
            depth_reached = item.get("depth", target_depth)

            score_cp: Optional[int] = None
            mate_in: Optional[int] = None

            if score_obj:
                score_white = score_obj.white()
                if score_white.is_mate():
                    mate_in = score_white.mate()
                else:
                    score_cp = score_white.score()

            win_prob = cp_to_win_prob(score_cp=score_cp, mate_in=mate_in)

            uci_moves: List[str] = []
            san_moves: List[str] = []
            replay_board = board.copy()

            for move in pv_moves:
                if move in replay_board.legal_moves:
                    san_moves.append(replay_board.san(move))
                    uci_moves.append(move.uci())
                    replay_board.push(move)
                else:
                    break

            parsed_lines.append(
                EngineLine(
                    rank=idx + 1,
                    score_cp=score_cp,
                    mate_in=mate_in,
                    win_probability=win_prob,
                    uci_moves=uci_moves,
                    san_moves=san_moves,
                    depth=depth_reached,
                )
            )

        top_line = parsed_lines[0] if parsed_lines else None
        return PositionAnalysis(
            fen=fen,
            depth=target_depth,
            lines=parsed_lines,
            score_cp=top_line.score_cp if top_line else None,
            mate_in=top_line.mate_in if top_line else None,
            win_probability=top_line.win_probability if top_line else 0.5,
        )


async def get_stockfish_engine() -> StockfishEngine:
    """Thread-safe singleton accessor."""
    global _global_engine_instance
    if _global_engine_instance is None or not _global_engine_instance.is_alive:
        async with _instance_init_lock:
            if _global_engine_instance is None or not _global_engine_instance.is_alive:
                engine = StockfishEngine()
                try:
                    await engine.start()
                except Exception as exc:
                    logger.warning(f"Could not initialize stockfish engine on startup: {exc}")
                _global_engine_instance = engine
    return _global_engine_instance


async def shutdown_stockfish_engine() -> None:
    """Explicit teardown hook for application exit."""
    global _global_engine_instance
    async with _instance_init_lock:
        if _global_engine_instance is not None:
            await _global_engine_instance.close()
            _global_engine_instance = None