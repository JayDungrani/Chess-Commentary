# backend/app/commentary/prompts.py

from typing import List, Optional
from app.commentary.schemas import CommentaryContext, SpeakingDynamic, ThinkCategory
from app.engine.schemas import MoveClassification


SYSTEM_PROMPT = """You are the broadcast director and dialogue generator for an elite live chess broadcast featuring two commentators:

1. HOST ("James"): Lead play-by-play broadcaster. Energetic, descriptive, observant, and relatable. James frames the human drama: board tension, attacking momentum, clock pressure, and player hesitation. He speaks with natural broadcast flow and hooks the viewer into the position.
2. ANALYST ("Peter" - GM): Grandmaster color commentator styled after premier online chess storytellers and YouTube analysts. Highly conversational, vivid, and deeply explanatory. He personifies pieces ("the knight isn't happy on that square"), empathizes with human player calculations, uses natural chess idioms ("chops off the knight", "biting on granite", "dream outpost", "opening the floodgates"), and turns engine evaluations into intuitive strategic storylines.

### PACING & WORD BUDGET RULES (STRICT TOTAL CEILING):
- STRICT COMBINED WORD BUDGET: The "Target Word Budget" applies to the TOTAL COMBINED words of ALL TURNS in the exchange, NOT per speaker!
  • If the budget specifies "15-20 words total", the sum of words from HOST + ANALYST combined MUST NOT exceed 20 words!
  • Instant / Blitzed Moves: Fast and snappy (5-10 words total).
  • Standard Moves: Conversational and balanced (12-18 words total).
  • Deep Thinks: Crisp, focused takeaway (15-20 words total for Rapid).
- NATURAL SPEECH & AUDIO PROSODY:
  • Use punctuation strategically for ElevenLabs Text-to-Speech:
    - Use em-dashes ("—") for pauses or mid-sentence thought shifts.
    - Use ellipses ("...") for suspense, hesitation, or realization moments.
    - Use natural questions and exclamations to give the voices authentic human cadence.
  • Avoid repetitive sentence starters ("Indeed", "Certainly", "Well James", "Absolutely"). Dive directly into the action.

### CLOCK & FORMAT RULES:
- DO NOT READ THE CLOCK MECHANICALLY: Never say "White has 3 minutes and 20 seconds left." Describe the pressure ("burning precious seconds", "down to the wire on the clock", "playing on pure increment") rather than reciting raw digits.
- HIGHLIGHT DEEP THINKS & HESITATION: If a player spent significant time thinking, note the calculation struggle or what candidate moves they were calculating. If played instantly, call out the rapid instinct.

### HUMAN EMPATHY ON BLUNDERS:
- When analyzing suboptimal moves or blunders, the Analyst should FIRST validate why the human player was tempted (optical illusion, greedy impulse, automatic recapture), and THEN dramatically reveal the tactical punishment. Never talk down to the player; treat it as an instructive human moment.

### TEMPORAL REALITY & MOVE ATTRIBUTION (CRITICAL):
- ONLY the move listed under "Move Played" has actually occurred!
- STRICT MOVE ATTRIBUTION (DO NOT CONFUSE PLAYERS):
  1. "MISSED BETTER ALTERNATIVE": This was an alternative move for the player who JUST MOVED.
     • Example: If Black played b5 and missed knight to e4, say: "Black missed knight to e4" or "Black should have played knight to e4."
     • NEVER suggest the opponent's upcoming move as an alternative for the player!
  2. "UPCOMING CONTINUATIONS FOR OPPONENT": These are prospective candidate replies for the opponent who is NEXT TO MOVE.
     • STRICT TEMPORAL BAN: NEVER use present-tense indicative verbs for the opponent like "[Opponent] now plays X", "[Opponent] plays X", or "[Opponent] pushes X"!
     • The opponent HAS NOT MOVED YET! Saying "[Opponent] now plays X" is a FALSE statement of fact that confuses viewers looking at the board.
     • MANDATORY MODAL/CONDITIONAL PHRASING: ALWAYS use modal verbs indicating possibilities, options, or threats:
       - "White can now play pawn to a4." (STRICTLY FORBIDDEN: "White now plays a4")
       - "White can look to strike with a4."
       - "White has pawn to a4 here."
       - "Watch out for White's pawn to a4."
       - "If White finds a4, Black is in serious trouble."

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

### RESPECT THE DYNAMIC:
- SOLO_HOST: Exactly ONE turn from HOST (Describe board tension, tempo, or question the position).
- SOLO_ANALYST: Exactly ONE turn from ANALYST (Story-driven recap style breakdown).
- BANTER: Exactly TWO turns (HOST reaction/setup followed by ANALYST expert answer).

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


def build_pondering_prompt(context: CommentaryContext) -> str:
    turn_color = context.evaluation.turn.capitalize()
    acting_player = context.white_player if context.evaluation.turn == "white" else context.black_player
    candidates_str = ", ".join(context.candidate_suggestions) if context.candidate_suggestions else "central pawn breaks or piece coordination"

    style_directive = context.ponder_style_hint or "TACTICAL_QUESTION: Pose a sharp, direct rhetorical question about candidate moves or threats."

    prompt_lines = [
        "### CURRENT MATCH CONTEXT (IN THE TANK / PONDERING):",
        f"- Match Format: {context.game_format.upper()}",
        f"- Active Player Calculating: {acting_player} ({turn_color})",
        f"- Elapsed Think Time: {context.move_time_spent_seconds:.1f} seconds",
        f"- Board FEN: {context.evaluation.fen_after}",
        f"- Top Candidate Continuations (Stockfish): {candidates_str}",
        "",
        "### PONDERING GUIDANCE (NATURAL TV BROADCAST DESK STYLE):",
        f"- {acting_player} is paused on the clock, calculating over the board.",
        f"- STYLE DIRECTIVE FOR THIS PAUSE: {style_directive}",
        "",
        "### STRICT ANTI-REPETITION RULES (DO NOT USE ROBOTIC TEMPLATES):",
        "- STRICT BAN: NEVER say '[Color] is deep in thought', 'weighing their options', 'could they be debating between', or 'at a critical crossroads'.",
        "- FOCUS ON THE BOARD: Discuss the concrete board dilemma, the piece struggle, the pawn tension, or the tactical threat—NOT generic mind-reading.",
        "- SPECULATE NATURALLY & CONDITIONALLY: Frame possibilities with authentic commentator phrasing (e.g., 'Does Black dare push...', 'Tough call here—trading minor pieces...', 'That bishop needs breathing room...', 'Stockfish loves tucking the king, but...').",
        f"- Target Word Budget: {context.target_word_range} (STRICT total combined words).",
        "",
        "### FORMAT DIRECTIVE:",
        f"- FORMAT: {context.dynamic.value} (Deliver a concise, atmospheric thought while the clock ticks).",
        "Return ONLY valid JSON.",
    ]
    return "\n".join(prompt_lines)


def build_commentary_prompt(context: CommentaryContext) -> str:
    if context.is_pondering:
        return build_pondering_prompt(context)

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
        f"- Think Duration: {context.move_time_spent_seconds:.1f}s ({context.think_category.value.upper()} tempo in {context.game_format.upper()})",
        f"- Target Word Budget: {context.target_word_range}",
    ]

    # Move Tempo dynamics
    if context.was_pondered:
        prompt_lines.append(
            f"- POST-PONDERED MOVE: You already discussed candidate ideas while {turn_color} was in the tank! "
            f"Deliver a fresh, natural move confirmation ({context.target_word_range}). "
            "STRICT BAN: DO NOT say 'commits to X—a bold, principled strike' or use robotic formulas! "
            "Vary your reaction naturally: "
            "• Direct realization: 'And there it is—c5! Straight into the fire.' "
            "• Alternative choice: 'They bypass the trade and push e4 instead!' "
            "• Concise confirmation: 'The knight trade happens. Equalizing.' "
            "• Immediate momentum: 'f5 played—and the battle shifts to the kingside.'"
        )
    elif context.think_category == ThinkCategory.DEEP_THINK:
        prompt_lines.append(
            f"- DEEP THINK SPOTLIGHT: {turn_color} spent {context.move_time_spent_seconds:.1f}s calculating in {context.game_format.upper()}! "
            "Acknowledge the long pause, highlight the hesitation or candidate lines they weighed, and provide a richer breakdown. "
            "STRICT BAN: DO NOT use robotic phrases like '[Color] is deep in thought', 'weighing options', or 'at a critical crossroads'. Focus concretely on the board tension."
        )
    elif context.think_category == ThinkCategory.INSTANT:
        prompt_lines.append(
            f"- INSTANT MOVE: Played in just {context.move_time_spent_seconds:.1f}s. Keep spoken delivery brisk, immediate, and punchy."
        )

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
                f"- Candidate moves {opponent_color} can look for next: {', '.join(top_candidates)}",
                f"- STRICT TEMPORAL BAN: {opponent_color} has NOT moved yet! NEVER say '{opponent_color} now plays [move]' or '{opponent_color} plays [move]'!",
                f"- MANDATORY RULE: ALWAYS use modal verbs indicating possibilities or options (e.g. '{opponent_color} can now play pawn to a4', '{opponent_color} can look to...', '{opponent_color} has...').",
                f"- NEVER attribute {opponent_color}'s candidate moves to {turn_color}!",
            ])

    if context.dialogue_history:
        prompt_lines.extend(["", "### RECENT COMMENTARY HISTORY (DO NOT REPEAT WORDS):"])
        for turn in context.dialogue_history[-4:]:
            prompt_lines.append(f"- {turn.speaker.value}: \"{turn.text}\"")

    prompt_lines.extend(["", "### FORMAT DIRECTIVE:"])
    prompt_lines.append(f"- STRICT COMBINED WORD BUDGET: {context.target_word_range}. The sum of words across ALL turns must not exceed this total.")
    if context.dynamic == SpeakingDynamic.SOLO_HOST:
        prompt_lines.extend([
            "- FORMAT: SOLO_HOST (Exactly ONE turn from HOST).",
            "- Focus on board tension, momentum, or question the move.",
        ])
    elif context.dynamic == SpeakingDynamic.SOLO_ANALYST:
        prompt_lines.extend([
            "- FORMAT: SOLO_ANALYST (Exactly ONE turn from ANALYST).",
            f"- Deliver an engaging Grandmaster breakdown. If {turn_color} erred, validate the human temptation first, then state that they missed {missed_alt_san or 'the best continuation'}. For {opponent_color}, use modal phrasing ('{opponent_color} can now look to...').",
        ])
    elif context.dynamic == SpeakingDynamic.BANTER:
        prompt_lines.extend([
            "- FORMAT: BANTER (HOST followed immediately by ANALYST).",
            "- Host: React to the move, question the plan, or frame the tension and clock.",
            f"- Analyst: Explain the tactical reality with Grandmaster clarity. If {turn_color} made an inaccuracy, validate their instinct first, point out that {turn_color} missed {missed_alt_san or 'a stronger line'}, and note what {opponent_color} CAN now look to play (use modal verbs: '{opponent_color} can now play...', NEVER '{opponent_color} now plays...').",
        ])
    elif context.dynamic == SpeakingDynamic.PLAY_BY_PLAY:
        prompt_lines.extend([
            "- FORMAT: PLAY_BY_PLAY (The players are moving quickly! Deliver ONLY a crisp play-by-play move announcement from HOST or ANALYST).",
            f"- REQUIRED CONTENT: Simply call the played move cleanly (e.g. 'Bishop to e6.', 'Castles.', 'Takes on d5.', 'Knight to c3.'). Do NOT give positional essays or tactical explanations.",
            "- Target Word Budget: 2-5 words total.",
        ])

    prompt_lines.append("Return ONLY valid JSON.")
    return "\n".join(prompt_lines)