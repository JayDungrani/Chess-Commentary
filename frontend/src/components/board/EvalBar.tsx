// src/components/board/EvalBar.tsx

import React from 'react';
import { formatEval, getEvalBarPercentage } from '../../utils/formatters';

interface EvalBarProps {
  scoreCp?: number | null;
  mateIn?: number | null;
  height?: number | string;
}

export const EvalBar: React.FC<EvalBarProps> = ({
  scoreCp,
  mateIn,
  height = '100%',
}) => {
  const whitePercent = getEvalBarPercentage(scoreCp, mateIn);
  const scoreLabel = formatEval(scoreCp, mateIn);
  const isWhiteFavored = whitePercent >= 50;

  return (
    <div
      style={{ height: height ?? '100%' }}
      className="relative w-6 sm:w-7 bg-[#12151d] rounded-lg overflow-hidden border border-stone-800 shadow-xl flex flex-col justify-between select-none shrink-0 transition-[height] duration-150"
    >
      {/* Top Half: Black's Share */}
      <div
        className="w-full bg-stone-900 transition-all duration-700 ease-out flex items-start justify-center pt-2"
        style={{ height: `${100 - whitePercent}%` }}
      >
        {!isWhiteFavored && (
          <span className="text-[10px] font-bold tracking-tighter text-stone-300 drop-shadow">
            {scoreLabel}
          </span>
        )}
      </div>

      {/* Midpoint Equality Indicator Line */}
      <div className="absolute top-1/2 left-0 right-0 h-[1px] bg-amber-400/60 z-10 pointer-events-none" />

      {/* Bottom Half: White's Share */}
      <div
        className="w-full bg-stone-200 transition-all duration-700 ease-out flex items-end justify-center pb-2"
        style={{ height: `${whitePercent}%` }}
      >
        {isWhiteFavored && (
          <span className="text-[10px] font-bold tracking-tighter text-stone-900 drop-shadow">
            {scoreLabel}
          </span>
        )}
      </div>
    </div>
  );
};