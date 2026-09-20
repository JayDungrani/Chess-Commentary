# backend/app/engine/opening_book.py

import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import chess
import chess.polyglot

from app.config import BACKEND_DIR, settings

logger = logging.getLogger(__name__)

DEFAULT_BOOK_PATH = BACKEND_DIR / "assets" / "books" / "gm2001.bin"

# Lightweight built-in ECO catalog for prominent opening names
# Maps ECO code -> (Name, Move Sequence)
COMMON_ECO_PATTERNS: Dict[str, Tuple[str, List[str]]] = {
    "B90": ("Sicilian Defense, Najdorf Variation", ["e4", "c5", "Nf3", "d6", "d4", "cxd4", "Nxd4", "Nf6", "Nc3", "a6"]),
    "B33": ("Sicilian Defense, Sveshnikov Variation", ["e4", "c5", "Nf3", "Nc6", "d4", "cxd4", "Nxd4", "Nf6", "Nc3", "e5"]),
    "B20": ("Sicilian Defense", ["e4", "c5"]),
    "C65": ("Ruy Lopez, Berlin Defense", ["e4", "e5", "Nf3", "Nc6", "Bb5", "Nf6"]),
    "C60": ("Ruy Lopez", ["e4", "e5", "Nf3", "Nc6", "Bb5"]),
    "C50": ("Italian Game", ["e4", "e5", "Nf3", "Nc6", "Bc4"]),
    "C42": ("Petrov's Defense", ["e4", "e5", "Nf3", "Nf6"]),
    "C00": ("French Defense", ["e4", "e6"]),
    "B10": ("Caro-Kann Defense", ["e4", "c6"]),
    "D06": ("Queen's Gambit", ["d4", "d5", "c4"]),
    "D30": ("Queen's Gambit Declined", ["d4", "d5", "c4", "e6"]),
    "D20": ("Queen's Gambit Accepted", ["d4", "d5", "c4", "dxc4"]),
    "E60": ("King's Indian Defense", ["d4", "Nf6", "c4", "g6"]),
    "E20": ("Nimzo-Indian Defense", ["d4", "Nf6", "c4", "e6", "Nc3", "Bb4"]),
    "A10": ("English Opening", ["c4"]),
    "A00": ("Uncommon Opening", []),
}


class OpeningBook:
    """
    Manages opening book lookups using Polyglot binary files (.bin).
    Calculates book validity via Zobrist hashing and resolves opening names.
    """

    def __init__(
        self,
        book_path: Optional[Path | str] = None,
        min_weight: int = 1,
    ):
        self.book_path = Path(book_path or getattr(settings, "stockfish_book_path", DEFAULT_BOOK_PATH))
        self.min_weight = min_weight
        self._reader: Optional[chess.polyglot.MemoryMappedReader] = None
        self._load_book()

    def _load_book(self) -> None:
        """Initializes the memory-mapped Polyglot book reader."""
        if not self.book_path.exists():
            logger.warning(
                f"Opening book not found at '{self.book_path}'. Book moves will be disabled."
            )
            self._reader = None
            return

        try:
            self._reader = chess.polyglot.open_reader(str(self.book_path))
            logger.info(f"Opening book loaded successfully from '{self.book_path}'.")
        except Exception as exc:
            logger.error(f"Failed to open Polyglot book at '{self.book_path}': {exc}")
            self._reader = None

    def close(self) -> None:
        """Closes the reader file descriptor."""
        if self._reader:
            self._reader.close()
            self._reader = None

    def is_book_move(self, board_before: chess.Board, move: chess.Move) -> bool:
        """
        Verifies if `move` played from `board_before` is present in the Polyglot book
        with weight >= min_weight.
        """
        if not self._reader:
            return False

        try:
            for entry in self._reader.find_all(board_before):
                if entry.move == move and entry.weight >= self.min_weight:
                    return True
        except Exception as exc:
            logger.debug(f"Polyglot lookup error: {exc}")
            return False

        return False

    def get_candidate_book_moves(self, board: chess.Board) -> List[Tuple[chess.Move, int]]:
        """
        Returns all valid book moves for the position sorted by weight descending.
        Returns a list of (Move, weight).
        """
        if not self._reader:
            return []

        try:
            entries = [
                (entry.move, entry.weight)
                for entry in self._reader.find_all(board)
                if entry.weight >= self.min_weight
            ]
            entries.sort(key=lambda x: x[1], reverse=True)
            return entries
        except Exception as exc:
            logger.debug(f"Failed to fetch candidate moves: {exc}")
            return []

    def identify_opening(self, played_sans: List[str]) -> Tuple[Optional[str], Optional[str]]:
        """
        Identifies the closest ECO code and Opening name based on played SAN sequence.
        Returns: (eco_code, opening_name)
        """
        best_match_eco: Optional[str] = None
        best_match_name: Optional[str] = None
        max_matched_length = -1

        for eco, (name, pattern) in COMMON_ECO_PATTERNS.items():
            if not pattern:
                continue
            pattern_len = len(pattern)
            if len(played_sans) >= pattern_len:
                if played_sans[:pattern_len] == pattern and pattern_len > max_matched_length:
                    max_matched_length = pattern_len
                    best_match_eco = eco
                    best_match_name = name

        return best_match_eco, best_match_name


class GameOpeningTracker:
    """
    Tracks stateful opening status across plies for a single game:
    detects when players leave theory (novelty / out-of-book).
    """

    def __init__(self, book: Optional[OpeningBook] = None):
        self.book = book or OpeningBook()
        self.in_book: bool = True
        self.out_of_book_ply: Optional[int] = None
        self.current_eco: Optional[str] = None
        self.current_opening_name: Optional[str] = None
        self.played_sans: List[str] = []

    def reset(self) -> None:
        """Resets tracker state for a new game."""
        self.in_book = True
        self.out_of_book_ply = None
        self.current_eco = None
        self.current_opening_name = None
        self.played_sans.clear()

    def process_move(
        self,
        board_before: chess.Board,
        move: chess.Move,
        move_san: str,
        ply: int,
    ) -> Tuple[bool, bool, Optional[str], Optional[str]]:
        """
        Evaluates the move against the book and tracks out-of-book transitions.

        Returns:
            is_book (bool): True if this move is in the book.
            left_book_now (bool): True if this was the first non-book move (novelty/out of book).
            eco (Optional[str]): Current identified ECO code.
            opening_name (Optional[str]): Current identified opening name.
        """
        self.played_sans.append(move_san)

        # Update opening name based on move sequence
        eco, name = self.book.identify_opening(self.played_sans)
        if eco and name:
            self.current_eco = eco
            self.current_opening_name = name

        if not self.in_book:
            return False, False, self.current_eco, self.current_opening_name

        is_book = self.book.is_book_move(board_before, move)

        left_book_now = False
        if not is_book:
            self.in_book = False
            self.out_of_book_ply = ply
            left_book_now = True

        return is_book, left_book_now, self.current_eco, self.current_opening_name