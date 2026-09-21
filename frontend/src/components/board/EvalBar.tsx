// src/components/board/EvalBar.tsx

import React from 'react';
import { formatEval, getEvalBarPercentage } from '../../utils/formatters';
import { useTheme } from '../../context/ThemeContext';

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
  const { isDark } = useTheme();
  const whitePercent = getEvalBarPercentage(scoreCp, mateIn);
  const scoreLabel = formatEval(scoreCp, mateIn);
  const isWhiteFavored = whitePercent >= 50;

  return (
    <div
      style={{ height: height ?? '100%' }}
      className={`relative w-6 sm:w-7 rounded-lg overflow-hidden border shadow-lg flex flex-col justify-between select-none shrink-0 transition-[height,background-color,border-color] duration-200 ${
        isDark ? 'bg-[#13151b] border-white/[0.08]' : 'bg-white border-neutral-300'
      }`}
    >
      {/* Top Half: Black's Share */}
      <div
        className="w-full bg-neutral-800 transition-all duration-700 ease-out flex items-start justify-center pt-2"
        style={{ height: `${100 - whitePercent}%` }}
      >
        {!isWhiteFavored && (
          <span className="text-[10px] font-mono font-bold tracking-tighter text-neutral-200 drop-shadow">
            {scoreLabel}
          </span>
        )}
      </div>

      {/* Midpoint Equality Indicator Line */}
      <div className="absolute top-1/2 left-0 right-0 h-[1.5px] bg-[#e05338] z-10 pointer-events-none" />

      {/* Bottom Half: White's Share */}
      <div
        className="w-full bg-neutral-100 transition-all duration-700 ease-out flex items-end justify-center pb-2"
        style={{ height: `${whitePercent}%` }}
      >
        {isWhiteFavored && (
          <span className="text-[10px] font-mono font-bold tracking-tighter text-neutral-900 drop-shadow">
            {scoreLabel}
          </span>
        )}
      </div>
    </div>
  );
};