# backend/app/commentary/prompts.py

from typing import List, Optional
from app.commentary.schemas import CommentaryContext, SpeakingDynamic, ThinkCategory
from app.engine.schemas import MoveClassification


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


SYSTEM_PROMPT = """You are the broadcast director and dialogue generator for an elite live chess broadcast featuring two commentators:

1. HOST ("James"): Play-by-play lead. Energetic, descriptive, and relatable. James frames human drama, board tension, momentum swings, player body language, and clock pressure. He makes punchy, atmospheric observations and calls the moves with vitality.
2. ANALYST ("Peter, GM"): Grandmaster color commentator. Conversational, vivid, and deeply explanatory. He personifies pieces ("the knight wants a better home"), explains player calculations, uses natural chess idioms ("chops off the knight", "dream outpost", "opens the floodgates"), and translates engine evaluations into clear strategic storylines.

### GOLDEN BROADCAST RULES:
1. STRICT COMBINED WORD BUDGET:
   - The target word budget applies to the TOTAL COMBINED words across all turns in the exchange, not per speaker.
   - Keep dialogue punchy, realistic, and tailored for broadcast pacing.

2. NATURAL AUDIO PROSODY & NO EM DASHES:
   - DO NOT USE EM DASHES: Never use em dashes or en dashes. Use standard punctuation like commas, periods, question marks, and natural pauses instead.
   - Use commas, ellipses ("..."), and question marks to create natural spoken cadence.
   - Avoid cliché sentence starters ("Indeed", "Certainly", "Well James", "Absolutely"). Dive directly into the action.

3. SPOKEN CHESS NOTATION ONLY:
   - NEVER output raw notation codes like "Qb2", "Bxc3", "Rfc8", "h3", "Ba6", or "Rc2".
   - Always speak them out in natural English words: "bishop to a6", "rook swings to c2", "queen to b2", "bishop captures on c3", "knight leaps into d5".
   - Refer to pieces by color and name ("White's knight", "Black's bishop", "White's f-rook").
   - Refer to players as "White" or "Black". Do not use usernames or numbers.
   - Never recite raw engine evaluations (never say "plus two point four" or "drops forty centipawns"). Use broadcast terms like "clear advantage", "dead equal", or "firmly in the driver's seat".

4. TEMPORAL REALITY & FOCUS ON THE PLAYED MOVE:
   - ONLY the move listed under "Move Played" has actually occurred! Focus your analysis directly on this move: why the player chose it, what square it controls, what weakness it addresses or creates, or what strategic plan it advances.
   - The opponent HAS NOT MOVED YET. DO NOT obsess over guessing the opponent's next move.
   - NEVER say "[Opponent] now eyes [move]", "[Opponent] eyes [move]", "[Opponent] now plays [move]", or "[Opponent] plays [move]". Viewers see the board and know the opponent has not moved.
   - If mentioning opponent options, keep them rare and strictly conditional:
     • "Black might consider knight to e4 here."
     • "Watch out for White's pawn break on the queenside."
   - Never confuse players or attribute one player's moves to the other.

5. DIALOGUE DIVERSITY & BAN FORMULAIC PATTERNS:
   - BAN PREDICTION CRUTCHES: NEVER use repetitive prediction templates like "[Color] now eyes [move]", "[Color] eyes [move]", "[Color] can now look to play", "[Color] can now strike with", or "[Color] opts for". Spend your words dissecting what JUST happened on the board.
   - BAN FORMULAIC QUESTIONS: Host (James) must NOT constantly end turns asking Peter questions, and NEVER use repetitive templates like "Is this [X], Peter?", "Is this the engine choice, Peter?", or "...what do you think, Peter?". James should primarily make sharp declarative observations, describe board tension, or highlight the player's clock pace. Organic questions should be rare.
   - IN THE OPENING (Plies 1-10): Focus on the opening's strategic character, pawn structures, and clash of styles rather than mechanically predicting obvious candidate moves move after move.

6. HUMAN EMPATHY ON MISTAKES:
   - On suboptimal moves or blunders, the Analyst should first validate why the human player was tempted (optical illusion, greedy impulse, natural recapture), and then dramatically reveal the tactical refutation.

### FEW-SHOT EXAMPLES:

Example 1 (Standard Move, BANTER format, 17 words total):
{
  "turns": [
    {
      "speaker": "HOST",
      "text": "Knight to c3, developing with purpose and clamping down on the central squares.",
      "emotion": "analytical",
      "priority": 2
    },
    {
      "speaker": "ANALYST",
      "text": "Staking a claim on d5. That knight wants an outpost, and Black must respond carefully.",
      "emotion": "analytical",
      "priority": 2
    }
  ]
}

Example 2 (Blunder, BANTER format, 18 words total):
{
  "turns": [
    {
      "speaker": "HOST",
      "text": "Wait, pawn to g5? That looks terribly loose on the kingside!",
      "emotion": "shocked",
      "priority": 8
    },
    {
      "speaker": "ANALYST",
      "text": "He wanted to kick the bishop, but it opens the floodgates. White has queen to h5 check ready to strike.",
      "emotion": "excited",
      "priority": 8
    }
  ]
}

Output strictly valid JSON matching the schema.
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
        "- REQUIRED PHRASING STYLE: SPECULATE CONDITIONALLY using candidate moves.",
        "- DO NOT claim you know what they ARE thinking; phrase conditionally as spectator speculation.",
        "",
        "### STRICT ANTI-REPETITION RULES:",
        "- Focus on the concrete board dilemma, the piece struggle, or the tactical threat, not generic mind-reading.",
        "- Speculate naturally and conditionally with authentic commentator phrasing.",
        f"- Target Word Budget: {context.target_word_range} (STRICT total combined words across all turns).",
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

    # Pre-translate played move to natural spoken words
    played_spoken = san_to_spoken_move(eval_data.played_san).rstrip(".")

    prompt_lines: List[str] = [
        "### CURRENT MATCH CONTEXT:",
        f"- Match Format: {context.game_format.upper()}",
        f"- Move Played: {played_spoken} ({eval_data.played_san}, Ply {eval_data.ply}) by {turn_color}",
        f"- Next to Move: {opponent_color}",
        f"- Clocks: {turn_color}: {_format_clock(active_clock)} | {opponent_color}: {_format_clock(opp_clock)}",
        f"- Think Duration: {context.move_time_spent_seconds:.1f}s ({context.think_category.value.upper()} tempo)",
        f"- Target Word Budget: {context.target_word_range}",
    ]

    # Move Tempo dynamics
    if context.was_pondered:
        prompt_lines.append(
            f"- POST-PONDERED MOVE: You already discussed candidate ideas while {turn_color} was in the tank! "
            f"Deliver a fresh, immediate move confirmation ({context.target_word_range})."
        )
    elif context.think_category == ThinkCategory.DEEP_THINK:
        prompt_lines.append(
            f"- DEEP THINK SPOTLIGHT: {turn_color} spent {context.move_time_spent_seconds:.1f}s calculating. "
            "Acknowledge the long pause and highlight the board complications they weighed."
        )
    elif context.think_category == ThinkCategory.THINK:
        prompt_lines.append(
            f"- CALCULATION PAUSE: {turn_color} paused for {context.move_time_spent_seconds:.1f}s to weigh options. "
            "Explain the strategic reasoning behind this calculated move."
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

    # Position Bias & Asymmetry Directive for Lopsided Evaluations
    cp_after = eval_data.eval_cp_after
    mate_after = eval_data.mate_in_after

    is_white_decisive = (mate_after is not None and mate_after > 0) or (cp_after is not None and cp_after >= 250)
    is_black_decisive = (mate_after is not None and mate_after < 0) or (cp_after is not None and cp_after <= -250)
    is_white_clear = cp_after is not None and 120 <= cp_after < 250
    is_black_clear = cp_after is not None and -250 < cp_after <= -120

    if is_white_decisive:
        prompt_lines.extend([
            "- BIASED POSITION DIRECTIVE (HEAVY WHITE ADVANTAGE):",
            "  The board is decisively lopsided in favor of White!",
            "  Your commentary MUST be opinionated and biased towards White's commanding dominance:",
            "  • Frame White as cruising toward victory with overwhelming board control (e.g., 'White is completely in the driver\\'s seat', 'White will comfortably wrap this up unless an unthinkable blunder happens', 'White has a vice grip on this position').",
            "  • Frame Black as desperately on life support or needing an absolute miracle to survive (e.g., 'Black\\'s defense is crumbling', 'Black is clinging on by a thread').",
            "  • Do not treat this as an equal struggle. Call the lopsided reality clearly and dramatically!",
        ])
    elif is_black_decisive:
        prompt_lines.extend([
            "- BIASED POSITION DIRECTIVE (HEAVY BLACK ADVANTAGE):",
            "  The board is decisively lopsided in favor of Black!",
            "  Your commentary MUST be opinionated and biased towards Black's commanding dominance:",
            "  • Frame Black as cruising toward victory with overwhelming board control (e.g., 'Black is completely in the driver\\'s seat', 'Black will comfortably take this home unless an unthinkable blunder occurs', 'Black dominates every critical file and diagonal').",
            "  • Frame White as desperately on life support or needing an absolute miracle to survive (e.g., 'White is clinging on by a thread', 'White\\'s position is collapsing under the pressure').",
            "  • Do not treat this as an equal struggle. Call the lopsided reality clearly and dramatically!",
        ])
    elif is_white_clear:
        prompt_lines.extend([
            "- ASYMMETRIC POSITION DIRECTIVE:",
            "  White holds a clear, tangible upper hand. Frame White as pressing forward for the win while Black fights an uphill defensive battle.",
        ])
    elif is_black_clear:
        prompt_lines.extend([
            "- ASYMMETRIC POSITION DIRECTIVE:",
            "  Black holds a clear, tangible upper hand. Frame Black as pressing forward for the win while White fights an uphill defensive battle.",
        ])

    # 1. WHAT THE ACTIVE PLAYER MISSED (RETROSPECTIVE ALTERNATIVE)
    missed_alt_san = None
    if eval_data.should_have_played and not eval_data.is_book:
        missed_alt_san = eval_data.should_have_played.primary_move_san
    elif eval_data.blunder_dossier and eval_data.blunder_dossier.missed_best_san:
        missed_alt_san = eval_data.blunder_dossier.missed_best_san

    if missed_alt_san and eval_data.classification in (MoveClassification.BLUNDER, MoveClassification.MISTAKE, MoveClassification.INACCURACY):
        missed_spoken = san_to_spoken_move(missed_alt_san).rstrip(".")
        prompt_lines.extend([
            "",
            f"### WHAT {turn_color.upper()} MISSED (BETTER ALTERNATIVE):",
            f"- Instead of {played_spoken}, {turn_color} missed: {missed_spoken} ({missed_alt_san}).",
            f"- If the Analyst discusses what {turn_color} should have played, cite {missed_spoken}. Do not attribute {opponent_color}'s moves to {turn_color}.",
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
            f"- Opponent's Refutation: {' '.join(dossier.punishment_moves_san[:3]) if dossier.punishment_moves_san else 'Immediate tactical punishment'}",
            "- Analyst: Acknowledge the player's natural temptation first, then reveal the refutation.",
        ])
    elif eval_data.classification == MoveClassification.BRILLIANT:
        prompt_lines.extend([
            "",
            "### BRILLIANCY:",
            "- Genuine sound sacrifice executed under sharp tactical conditions.",
            "- Host reacts with excitement; Analyst explains the tactical refutation if accepted.",
        ])

    # 3. OPENING PHASE GUIDANCE vs. PROSPECTIVE CONTINUATIONS
    is_opening = eval_data.is_book or (
        eval_data.ply <= 10
        and eval_data.classification not in (MoveClassification.BLUNDER, MoveClassification.BRILLIANT)
    )

    if is_opening:
        prompt_lines.extend([
            "",
            "### OPENING PHASE GUIDANCE:",
            "- Focus on the opening's strategic character, pawn structure, player preparation, and clash of plans.",
            "- DO NOT predict routine theoretical next moves (avoid mechanically guessing development steps). Discuss the overarching ideas, fighting style, and strategic battleground instead.",
            "- Avoid formulaic statements. Speak naturally about how both sides are setting up.",
        ])
    elif eval_data.is_blunder or eval_data.classification in (MoveClassification.BLUNDER, MoveClassification.MISTAKE) or abs(eval_data.eval_swing_cp) >= 80:
        top_candidates = []
        if eval_data.candidate_responses:
            for line in eval_data.candidate_responses[:2]:
                if line.primary_move_san:
                    cand_spoken = san_to_spoken_move(line.primary_move_san).rstrip(".")
                    eval_hint = _format_eval_description(line.score_cp, line.mate_in)
                    top_candidates.append(f"{cand_spoken} ({line.primary_move_san} - {eval_hint})")

        if top_candidates:
            prompt_lines.extend([
                "",
                f"### TACTICAL THREATS & REFUTATIONS FOR {opponent_color.upper()}:",
                f"- Tactical replies {opponent_color} can consider: {', '.join(top_candidates)}.",
                f"- TEMPORAL RULE: {opponent_color} has NOT moved yet. Frame as conditional refutations (e.g. '{opponent_color} has {top_candidates[0].split('(')[0].strip()} ready to strike.'). NEVER say '{opponent_color} now eyes...' or '{opponent_color} plays...'.",
            ])
    else:
        prompt_lines.extend([
            "",
            f"### ANALYSIS FOCUS FOR {turn_color.upper()}'S MOVE ({played_spoken}):",
            f"- Dissect what {turn_color}'s {played_spoken} accomplishes on the board: space control, piece mobility, pawn structure, or defensive solidity.",
            f"- DO NOT guess or predict {opponent_color}'s upcoming moves. NEVER say '{opponent_color} now eyes...' or '{opponent_color} plays...'. Focus 100% on the move that was just played.",
        ])

    if context.dialogue_history:
        prompt_lines.extend(["", "### RECENT COMMENTARY HISTORY (DO NOT REPEAT WORDS):"])
        for turn in context.dialogue_history[-4:]:
            prompt_lines.append(f"- {turn.speaker.value}: \"{turn.text}\"")

    prompt_lines.extend(["", "### FORMAT DIRECTIVE:"])
    prompt_lines.append(f"- STRICT COMBINED WORD BUDGET: {context.target_word_range} total words combined across all turns.")
    if context.dynamic == SpeakingDynamic.SOLO_HOST:
        prompt_lines.append("- FORMAT: SOLO_HOST (Exactly ONE turn from HOST). Focus on board tension, tempo, or the unfolding story of the game.")
    elif context.dynamic == SpeakingDynamic.SOLO_ANALYST:
        prompt_lines.append("- FORMAT: SOLO_ANALYST (Exactly ONE turn from ANALYST). Deliver a concise Grandmaster breakdown.")
    elif context.dynamic == SpeakingDynamic.BANTER:
        prompt_lines.append("- FORMAT: BANTER (HOST followed by ANALYST). Host reacts to the board drama, tempo, or position; Analyst delivers Grandmaster insight. Host should vary between declarative reactions and genuine questions; do NOT use formulaic question templates.")
    elif context.dynamic == SpeakingDynamic.PLAY_BY_PLAY:
        prompt_lines.extend([
            "- FORMAT: PLAY_BY_PLAY (The players are moving quickly! Deliver ONLY a crisp play-by-play move announcement from HOST or ANALYST).",
            f"- REQUIRED CONTENT: Simply call the played move cleanly (e.g. '{played_spoken}.'). Do NOT give positional essays or tactical explanations.",
            "- Target Word Budget: 2-5 words total.",
        ])

    prompt_lines.append("Return ONLY valid JSON.")
    return "\n".join(prompt_lines)