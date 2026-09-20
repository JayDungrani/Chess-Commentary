# backend/app/commentary/prompts.py

from typing import List, Optional
from app.commentary.schemas import CommentaryContext, SpeakingDynamic
from app.engine.schemas import MoveClassification


SYSTEM_PROMPT = """You are the broadcast director and dialogue generator for an elite live chess broadcast featuring two commentators:

1. HOST ("James"): Lead play-by-play broadcaster. Energetic, descriptive, and observant. James paints the broadcast narrative: board tension, attacking momentum, and player posture. He does NOT just report clocks. Speaks in punchy, atmospheric bursts (strict 10-15 words).
2. ANALYST ("Peter" - GM): Grandmaster color commentator styled after premier online chess storytellers and YouTube analysts. Highly conversational, vivid, and deeply explanatory. He personifies pieces ("the knight isn't happy on that square"), explains human intent, uses natural chess vernacular ("chops off the knight", "if you take, take, and take here", "keeping development flexible"), and turns engine evaluations into intuitive strategic plans (strict 10-15 words).

### CLOCK & FORMAT RULES (STRICT):
- DO NOT READ THE CLOCK MECHANICALLY: Never say "White has 3 minutes and 20 seconds left." This is repetitive and unlistenable on audio.
- MENTION TIME ONLY WHEN DRAMATIC: The Host should only bring up time when the clock is a decisive story element:
  • Bullet: Only in a mad scramble (<10 seconds).
  • Blitz: In severe time trouble (<30 seconds) or a massive time gap (>2 minutes apart).
  • Rapid: When dipping under 2 minutes or after a long 3+ minute think.
  • Classical: When approaching time control (<5 minutes).
- When mentioning time, describe the pressure ("burning precious seconds", "down to the wire on the clock") rather than just reading raw digits.

### TEMPORAL REALITY & MOVE ATTRIBUTION (CRITICAL):
- ONLY the move listed under "Move Played" has actually occurred!
- STRICT MOVE ATTRIBUTION (DO NOT CONFUSE PLAYERS):
  1. "MISSED BETTER ALTERNATIVE": This was an alternative move for the player who JUST MOVED.
     • Example: If Black played Bg4 and missed Ba6, say: "Black should have played bishop to a6" or "Black missed the chance to drop the bishop to a6."
     • NEVER suggest the opponent's upcoming move as an alternative for the player!
  2. "UPCOMING CONTINUATIONS FOR OPPONENT": These are prospective replies for the opponent who is NEXT TO MOVE.
     • Example: "White can now look to swing the rook to c2."
     • Black CANNOT play rook to c2—that is White's rook! Never mix up the two sides.
- Frame opponent responses conditionally as suggestions, threats, or possibilities:
  • "White can look to push the f-pawn here..."
  • "The natural try is castling kingside..."
  • "If White finds knight to d5, Black is in serious trouble."

### SPOKEN AUDIO & STYLE RULES:
- NO RAW ALGEBRAIC NOTATION: NEVER output notation codes like "Qb2", "Bxc3", "Rfc8", "h3", "Ba6", or "Rc2". Always speak them in natural English words:
  • "Ba6"   -> "bishop to a6"
  • "Rc2"   -> "rook to c2" (or "swing the rook to c2")
  • "Qb2"   -> "queen to b2"
  • "Bxc3"  -> "bishop chops on c3"
  • "Nxd5"  -> "knight leaps into d5"
- PIECES NAMES: Always refer to pieces with their side ("White's knight", "Black's bishop", "White's f-rook").
- PLAYER NAMES: Always refer to players as "White" or "Black" (e.g., "White's knight", "Black counter-strikes"). Do not use internet handles or numbers.
- NO NUMBER RECITALS: Never say "plus two point four" or "drops forty centipawns." Say "firmly in the driver's seat," "ample compensation," "a sharp swing," or "dead equal."
- NO ROBOTIC AGREEMENTS: The Analyst must NEVER start by agreeing with the Host ("Indeed James", "You're right", "Exactly"). The Analyst immediately dives into the chess.

### RESPECT THE DYNAMIC:
- SOLO_HOST: Exactly ONE turn from HOST (Describe board tension, piece maneuvering, or question the position; <15 words).
- SOLO_ANALYST: Exactly ONE turn from ANALYST (Story-driven recap style breakdown).
- BANTER: Exactly TWO turns (HOST reaction/setup followed by ANALYST expert answer; Analyst 10-15 words).

### OUTPUT FORMAT:
Output strictly valid JSON matching this schema:
{
  "turns": [
    {
      "speaker": "HOST" | "ANALYST",
      "text": "spoken dialogue text",
      "emotion": "neutral" | "excited" | "shocked" | "analytical" | "tense" | "humorous",
      "priority": 1-10
    }
  ]
}
"""


def _format_clock(seconds: Optional[float]) -> str:
    if seconds is None:
        return "Unknown"
    m, s = divmod(int(seconds), 60)
    return f"{m:02d}:{s:02d}"


def _format_eval_description(eval_cp: Optional[int], mate_in: Optional[int]) -> str:
    if mate_in is not None:
        return f"White has forced mate in {mate_in}" if mate_in > 0 else f"Black has forced mate in {abs(mate_in)}"
    if eval_cp is None:
        return "Equal position"
    pawns = eval_cp / 100.0
    if abs(pawns) < 0.3:
        return "Completely balanced"
    elif pawns >= 2.5:
        return "Decisively winning for White"
    elif pawns >= 1.0:
        return "Clear advantage for White"
    elif pawns > 0.3:
        return "Slight edge for White"
    elif pawns <= -2.5:
        return "Decisively winning for Black"
    elif pawns <= -1.0:
        return "Clear advantage for Black"
    else:
        return "Slight edge for Black"


def build_commentary_prompt(context: CommentaryContext) -> str:
    eval_data = context.evaluation
    turn_color = eval_data.turn.capitalize()
    opponent_color = "Black" if eval_data.turn == "white" else "White"

    active_clock = context.white_clock_seconds if eval_data.turn == "white" else context.black_clock_seconds
    opp_clock = context.black_clock_seconds if eval_data.turn == "white" else context.white_clock_seconds

    prompt_lines: List[str] = [
        "### CURRENT MATCH CONTEXT:",
        f"- Match Format: {context.game_format.upper()}",
        f"- Move Played: {eval_data.played_san} (Ply {eval_data.ply}) by {turn_color}",
        f"- Next to Move: {opponent_color}",
        f"- Clocks: {turn_color}: {_format_clock(active_clock)} | {opponent_color}: {_format_clock(opp_clock)}",
    ]

    # Time pressure context
    if context.is_time_trouble:
        prompt_lines.append(f"- Clock Drama: ACTIVE TIME TROUBLE for {turn_color} in {context.game_format.upper()}!")
    else:
        prompt_lines.append("- Clock Drama: Normal. Do NOT talk about clocks unless relevant to a disparity.")

    # Theory & Book Status
    if eval_data.is_book:
        prompt_lines.append(f"- Opening Status: BOOK MOVE in {eval_data.opening_name or eval_data.eco_code or 'theory'}.")
    elif eval_data.left_book_now:
        prompt_lines.append(f"- Opening Status: NOVELTY / OUT OF BOOK ({eval_data.opening_name or eval_data.eco_code}).")

    eval_desc = _format_eval_description(eval_data.eval_cp_after, eval_data.mate_in_after)
    prompt_lines.extend([
        f"- Move Quality: {eval_data.classification.value}",
        f"- Position Assessment: {eval_desc}",
    ])

    if eval_data.classification in (MoveClassification.BLUNDER, MoveClassification.MISTAKE, MoveClassification.INACCURACY):
        pawn_loss = abs(eval_data.eval_swing_cp) / 100.0
        prompt_lines.append(f"- Damage: Suboptimal move by {turn_color} (-{pawn_loss:.2f} pawns).")

    # 1. WHAT THE ACTIVE PLAYER MISSED (RETROSPECTIVE ALTERNATIVE)
    missed_alt_san = None
    missed_alt_line = ""
    if eval_data.should_have_played and not eval_data.is_book:
        missed_alt_san = eval_data.should_have_played.primary_move_san
        if eval_data.should_have_played.san_moves:
            missed_alt_line = " ".join(eval_data.should_have_played.san_moves[:4])
    elif eval_data.blunder_dossier and eval_data.blunder_dossier.missed_best_san:
        missed_alt_san = eval_data.blunder_dossier.missed_best_san

    if missed_alt_san and eval_data.classification in (MoveClassification.BLUNDER, MoveClassification.MISTAKE, MoveClassification.INACCURACY):
        prompt_lines.extend([
            "",
            f"### WHAT {turn_color.upper()} MISSED (BETTER ALTERNATIVE):",
            f"- Instead of {eval_data.played_san}, {turn_color} should have played: {missed_alt_san} (Line: {missed_alt_line or missed_alt_san})",
            f"- MANDATORY RULE: If the Analyst discusses what {turn_color} should have played, you MUST cite {missed_alt_san} (spoken out, e.g. 'bishop to a6'). DO NOT attribute {opponent_color}'s moves to {turn_color}!",
        ])

    # 2. BLUNDER DOSSIER (IF APPLICABLE)
    if eval_data.blunder_dossier:
        dossier = eval_data.blunder_dossier
        prompt_lines.extend([
            "",
            "### TACTICAL BLUNDER BREAKDOWN:",
            f"- Natural Human Trap: {'YES' if dossier.is_natural_trap else 'No'}",
            f"- Human Temptation: {dossier.motivation_explanation}",
            f"- The Oversight: {dossier.refutation_explanation}",
            f"- Opponent's Refutation Sequence: {' '.join(dossier.punishment_moves_san[:3]) if dossier.punishment_moves_san else 'Immediate tactical loss'}",
            "- Guidance for Analyst: Explain why the human instinct was flawed and reveal the refutation.",
        ])
    elif eval_data.classification == MoveClassification.BRILLIANT:
        prompt_lines.extend([
            "",
            "### BRILLIANCY:",
            "- Genuine sound sacrifice executed under sharp tactical conditions.",
            "- Host: React with excitement and wonder.",
            "- Analyst: Breakdown what was offered up and why accepting it leads to ruin.",
        ])

    # 3. WHAT THE OPPONENT CAN PLAY NEXT (PROSPECTIVE CONTINUATIONS)
    if eval_data.candidate_responses:
        top_candidates = [
            f"{line.primary_move_san} ({_format_eval_description(line.score_cp, line.mate_in)})"
            for line in eval_data.candidate_responses[:2]
            if line.primary_move_san
        ]
        if top_candidates:
            prompt_lines.extend([
                "",
                f"### UPCOMING CONTINUATIONS FOR {opponent_color.upper()} (NEXT TO MOVE):",
                f"- Moves {opponent_color} can look for now: {', '.join(top_candidates)}",
                f"- MANDATORY RULE: These moves belong to {opponent_color}. Never say {turn_color} should have played them!",
            ])

    if context.dialogue_history:
        prompt_lines.extend(["", "### RECENT COMMENTARY HISTORY (DO NOT REPEAT WORDS):"])
        for turn in context.dialogue_history[-4:]:
            prompt_lines.append(f"- {turn.speaker.value}: \"{turn.text}\"")

    prompt_lines.extend(["", "### FORMAT DIRECTIVE:"])
    if context.dynamic == SpeakingDynamic.SOLO_HOST:
        prompt_lines.extend([
            "- FORMAT: SOLO_HOST (Exactly ONE turn from HOST).",
            "- Focus on board tension, momentum, or question the move.",
        ])
    elif context.dynamic == SpeakingDynamic.SOLO_ANALYST:
        prompt_lines.extend([
            "- FORMAT: SOLO_ANALYST (Exactly ONE turn from ANALYST).",
            "- Deliver an engaging YouTube recap-style breakdown. If {turn_color} erred, state that they missed {missed_alt_san or 'the best continuation'}",
        ])
    elif context.dynamic == SpeakingDynamic.BANTER:
        prompt_lines.extend([
            "- FORMAT: BANTER (HOST followed immediately by ANALYST).",
            "- Host: React to the move, question the plan, or frame the tension.",
            f"- Analyst: Explain the tactical reality. If {turn_color} made an inaccuracy, point out that {turn_color} missed {missed_alt_san or 'a stronger line'}, and note what {opponent_color} can now try.",
        ])

    prompt_lines.append("Return ONLY valid JSON.")
    return "\n".join(prompt_lines)