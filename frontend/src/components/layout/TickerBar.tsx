// src/components/layout/TickerBar.tsx

import React from 'react';
import { AlertTriangle, Sparkles, Cpu, ShieldAlert } from 'lucide-react';
import type { MoveEvaluation, ParsedMoveEvent } from '../../types/broadcast';
import { formatEval, formatPlyToMoveNumber, getClassificationStyles } from '../../utils/formatters';

interface TickerBarProps {
  evaluation?: MoveEvaluation | null;
  lastMove?: ParsedMoveEvent | null;
  terminationReason?: string | null;
  isGameOver: boolean;
}

export const TickerBar: React.FC<TickerBarProps> = ({
  evaluation,
  lastMove,
  terminationReason,
  isGameOver,
}) => {
  // If match has completed, display prominent final result banner
  if (isGameOver && terminationReason) {
    return (
      <footer className="w-full bg-[#12151d] border-t border-stone-800 px-4 py-2 flex items-center justify-between text-xs font-mono shadow-2xl z-20">
        <div className="flex items-center gap-2">
          <span className="px-2 py-0.5 rounded bg-amber-500/15 border border-amber-500/30 text-amber-300 font-bold tracking-wider uppercase text-[10px]">
            FINAL RESULT
          </span>
          <span className="text-stone-100 font-bold text-sm tracking-tight font-sans">
            {terminationReason}
          </span>
        </div>
        <span className="text-stone-500 text-[11px]">Match Concluded</span>
      </footer>
    );
  }

  const classification = evaluation?.classification;
  const isBlunder = classification === 'BLUNDER';
  const isBrilliant = classification === 'BRILLIANT';
  const isMistake = classification === 'MISTAKE';
  const isSuboptimal = isBlunder || isMistake || classification === 'INACCURACY';

  const classStyle = getClassificationStyles(classification);
  const evalStr = formatEval(evaluation?.eval_cp_after, evaluation?.mate_in_after);

  // Extract full engine continuation moves safely across varying backend schemas
  const engineLineMoves: string[] = (() => {
    if (!evaluation) return [];
    const anyEval = evaluation as any;

    // 1. Direct engine line / PV array or string on evaluation
    if (Array.isArray(anyEval.engine_line)) return anyEval.engine_line;
    if (typeof anyEval.engine_line === 'string') return anyEval.engine_line.split(' ').filter(Boolean);
    if (Array.isArray(anyEval.best_line_san)) return anyEval.best_line_san;
    if (Array.isArray(anyEval.pv_san)) return anyEval.pv_san;

    // 2. Line / continuation on top candidate response
    const topCand = evaluation.candidate_responses?.[0] as any;
    if (topCand) {
      if (Array.isArray(topCand.san_moves) && topCand.san_moves.length > 0) {
        return topCand.san_moves;
      }
      if (typeof topCand.line === 'string') {
        return topCand.line.split(' ').filter(Boolean);
      }
      if (Array.isArray(topCand.line)) {
        return topCand.line;
      }
    }

    // 3. Fallback: collect primary moves across candidate responses
    if (evaluation.candidate_responses && evaluation.candidate_responses.length > 0) {
      return evaluation.candidate_responses
        .map((cand) => cand.primary_move_san)
        .filter(Boolean);
    }

    return [];
  })();

  return (
    <footer className="w-full bg-[#0a0c10] border-t border-stone-800/90 px-4 py-1.5 flex items-center justify-between gap-4 text-xs z-20 select-none">
      {/* Left: Move Identification & Quality Tag */}
      <div className="flex items-center gap-2.5 shrink-0">
        {lastMove && (
          <div className="flex items-center gap-1.5 font-mono">
            <span className="text-stone-500 font-bold">
              {formatPlyToMoveNumber(lastMove.ply, lastMove.turn)}
            </span>
            <span className="font-bold text-stone-100 text-sm">{lastMove.san}</span>
          </div>
        )}

        {classification && (
          <span
            className={`px-2 py-0.5 rounded-md border text-[10px] font-bold uppercase tracking-wider ${classStyle.bg} ${classStyle.text} ${classStyle.border}`}
          >
            {classification}
          </span>
        )}

        {evaluation && (
          <span className="text-[11px] font-mono font-bold text-stone-300 bg-[#12151d] px-2 py-0.5 rounded border border-stone-800">
            {evalStr}
          </span>
        )}
      </div>

      {/* Center: Live Tactical Insight & Engine Line */}
      <div className="flex-1 min-w-0 flex items-center gap-2 overflow-hidden truncate">
        {/* Scenario A: Blunder Refutation Sequence */}
        {evaluation?.blunder_dossier ? (
          <div className="flex items-center gap-2 text-rose-400 font-mono text-[11px] truncate">
            <ShieldAlert className="w-3.5 h-3.5 shrink-0" />
            <span className="font-bold">PUNISHMENT:</span>
            <span className="text-stone-200">
              {evaluation.blunder_dossier.punishment_moves_san.slice(0, 4).join(' ')}
            </span>
            <span className="text-stone-500 truncate hidden lg:inline">
              ({evaluation.blunder_dossier.refutation_explanation})
            </span>
          </div>
        ) : isBrilliant ? (
          /* Scenario B: Brilliant Piece Sacrifice */
          <div className="flex items-center gap-2 text-amber-300 font-mono text-[11px]">
            <Sparkles className="w-3.5 h-3.5 text-amber-400 shrink-0" />
            <span className="font-bold">BRILLIANCY:</span>
            <span className="text-stone-200">Decisive tactical sacrifice executed on board.</span>
          </div>
        ) : isSuboptimal && evaluation?.should_have_played ? (
          /* Scenario C: Better Alternative Missed */
          <div className="flex items-center gap-2 text-stone-300 font-mono text-[11px] truncate">
            <AlertTriangle className="w-3.5 h-3.5 text-amber-400 shrink-0" />
            <span className="font-bold text-stone-400">BETTER TRY:</span>
            <span className="text-amber-300 font-bold">
              {evaluation.should_have_played.primary_move_san}
            </span>
            {evaluation.should_have_played.san_moves.length > 1 && (
              <span className="text-stone-500 hidden sm:inline truncate">
                ({evaluation.should_have_played.san_moves.slice(1, 4).join(' ')})
              </span>
            )}
          </div>
        ) : engineLineMoves.length > 0 ? (
          /* Scenario D: Engine Line / Principal Variation Continuation */
          <div className="flex items-center gap-2 text-stone-400 font-mono text-[11px] truncate">
            <Cpu className="w-3.5 h-3.5 text-amber-400 shrink-0" />
            <span className="text-stone-400 font-bold uppercase tracking-wider text-[10px] shrink-0">
              ENGINE LINE:
            </span>
            <div className="flex items-center gap-1.5 truncate">
              {engineLineMoves.map((move, idx) => (
                <span
                  key={idx}
                  className={idx === 0 ? 'text-amber-300 font-bold' : 'text-stone-300'}
                >
                  {move}
                </span>
              ))}
            </div>
          </div>
        ) : (
          <span className="text-stone-600 font-mono text-[11px]">
            Waiting for live engine analysis...
          </span>
        )}
      </div>

      {/* Right: Opening or Theory Tag */}
      {evaluation?.opening_name && (
        <div className="hidden md:flex items-center gap-1.5 text-[11px] text-stone-400 font-mono shrink-0">
          <span className="text-stone-700">•</span>
          <span className="truncate max-w-[200px] text-stone-300">
            {evaluation.opening_name}
          </span>
        </div>
      )}
    </footer>
  );
};