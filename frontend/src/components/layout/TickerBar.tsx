import React from 'react';
import { AlertTriangle, Sparkles, Cpu, ShieldAlert } from 'lucide-react';
import type { MoveEvaluation, ParsedMoveEvent } from '../../types/broadcast';
import { formatEval, formatPlyToMoveNumber, getClassificationStyles } from '../../utils/formatters';
import { useTheme } from '../../context/ThemeContext';

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
  const { isDark } = useTheme();

  // If match has completed, display prominent final result banner
  if (isGameOver && terminationReason) {
    return (
      <footer
        className={`w-full border-t px-4 py-2 flex items-center justify-between text-xs font-mono shadow-lg z-20 transition-colors duration-200 ${
          isDark ? 'bg-[#13151b] border-white/[0.08]' : 'bg-white border-neutral-200'
        }`}
      >
        <div className="flex items-center gap-2">
          <span className="px-2 py-0.5 rounded bg-[#e05338]/15 border border-[#e05338]/30 text-[#e05338] font-bold tracking-wider uppercase text-[10px]">
            FINAL RESULT
          </span>
          <span
            className={`font-bold text-sm tracking-tight font-sans ${
              isDark ? 'text-neutral-100' : 'text-neutral-900'
            }`}
          >
            {terminationReason}
          </span>
        </div>
        <span className={isDark ? 'text-neutral-400 text-[11px]' : 'text-neutral-500 text-[11px]'}>
          Match Concluded
        </span>
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
    <footer
      className={`w-full border-t px-4 py-1.5 flex items-center justify-between gap-4 text-xs z-20 select-none transition-colors duration-200 ${
        isDark ? 'bg-[#0b0c0f] border-white/[0.08]' : 'bg-white border-neutral-200'
      }`}
    >
      {/* Left: Move Identification & Quality Tag */}
      <div className="flex items-center gap-2.5 shrink-0">
        {lastMove && (
          <div className="flex items-center gap-1.5 font-mono">
            <span className={isDark ? 'text-neutral-500 font-bold' : 'text-neutral-400 font-bold'}>
              {formatPlyToMoveNumber(lastMove.ply, lastMove.turn)}
            </span>
            <span
              className={`font-bold text-sm ${
                isDark ? 'text-neutral-100' : 'text-neutral-900'
              }`}
            >
              {lastMove.san}
            </span>
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
          <span
            className={`text-[11px] font-mono font-bold px-2 py-0.5 rounded border ${
              isDark
                ? 'text-neutral-200 bg-[#13151b] border-white/[0.08]'
                : 'text-neutral-800 bg-neutral-100 border-neutral-200'
            }`}
          >
            {evalStr}
          </span>
        )}
      </div>

      {/* Center: Live Tactical Insight & Engine Line */}
      <div className="flex-1 min-w-0 flex items-center gap-2 overflow-hidden truncate">
        {/* Scenario A: Blunder Refutation Sequence */}
        {evaluation?.blunder_dossier ? (
          <div className="flex items-center gap-2 text-rose-500 font-mono text-[11px] truncate">
            <ShieldAlert className="w-3.5 h-3.5 shrink-0" />
            <span className="font-bold">PUNISHMENT:</span>
            <span className={isDark ? 'text-neutral-200' : 'text-neutral-800'}>
              {evaluation.blunder_dossier.punishment_moves_san.slice(0, 4).join(' ')}
            </span>
            <span className="text-neutral-500 truncate hidden lg:inline">
              ({evaluation.blunder_dossier.refutation_explanation})
            </span>
          </div>
        ) : isBrilliant ? (
          /* Scenario B: Brilliant Piece Sacrifice */
          <div className="flex items-center gap-2 text-[#e05338] font-mono text-[11px]">
            <Sparkles className="w-3.5 h-3.5 text-[#e05338] shrink-0" />
            <span className="font-bold">BRILLIANCY:</span>
            <span className={isDark ? 'text-neutral-200' : 'text-neutral-800'}>
              Decisive tactical sacrifice executed on board.
            </span>
          </div>
        ) : isSuboptimal && evaluation?.should_have_played ? (
          /* Scenario C: Better Alternative Missed */
          <div className="flex items-center gap-2 font-mono text-[11px] truncate">
            <AlertTriangle className="w-3.5 h-3.5 text-[#e05338] shrink-0" />
            <span className="font-bold text-neutral-500">BETTER TRY:</span>
            <span className="text-[#e05338] font-bold">
              {evaluation.should_have_played.primary_move_san}
            </span>
            {evaluation.should_have_played.san_moves.length > 1 && (
              <span className="text-neutral-500 hidden sm:inline truncate">
                ({evaluation.should_have_played.san_moves.slice(1, 4).join(' ')})
              </span>
            )}
          </div>
        ) : engineLineMoves.length > 0 ? (
          /* Scenario D: Engine Line / Principal Variation Continuation */
          <div className="flex items-center gap-2 font-mono text-[11px] truncate">
            <Cpu className="w-3.5 h-3.5 text-[#e05338] shrink-0" />
            <span className="text-neutral-500 font-bold uppercase tracking-wider text-[10px] shrink-0">
              ENGINE LINE:
            </span>
            <div className="flex items-center gap-1.5 truncate">
              {engineLineMoves.map((move, idx) => (
                <span
                  key={idx}
                  className={
                    idx === 0
                      ? 'text-[#e05338] font-bold'
                      : isDark
                      ? 'text-neutral-300'
                      : 'text-neutral-700'
                  }
                >
                  {move}
                </span>
              ))}
            </div>
          </div>
        ) : (
          <span className="text-neutral-500 font-mono text-[11px] flex items-center gap-2">
            <Cpu className="w-3 h-3 text-[#e05338] animate-pulse" />
            <span>Calculating engine continuation...</span>
          </span>
        )}
      </div>

      {/* Right: Opening or Theory Tag */}
      {evaluation?.opening_name && (
        <div className="hidden md:flex items-center gap-1.5 text-[11px] font-mono shrink-0">
          <span className="text-neutral-500">•</span>
          <span
            className={`truncate max-w-[200px] ${
              isDark ? 'text-neutral-300' : 'text-neutral-700'
            }`}
          >
            {evaluation.opening_name}
          </span>
        </div>
      )}
    </footer>
  );
};