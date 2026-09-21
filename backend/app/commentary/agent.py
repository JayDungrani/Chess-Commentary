# backend/app/commentary/agent.py

import json
import logging
import os
import re
import time
from typing import List, Optional
from dotenv import load_dotenv

from google import genai
from google.genai import types

from app.config import settings
from app.commentary.schemas import (
    CommentaryContext,
    CommentaryExchange,
    DialogueTurn,
    CommentatorRole,
    CommentaryEmotion,
    SpeakingDynamic,
    CommentaryPriority,
    ThinkCategory,
)
from app.commentary.prompts import SYSTEM_PROMPT, build_commentary_prompt
from app.engine.schemas import MoveClassification

logger = logging.getLogger(__name__)
load_dotenv()

# Low-latency production model for real-time commentary
DEFAULT_GEMINI_MODEL = "gemini-3.1-flash-lite"


def san_to_spoken_move(san: str) -> str:
    """
    Converts standard algebraic notation (SAN) into a clean, spoken chess call.
    Examples:
        'Be6'     -> 'Bishop to e6.'
        'O-O'     -> 'Castles.'
        'O-O-O'   -> 'Castles queenside.'
        'Nxd5'    -> 'Knight takes on d5.'
        'exd5'    -> 'Takes on d5.'
        'Qh5+'    -> 'Queen to h5, check!'
        'Qxf7#'   -> 'Queen takes on f7, checkmate!'
        'e4'      -> 'e4.'
        'e8=Q'    -> 'Pawn promotes to Queen.'
    """
    if not san or san in ("...", "thinking...", "0000"):
        return "Move played."

    clean = san.strip().rstrip("!?")
    is_mate = clean.endswith("#")
    is_check = clean.endswith("+")
    clean = clean.rstrip("+#")

    # Castling
    if clean in ("O-O", "0-0"):
        suffix = ", checkmate!" if is_mate else (", check!" if is_check else ".")
        return f"Castles{suffix}"
    if clean in ("O-O-O", "0-0-0"):
        suffix = ", checkmate!" if is_mate else (", check!" if is_check else ".")
        return f"Castles queenside{suffix}"

    # Promotion
    prom_piece = None
    if "=" in clean:
        parts = clean.split("=")
        clean = parts[0]
        prom_piece = {"Q": "Queen", "R": "Rook", "B": "Bishop", "N": "Knight"}.get(parts[1], "Queen")

    # Check for capture
    is_capture = "x" in clean

    PIECE_NAMES = {
        "N": "Knight",
        "B": "Bishop",
        "R": "Rook",
        "Q": "Queen",
        "K": "King",
    }

    first_char = clean[0]
    if first_char in PIECE_NAMES:
        piece = PIECE_NAMES[first_char]
        dest_square = clean[-2:] if len(clean) >= 2 else ""
        if is_capture:
            spoken = f"{piece} takes on {dest_square}"
        else:
            spoken = f"{piece} to {dest_square}"
    else:
        # Pawn move
        if is_capture:
            dest_square = clean[-2:] if len(clean) >= 2 else ""
            if prom_piece:
                spoken = f"Takes on {dest_square}, promoting to {prom_piece}"
            else:
                spoken = f"Takes on {dest_square}"
        else:
            if prom_piece:
                spoken = f"Pawn promotes to {prom_piece}"
            else:
                dest_square = clean[-2:] if len(clean) >= 2 else clean
                spoken = dest_square

    if is_mate:
        spoken += ", checkmate!"
    elif is_check:
        spoken += ", check!"
    else:
        spoken += "."

    return spoken


class CommentaryAgent:
    """
    Asynchronous LLM agent using Google Gemini API.
    Transforms MoveEvaluation and BlunderDossier signals into dual-commentator
    broadcast dialogue (Host & Analyst) formatted strictly for TTS playback.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = DEFAULT_GEMINI_MODEL,
        temperature: float = 0.5,
        max_tokens: int = 500,
    ):
        self.api_key = (
            api_key
            or os.getenv("GEMINI_API_KEY")
            or os.getenv("GOOGLE_API_KEY")
            or getattr(settings, "gemini_api_key", None)
            or getattr(settings, "google_api_key", None)
        )

        self.model = (
            os.getenv("GEMINI_MODEL")
            or getattr(settings, "gemini_model", None)
            or model
        )
        self.temperature = temperature
        self.max_tokens = max_tokens

        if not self.api_key:
            logger.warning(
                "GEMINI_API_KEY / GOOGLE_API_KEY not found in settings or environment. "
                "Live commentary calls will fall back to local rule-based phrases."
            )
            self._client: Optional[genai.Client] = None
        else:
            self._client = genai.Client(api_key=self.api_key)

    async def generate_commentary(
        self,
        context: CommentaryContext,
    ) -> CommentaryExchange:
        eval_data = context.evaluation

        # 1. Deliberate Silence Guard
        if context.dynamic == SpeakingDynamic.SILENCE:
            return CommentaryExchange(
                ply=eval_data.ply,
                move_san=eval_data.played_san,
                turn_color=eval_data.turn,
                dynamic=SpeakingDynamic.SILENCE,
                priority=CommentaryPriority.BACKGROUND.value,
                turns=[],
                is_interrupt=False,
            )

        # 2. Priority & Interrupt Determination
        is_interrupt = False
        if eval_data.is_blunder or eval_data.classification == MoveClassification.BRILLIANT:
            priority = CommentaryPriority.INTERRUPT.value
            is_interrupt = True
        elif context.is_time_trouble:
            priority = CommentaryPriority.TIME_TROUBLE.value
        elif eval_data.classification in (MoveClassification.MISTAKE, MoveClassification.INACCURACY):
            priority = CommentaryPriority.TACTICAL.value
        else:
            priority = CommentaryPriority.NORMAL.value

        # 3. Fallback if API key is missing
        if not self._client:
            fallback_turns = self._generate_fallback_turns(context, priority)
            return CommentaryExchange(
                ply=eval_data.ply,
                move_san=eval_data.played_san,
                turn_color=eval_data.turn,
                dynamic=context.dynamic,
                priority=priority,
                turns=fallback_turns,
                is_interrupt=is_interrupt,
            )

        # 4. Build Prompt & Config
        user_prompt = build_commentary_prompt(context)
        gen_config = types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            response_mime_type="application/json",
            temperature=self.temperature,
            max_output_tokens=self.max_tokens,
        )

        t0 = time.perf_counter()
        try:
            response = await self._client.aio.models.generate_content(
                model=self.model,
                contents=user_prompt,
                config=gen_config,
            )
            elapsed_ms = (time.perf_counter() - t0) * 1000
            raw_content = response.text or "{}"
            logger.debug(f"Gemini [{self.model}] returned in {elapsed_ms:.1f}ms: {raw_content}")

            parsed_turns = self._parse_llm_json(raw_content, priority)

        except Exception as exc:
            logger.error(f"Gemini commentary generation failed ({exc}); falling back to template.")
            parsed_turns = self._generate_fallback_turns(context, priority)

        # 5. Populate Speech Metadata (~2.5 words per second)
        for turn in parsed_turns:
            word_count = len(turn.text.split())
            turn.estimated_duration_seconds = max(1.0, round(word_count / 2.5, 2))

        return CommentaryExchange(
            ply=eval_data.ply,
            move_san=eval_data.played_san,
            turn_color=eval_data.turn,
            dynamic=context.dynamic,
            priority=priority,
            turns=parsed_turns,
            is_interrupt=is_interrupt,
        )

    def _parse_llm_json(self, raw_json: str, priority: int) -> List[DialogueTurn]:
        """Sanitizes and parses JSON string safely."""
        clean_text = raw_json.strip()
        if clean_text.startswith("```"):
            clean_text = re.sub(r"^```[a-zA-Z]*\n?", "", clean_text)
            clean_text = re.sub(r"\n?```$", "", clean_text).strip()

        data = json.loads(clean_text)

        raw_turns = data.get("turns") or data.get("dialogue") or (data if isinstance(data, list) else [])

        turns: List[DialogueTurn] = []
        for item in raw_turns:
            speaker_str = str(item.get("speaker", "HOST")).upper()
            speaker = (
                CommentatorRole.ANALYST
                if "ANALYST" in speaker_str or "PETER" in speaker_str
                else CommentatorRole.HOST
            )

            emotion_str = str(item.get("emotion", "neutral")).lower()
            try:
                emotion = CommentaryEmotion(emotion_str)
            except ValueError:
                emotion = CommentaryEmotion.NEUTRAL

            text = str(item.get("text", "")).strip()
            if text:
                turns.append(
                    DialogueTurn(
                        speaker=speaker,
                        text=text,
                        emotion=emotion,
                        priority=item.get("priority", priority),
                    )
                )

        return turns

    def _generate_fallback_turns(
        self,
        context: CommentaryContext,
        priority: int,
    ) -> List[DialogueTurn]:
        """Rule-based emergency fallback if the LLM API is unavailable."""
        eval_data = context.evaluation
        player = context.white_player if eval_data.turn == "white" else context.black_player

        if context.dynamic == SpeakingDynamic.PLAY_BY_PLAY:
            spoken_call = san_to_spoken_move(eval_data.played_san)
            return [
                DialogueTurn(
                    speaker=CommentatorRole.HOST,
                    text=spoken_call,
                    emotion=CommentaryEmotion.NEUTRAL,
                    priority=priority,
                )
            ]

        if context.is_pondering:
            cands = ", ".join(context.candidate_suggestions[:2]) if context.candidate_suggestions else "candidate breaks"
            return [
                DialogueTurn(
                    speaker=CommentatorRole.ANALYST,
                    text=f"{player} might be weighing options here, perhaps considering {cands}.",
                    emotion=CommentaryEmotion.ANALYTICAL,
                    priority=priority,
                )
            ]

        if context.was_pondered:
            return [
                DialogueTurn(
                    speaker=CommentatorRole.HOST,
                    text=f"And the decision is {eval_data.played_san}.",
                    emotion=CommentaryEmotion.NEUTRAL,
                    priority=priority,
                )
            ]

        if eval_data.is_blunder:
            return [
                DialogueTurn(
                    speaker=CommentatorRole.HOST,
                    text=f"A massive swing on the board as {player} plays {eval_data.played_san}!",
                    emotion=CommentaryEmotion.SHOCKED,
                    priority=priority,
                ),
                DialogueTurn(
                    speaker=CommentatorRole.ANALYST,
                    text=(
                        eval_data.blunder_dossier.motivation_explanation + ", but it completely overlooks the tactical reply."
                        if eval_data.blunder_dossier
                        else "A serious miscalculation that leaves material hanging immediately."
                    ),
                    emotion=CommentaryEmotion.ANALYTICAL,
                    priority=priority,
                ),
            ]

        if eval_data.classification == MoveClassification.BRILLIANT:
            return [
                DialogueTurn(
                    speaker=CommentatorRole.HOST,
                    text=f"Unbelievable! {player} plays {eval_data.played_san}, offering up material!",
                    emotion=CommentaryEmotion.EXCITED,
                    priority=priority,
                ),
                DialogueTurn(
                    speaker=CommentatorRole.ANALYST,
                    text="A brilliant tactical strike. Accepting that piece leads to a complete collapse.",
                    emotion=CommentaryEmotion.ANALYTICAL,
                    priority=priority,
                ),
            ]

        if eval_data.left_book_now:
            return [
                DialogueTurn(
                    speaker=CommentatorRole.HOST,
                    text=f"And with {eval_data.played_san}, we are officially out of theoretical preparation.",
                    emotion=CommentaryEmotion.NEUTRAL,
                    priority=priority,
                )
            ]

        if context.think_category == ThinkCategory.DEEP_THINK:
            think_dur = int(context.move_time_spent_seconds)
            return [
                DialogueTurn(
                    speaker=CommentatorRole.HOST,
                    text=f"After a deep think of {think_dur} seconds, {player} commits to {eval_data.played_san}.",
                    emotion=CommentaryEmotion.TENSE,
                    priority=priority,
                ),
                DialogueTurn(
                    speaker=CommentatorRole.ANALYST,
                    text="A critical juncture in the game—taking the time to calculate the complications before making a stand.",
                    emotion=CommentaryEmotion.ANALYTICAL,
                    priority=priority,
                ),
            ]

        return [
            DialogueTurn(
                speaker=CommentatorRole.HOST,
                text=f"{player} plays {eval_data.played_san}.",
                emotion=CommentaryEmotion.NEUTRAL,
                priority=priority,
            )
        ]