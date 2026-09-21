// src/components/board/PlayerCard.tsx

import React from 'react';
import { Clock, User } from 'lucide-react';
import type { PlayerInfo } from '../../types/broadcast';
import { formatClock } from '../../utils/formatters';
import { useTheme } from '../../context/ThemeContext';

interface PlayerCardProps {
  player?: PlayerInfo | null;
  color: 'white' | 'black';
  clockSeconds?: number | null;
  isActiveTurn: boolean;
  isTimeTrouble?: boolean;
  lastMoveTimeSpent?: number | null;
}

export const PlayerCard: React.FC<PlayerCardProps> = ({
  player,
  color,
  clockSeconds,
  isActiveTurn,
  isTimeTrouble = false,
  lastMoveTimeSpent,
}) => {
  const { isDark } = useTheme();
  const isWhite = color === 'white';
  const username = player?.username || (isWhite ? 'White' : 'Black');
  const title = player?.title;
  const rating = player?.rating;

  return (
    <div
      className={`w-full flex items-center justify-between px-4 py-2.5 rounded-xl border transition-all duration-200 ${
        isActiveTurn
          ? isDark
            ? 'bg-[#181c26] border-[#e05338]/60 shadow-[0_0_14px_rgba(224,83,56,0.12)]'
            : 'bg-white border-[#e05338]/60 shadow-[0_0_14px_rgba(224,83,56,0.10)]'
          : isDark
          ? 'bg-[#13151b]/90 border-white/[0.08]'
          : 'bg-white/90 border-black/[0.08] shadow-sm'
      }`}
    >
      {/* Left: Player Identity */}
      <div className="flex items-center gap-3 min-w-0">
        {/* Color Marker & Avatar Icon */}
        <div
          className={`w-8 h-8 rounded-lg flex items-center justify-center border font-bold text-xs shadow-inner shrink-0 ${
            isWhite
              ? isDark
                ? 'bg-neutral-200 text-neutral-900 border-neutral-300'
                : 'bg-neutral-100 text-neutral-800 border-neutral-300'
              : 'bg-neutral-800 text-neutral-100 border-neutral-700'
          }`}
        >
          <User className="w-4 h-4" />
        </div>

        {/* Player Name, Title & Rating */}
        <div className="flex flex-col min-w-0">
          <div className="flex items-center gap-1.5 truncate">
            {title && (
              <span className="bg-[#e05338]/15 text-[#e05338] text-[10px] font-bold px-1.5 py-0.5 rounded border border-[#e05338]/30 uppercase tracking-wide">
                {title}
              </span>
            )}
            <span
              className={`font-semibold text-sm truncate ${
                isDark ? 'text-neutral-100' : 'text-neutral-900'
              }`}
            >
              {username}
            </span>
          </div>
          {(rating != null || (lastMoveTimeSpent != null && lastMoveTimeSpent > 0)) && (
            <div className="flex items-center gap-1.5 mt-0.5">
              {rating != null && (
                <span className="text-[11px] font-mono text-neutral-500 font-medium">
                  {rating}
                </span>
              )}
              {rating != null && lastMoveTimeSpent != null && lastMoveTimeSpent > 0 && (
                <span className="text-neutral-400 text-[10px]">•</span>
              )}
              {lastMoveTimeSpent != null && lastMoveTimeSpent > 0 && (
                <span className="text-[10px] font-mono text-neutral-500">
                  took {lastMoveTimeSpent.toFixed(1)}s
                </span>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Right: Broadcast Digital Clock */}
      <div
        className={`flex items-center gap-2 px-3 py-1.5 rounded-lg border font-mono text-base font-bold tracking-tight transition-colors shrink-0 ${
          isTimeTrouble
            ? 'bg-red-500/15 border-red-500/60 text-red-500 animate-pulse'
            : isActiveTurn
            ? isDark
              ? 'bg-[#0b0c0f] border-[#e05338]/50 text-[#e05338] shadow-inner'
              : 'bg-neutral-50 border-[#e05338]/50 text-[#e05338] shadow-inner'
            : isDark
            ? 'bg-[#0b0c0f] border-white/[0.06] text-neutral-400'
            : 'bg-neutral-100 border-neutral-200 text-neutral-700'
        }`}
      >
        <Clock
          className={`w-4 h-4 ${
            isTimeTrouble
              ? 'text-red-500'
              : isActiveTurn
              ? 'text-[#e05338]'
              : isDark
              ? 'text-neutral-500'
              : 'text-neutral-400'
          }`}
        />
        <span>{formatClock(clockSeconds)}</span>
      </div>
    </div>
  );
};