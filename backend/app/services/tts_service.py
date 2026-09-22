# backend/app/services/tts_service.py

import asyncio
import logging
import os
import re
import shutil
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import aiohttp

from app.config import BACKEND_DIR, settings
from app.commentary.schemas import (
    CommentaryEmotion,
    CommentaryExchange,
    CommentatorRole,
    DialogueTurn,
    SpeakingDynamic,
)

logger = logging.getLogger(__name__)

# Default audio output directory
DEFAULT_AUDIO_DIR = BACKEND_DIR / "static" / "audio"

# ElevenLabs Production Voices
# Antoni: Energetic, clear, fast play-by-play
DEFAULT_HOST_VOICE_ID = "D11AWvkESE7DJwqIVi7L"
# Daniel: Authoritative, calm, analytical grandmaster
DEFAULT_ANALYST_VOICE_ID = "onwK4e9ZLuTAKqWW03F9"

# Fast, low-latency model optimized for real-time broadcast streaming
DEFAULT_ELEVEN_MODEL = "eleven_turbo_v2_5"

# Emotion to ElevenLabs VoiceSettings mapping
# (stability, similarity_boost, style)
EMOTION_VOICE_SETTINGS: Dict[CommentaryEmotion, Tuple[float, float, float, float]] = {
    #                               stability, similarity, style, speed
    CommentaryEmotion.NEUTRAL:    (0.55,      0.75,       0.20,  1.12),
    CommentaryEmotion.ANALYTICAL: (0.65,      0.80,       0.15,  1.08),
    CommentaryEmotion.TENSE:      (0.35,      0.75,       0.60,  1.16),
    CommentaryEmotion.SHOCKED:    (0.22,      0.85,       0.85,  1.20),  # Max allowed by API
    CommentaryEmotion.EXCITED:    (0.28,      0.80,       0.75,  1.20),  # Max allowed by API
    CommentaryEmotion.HUMOROUS:   (0.45,      0.75,       0.40,  1.10),
}
GLOBAL_SPEED_MULTIPLIER: float = 1.08  # Adjust this one value to speed up or slow down everything

class TTSService:
    """
    Asynchronous Text-to-Speech synthesis service using ElevenLabs.
    Converts DialogueTurn text into broadcast-ready audio clips with
    emotional expression, interrupt handling, and playback backpressure tracking.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        host_voice_id: Optional[str] = None,
        analyst_voice_id: Optional[str] = None,
        model_id: str = DEFAULT_ELEVEN_MODEL,
        output_dir: Optional[Path] = None,
    ):
        self.api_key = (
            api_key
            or os.getenv("ELEVENLABS_API_KEY")
            or getattr(settings, "elevenlabs_api_key", None)
        )
        self.host_voice_id = (
            host_voice_id
            or os.getenv("ELEVENLABS_HOST_VOICE_ID")
            or getattr(settings, "elevenlabs_host_voice_id", None)
            or DEFAULT_HOST_VOICE_ID
        )
        self.analyst_voice_id = (
            analyst_voice_id
            or os.getenv("ELEVENLABS_ANALYST_VOICE_ID")
            or getattr(settings, "elevenlabs_analyst_voice_id", None)
            or DEFAULT_ANALYST_VOICE_ID
        )
        self.model_id = (
            os.getenv("ELEVENLABS_MODEL_ID")
            or getattr(settings, "elevenlabs_model_id", None)
            or model_id
        )

        self.output_dir = output_dir or DEFAULT_AUDIO_DIR
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.cleanup_old_audio()

        # Backpressure & lifecycle tracking
        self.pending_audio_seconds: float = 0.0
        self._interrupt_epoch: int = 0
        self._active_tasks: List[asyncio.Task] = []
        self._lock = asyncio.Lock()

        if not self.api_key:
            logger.warning(
                "ELEVENLABS_API_KEY not found. TTS service will generate dummy audio metadata without API calls."
            )

    def cleanup_old_audio(self, max_age_hours: int = 24) -> int:
        """
        Prunes session audio directories older than max_age_hours to prevent unbounded disk usage.
        Returns number of deleted directories/files.
        """
        now = time.time()
        deleted_count = 0
        cutoff = now - (max_age_hours * 3600)
        try:
            for item in self.output_dir.iterdir():
                try:
                    if item.is_dir():
                        mtime = item.stat().st_mtime
                        if mtime < cutoff:
                            shutil.rmtree(item, ignore_errors=True)
                            deleted_count += 1
                    elif item.is_file() and item.suffix == ".mp3":
                        if item.stat().st_mtime < cutoff:
                            item.unlink(missing_ok=True)
                            deleted_count += 1
                except Exception:
                    continue
            if deleted_count > 0:
                logger.info(f"Cleaned up {deleted_count} stale audio sessions/files from storage.")
        except Exception as exc:
            logger.debug(f"Audio cleanup note: {exc}")
        return deleted_count

    # ==========================================================================
    # Voice & Parameter Resolution
    # ==========================================================================

    def _get_voice_id(self, speaker: CommentatorRole) -> str:
        """Resolves the configured voice ID for the speaker persona."""
        if speaker == CommentatorRole.HOST:
            return self.host_voice_id
        return self.analyst_voice_id

    def _get_voice_settings(
        self,
        emotion: CommentaryEmotion,
        speaker: Optional[CommentatorRole] = None,
    ) -> Dict[str, float]:
        """Calculates ElevenLabs voice settings according to emotional posture and speaker role."""
        stability, similarity_boost, style, base_speed = EMOTION_VOICE_SETTINGS.get(
            emotion, (0.50, 0.75, 0.25, 1.15)
        )
        
        # Host (Antoni) has a naturally brisk and energetic cadence.
        # Calibrate Host speed with a 0.88 factor so their pace sounds natural, articulate,
        # and perfectly matches Analyst Peter's cadence (which is praised as perfect).
        speed_factor = 0.88 if speaker == CommentatorRole.HOST else 1.0
        calculated_speed = base_speed * GLOBAL_SPEED_MULTIPLIER * speed_factor

        # Strictly clamp between ElevenLabs API limits: 0.70 and 1.20
        adjusted_speed = min(max(round(calculated_speed, 2), 0.70), 1.20)

        return {
            "stability": stability,
            "similarity_boost": similarity_boost,
            "style": style,
            "speed": adjusted_speed,
        }

    # ==========================================================================
    # Interrupt Management
    # ==========================================================================

    def trigger_interrupt(self) -> None:
        """
        Cancels in-flight audio synthesis tasks and clears pending audio time
        when a high-priority tactical event (blunder/brilliant) occurs.
        """
        self._interrupt_epoch += 1
        self.pending_audio_seconds = 0.0

        for task in self._active_tasks:
            if not task.done():
                task.cancel()
        self._active_tasks.clear()

        logger.info(f"TTS audio interrupt triggered (epoch: {self._interrupt_epoch}). Audio queue cleared.")

    def consume_audio(self, duration_seconds: float) -> None:
        """Reduces the pending audio queue duration as audio completes playback."""
        self.pending_audio_seconds = max(0.0, self.pending_audio_seconds - duration_seconds)

    # ==========================================================================
    # Core Audio Synthesis
    # ==========================================================================

    async def synthesize_turn(
        self,
        turn: DialogueTurn,
        game_id: str,
        ply: int,
        turn_index: int = 0,
    ) -> DialogueTurn:
        """
        Synthesizes audio for a single DialogueTurn.
        Updates turn.audio_url and turn.estimated_duration_seconds.
        """
        if not turn.text.strip():
            return turn

        # Dry-run fallback if no API key configured
        if not self.api_key:
            duration = max(1.2, round(len(turn.text.split()) / 2.5, 2))
            turn.estimated_duration_seconds = duration
            turn.audio_url = None
            async with self._lock:
                self.pending_audio_seconds += duration
            return turn

        current_epoch = self._interrupt_epoch
        voice_id = self._get_voice_id(turn.speaker)
        voice_settings = self._get_voice_settings(turn.emotion, speaker=turn.speaker)

        # Output filename: {output_dir}/{safe_game_id}/ply{ply:03d}_{turn_index}_{speaker}.mp3
        clean_speaker = turn.speaker.value.lower()
        safe_game_id = re.sub(r'[^a-zA-Z0-9_\-]', '_', game_id)
        game_audio_dir = self.output_dir / safe_game_id
        game_audio_dir.mkdir(parents=True, exist_ok=True)

        file_name = f"ply{ply:03d}_{turn_index}_{clean_speaker}.mp3"
        file_path = game_audio_dir / file_name
        audio_url = f"/static/audio/{safe_game_id}/{file_name}"

        url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
        headers = {
            "xi-api-key": self.api_key,
            "Content-Type": "application/json",
            "Accept": "audio/mpeg",
        }
        payload = {
            "text": turn.text,
            "model_id": self.model_id,
            "voice_settings": voice_settings,
        }

        t0 = time.perf_counter()
        try:
            timeout = aiohttp.ClientTimeout(total=8.0)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(url, json=payload, headers=headers) as resp:
                    if resp.status != 200:
                        error_text = await resp.text()
                        logger.error(
                            f"ElevenLabs TTS failed (HTTP {resp.status}) for '{turn.speaker.value}': {error_text[:200]}"
                        )
                        # Fallback to word-count duration on failure
                        turn.estimated_duration_seconds = max(1.2, round(len(turn.text.split()) / 2.5, 2))
                        return turn

                    audio_bytes = await resp.read()

            # Abort write if an interrupt arrived while network request was in-flight
            if current_epoch != self._interrupt_epoch:
                logger.debug(f"Discarding obsolete TTS audio for Ply {ply} due to newer interrupt.")
                return turn

            # Write MP3 file to disk
            await asyncio.to_thread(file_path.write_bytes, audio_bytes)
            elapsed_ms = (time.perf_counter() - t0) * 1000

            # Calculate duration (128 kbps MP3 = 16,000 bytes/second)
            duration_sec = max(0.8, round(len(audio_bytes) / 16000.0, 2))

            turn.audio_url = audio_url
            turn.estimated_duration_seconds = duration_sec

            async with self._lock:
                self.pending_audio_seconds += duration_sec

            logger.info(
                f"TTS generated: {file_name} ({duration_sec}s) at {file_path.resolve()}"
            )

        except asyncio.CancelledError:
            logger.debug(f"TTS synthesis cancelled for Ply {ply}")
            raise
        except Exception as exc:
            logger.error(f"TTS synthesis exception: {exc}")
            turn.estimated_duration_seconds = max(1.2, round(len(turn.text.split()) / 2.5, 2))

        return turn

    async def synthesize_exchange(
        self,
        exchange: CommentaryExchange,
        game_id: str,
    ) -> CommentaryExchange:
        """
        Synthesizes all dialogue turns within a CommentaryExchange.
        Handles interrupts before synthesis if flagged.
        """
        if exchange.dynamic == SpeakingDynamic.SILENCE or not exchange.turns:
            return exchange

        # Preempt queue if this exchange is a priority interrupt
        if exchange.is_interrupt:
            self.trigger_interrupt()

        task = asyncio.create_task(self._process_exchange(exchange, game_id))
        self._active_tasks.append(task)

        try:
            await task
        finally:
            if task in self._active_tasks:
                self._active_tasks.remove(task)

        return exchange

    async def _process_exchange(
        self,
        exchange: CommentaryExchange,
        game_id: str,
    ) -> CommentaryExchange:
        """Synthesizes turns sequentially to guarantee chronological playback ordering."""
        for idx, turn in enumerate(exchange.turns):
            await self.synthesize_turn(
                turn=turn,
                game_id=game_id,
                ply=exchange.ply,
                turn_index=idx,
            )
        return exchange


# ==============================================================================
# Standalone CLI Verification
# ==============================================================================

async def main():
    print("Testing ElevenLabs TTS Service...")
    tts = TTSService()

    test_turns = [
        DialogueTurn(
            speaker=CommentatorRole.HOST,
            text="Queen to b6 from Black! James, does White have a window to strike here?",
            emotion=CommentaryEmotion.EXCITED,
            priority=2,
        ),
        DialogueTurn(
            speaker=CommentatorRole.ANALYST,
            text="White can simply castle to safety. If they do, look for knight to a4 next, trapping the queen.",
            emotion=CommentaryEmotion.ANALYTICAL,
            priority=2,
        ),
    ]

    test_exchange = CommentaryExchange(
        ply=24,
        move_san="Qb6",
        turn_color="black",
        dynamic=SpeakingDynamic.BANTER,
        priority=2,
        turns=test_turns,
        is_interrupt=False,
    )

    result = await tts.synthesize_exchange(test_exchange, game_id="test_game")

    print("\nSynthesis Completed:")
    for turn in result.turns:
        print(f"- [{turn.speaker.value}] ({turn.emotion.value}): {turn.text}")
        print(f"  Audio URL: {turn.audio_url} | Duration: {turn.estimated_duration_seconds}s")

    print(f"\nPending audio duration: {tts.pending_audio_seconds}s")
    print(f"Files saved in: {tts.output_dir.resolve()}")


if __name__ == "__main__":
    asyncio.run(main())