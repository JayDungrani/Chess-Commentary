# backend/app/config.py

import os
import shutil
from pathlib import Path
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict

# Base directory paths
APP_DIR = Path(__file__).resolve().parent
BACKEND_DIR = APP_DIR.parent
PROJECT_ROOT = BACKEND_DIR.parent

class Settings(BaseSettings):
    """Application configuration supporting environment variables and .env files."""

    # Server Settings
    app_name: str = "Live Chess Commentary"
    environment: str = "development"
    debug: bool = True
    host: str = "0.0.0.0"
    port: int = 8000

    # Lichess Configuration
    lichess_api_token: Optional[str] = None
    time_trouble_threshold_seconds: float = 30.0

    # Pacing Buffer Settings
    fast_forward_initial_history: bool = True
    max_paced_move_delay_seconds: float = 45.0
    pacing_buffer_max_delay_bullet: float = 4.0
    pacing_buffer_max_delay_blitz: float = 15.0
    pacing_buffer_max_delay_rapid: float = 45.0
    pacing_buffer_max_delay_classical: float = 120.0

    # Stockfish Engine Settings
    stockfish_path: str = r"C:\Users\PRINCE\Desktop\RAG\chess_engine\stockfish-windows-x86-64-universal\stockfish\stockfish-windows-x86-64-universal.exe"
    stockfish_depth: int = 14
    stockfish_movetime_ms: int = 250
    stockfish_multipv: int = 3
    stockfish_threads: int = 2
    stockfish_hash_mb: int = 128

    # Opening Book Settings
    opening_book_path: Path = BACKEND_DIR / "assets" / "books" / "gm2001.bin"
    opening_book_min_weight: int = 1

    # Heuristic & Eval Swing Thresholds (Centipawns)
    blunder_threshold_cp: int = 200      # >= 2.0 pawn loss
    mistake_threshold_cp: int = 100      # >= 1.0 pawn loss
    inaccuracy_threshold_cp: int = 50    # >= 0.5 pawn loss

    # Win Probability Curve Constant
    win_prob_scaling: float = 400.0

    # LLM & TTS Settings
    openai_api_key: Optional[str] = None
    anthropic_api_key: Optional[str] = None
    elevenlabs_api_key: Optional[str] = None
    elevenlabs_analyst_voice_id: Optional[str] = None
    elevenlabs_host_voice_id: Optional[str] = None

    model_config = SettingsConfigDict(
        env_file=str(PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()