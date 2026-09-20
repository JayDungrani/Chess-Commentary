# backend/app/engine/stockfish_pool.py

import asyncio
import logging
from typing import Optional, List
import chess
import chess.engine

from app.config import settings
from app.engine.schemas import EngineLine, PositionAnalysis
from app.engine.heuristics import cp_to_win_prob

logger = logging.getLogger(__name__)

# Global singleton storage
_global_engine_instance: Optional["StockfishEngine"] = None
_instance_init_lock = asyncio.Lock()


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
        self.binary_path = binary_path or settings.stockfish_path
        self.multipv = multipv
        self.depth = depth
        self.movetime_ms = movetime_ms
        self.threads = threads
        self.hash_mb = hash_mb

        self._engine: Optional[chess.engine.SimpleEngine] = None
        self._lock = asyncio.Lock()

    @property
    def is_alive(self) -> bool:
        """Returns True if the engine process is running and responsive."""
        if self._engine is None:
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
            return True  # If the engine instance exists, assume alive to prevent runaway spawns

    async def start(self) -> None:
        """Launches the Stockfish engine process via a worker thread."""
        if self.is_alive:
            return

        # Clean up any dead/zombie process reference before spawning
        if self._engine is not None:
            try:
                await asyncio.to_thread(self._engine.quit)
            except Exception:
                pass
            self._engine = None

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
            logger.info(
                f"Stockfish online: Threads={self.threads}, Hash={self.hash_mb}MB, MultiPV={self.multipv}"
            )
        except Exception as exc:
            logger.error(f"Failed to start Stockfish process: {exc}")
            self._engine = None
            raise

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
                logger.info("Stockfish engine shutdown complete.")

    async def analyze_position(
        self,
        fen: str,
        depth: Optional[int] = None,
        movetime_ms: Optional[int] = None,
    ) -> PositionAnalysis:
        if not self.is_alive:
            await self.start()

        target_depth = depth or self.depth
        time_limit = (movetime_ms or self.movetime_ms) / 1000.0

        board = chess.Board(fen=fen)
        limit = chess.engine.Limit(depth=target_depth, time=time_limit)

        # Mutex lock ensures concurrent LLM / AFC calls do not interleave UCI commands
        async with self._lock:
            assert self._engine is not None
            results = await asyncio.to_thread(
                self._engine.analyse,
                board,
                limit,
                multipv=self.multipv,
            )

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
                await engine.start()
                _global_engine_instance = engine
    return _global_engine_instance


async def shutdown_stockfish_engine() -> None:
    """Explicit teardown hook for application exit."""
    global _global_engine_instance
    async with _instance_init_lock:
        if _global_engine_instance is not None:
            await _global_engine_instance.close()
            _global_engine_instance = None