// src/components/board/PlayerCard.tsx

import React from 'react';
import { Clock, User } from 'lucide-react';
import type { PlayerInfo } from '../../types/broadcast';
import { formatClock } from '../../utils/formatters';

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
  const isWhite = color === 'white';
  const username = player?.username || (isWhite ? 'White' : 'Black');
  const title = player?.title;
  const rating = player?.rating;

  return (
    <div
      className={`w-full flex items-center justify-between px-4 py-2.5 rounded-xl border transition-all duration-300 ${
        isActiveTurn
          ? 'bg-[#181c26] border-amber-500/50 shadow-[0_0_12px_rgba(245,158,11,0.08)]'
          : 'bg-[#12151d]/90 border-stone-800/80'
      }`}
    >
      {/* Left: Player Identity */}
      <div className="flex items-center gap-3 min-w-0">
        {/* Color Marker & Avatar Icon */}
        <div
          className={`w-8 h-8 rounded-lg flex items-center justify-center border font-bold text-xs shadow-inner shrink-0 ${
            isWhite
              ? 'bg-stone-200 text-stone-900 border-stone-300'
              : 'bg-stone-800 text-stone-200 border-stone-700'
          }`}
        >
          <User className="w-4 h-4" />
        </div>

        {/* Player Name, Title & Rating */}
        <div className="flex flex-col min-w-0">
          <div className="flex items-center gap-1.5 truncate">
            {title && (
              <span className="bg-amber-500/15 text-amber-300 text-[10px] font-bold px-1.5 py-0.5 rounded border border-amber-500/30 uppercase tracking-wide">
                {title}
              </span>
            )}
            <span className="font-semibold text-sm text-stone-100 truncate">
              {username}
            </span>
          </div>

        </div>
      </div>

      {/* Right: Broadcast Digital Clock */}
      <div
        className={`flex items-center gap-2 px-3 py-1.5 rounded-lg border font-mono text-base font-bold tracking-tight transition-colors shrink-0 ${
          isTimeTrouble
            ? 'bg-red-500/15 border-red-500/60 text-red-400 animate-pulse'
            : isActiveTurn
            ? 'bg-stone-900 border-amber-500/40 text-amber-300 shadow-inner'
            : 'bg-[#0a0c10] border-stone-800 text-stone-400'
        }`}
      >
        <Clock className={`w-4 h-4 ${isTimeTrouble ? 'text-red-400' : 'text-stone-400'}`} />
        <span>{formatClock(clockSeconds)}</span>
      </div>
    </div>
  );
};