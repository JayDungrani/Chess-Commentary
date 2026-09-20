// src/components/board/MoveNavigator.tsx

import React, { useEffect } from 'react';
import {
  ChevronsLeft,
  ChevronLeft,
  ChevronRight,
  ChevronsRight,
  Radio,
} from 'lucide-react';
import { formatPlyToMoveNumber } from '../../utils/formatters';

interface MoveNavigatorProps {
  currentPly: number;
  maxPly: number;
  minPly: number;
  isLive: boolean;
  onNavigate: (ply: number) => void;
  onGoLive: () => void;
  moveSan?: string | null;
  turn?: 'white' | 'black';
}

export const MoveNavigator: React.FC<MoveNavigatorProps> = ({
  currentPly,
  maxPly,
  minPly,
  isLive,
  onNavigate,
  onGoLive,
  moveSan,
  turn,
}) => {
  // Arrow key navigation listener (Left = previous, Right = next)
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Ignore if user is focused inside an input or textarea
      if (['INPUT', 'TEXTAREA'].includes((e.target as HTMLElement)?.tagName)) {
        return;
      }

      if (e.key === 'ArrowLeft') {
        e.preventDefault();
        if (currentPly > minPly) {
          onNavigate(currentPly - 1);
        }
      } else if (e.key === 'ArrowRight') {
        e.preventDefault();
        if (currentPly < maxPly) {
          const next = currentPly + 1;
          if (next >= maxPly) {
            onGoLive();
          } else {
            onNavigate(next);
          }
        }
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [currentPly, minPly, maxPly, onNavigate, onGoLive]);

  const canGoBack = currentPly > minPly;
  const canGoForward = currentPly < maxPly;

  return (
    <div className="w-full flex items-center justify-between px-3 py-1.5 rounded-xl bg-[#12151d] border border-stone-800 shadow-md select-none shrink-0">
      {/* 1. Step Arrow Controls */}
      <div className="flex items-center gap-1">
        {/* Jump to start */}
        <button
          onClick={() => onNavigate(minPly)}
          disabled={!canGoBack}
          className="p-1 rounded-md text-stone-400 hover:text-stone-100 hover:bg-stone-800/80 disabled:opacity-30 disabled:pointer-events-none transition-colors"
          title="Jump to Start"
        >
          <ChevronsLeft className="w-4 h-4" />
        </button>

        {/* Previous move */}
        <button
          onClick={() => onNavigate(currentPly - 1)}
          disabled={!canGoBack}
          className="p-1 rounded-md text-stone-400 hover:text-stone-100 hover:bg-stone-800/80 disabled:opacity-30 disabled:pointer-events-none transition-colors"
          title="Previous Move (← Arrow)"
        >
          <ChevronLeft className="w-4 h-4" />
        </button>

        {/* Next move */}
        <button
          onClick={() => {
            const next = currentPly + 1;
            if (next >= maxPly) {
              onGoLive();
            } else {
              onNavigate(next);
            }
          }}
          disabled={!canGoForward}
          className="p-1 rounded-md text-stone-400 hover:text-stone-100 hover:bg-stone-800/80 disabled:opacity-30 disabled:pointer-events-none transition-colors"
          title="Next Move (→ Arrow)"
        >
          <ChevronRight className="w-4 h-4" />
        </button>

        {/* Jump to live */}
        <button
          onClick={onGoLive}
          disabled={isLive}
          className="p-1 rounded-md text-stone-400 hover:text-stone-100 hover:bg-stone-800/80 disabled:opacity-30 disabled:pointer-events-none transition-colors"
          title="Jump to Latest (Live)"
        >
          <ChevronsRight className="w-4 h-4" />
        </button>
      </div>

      {/* 2. Inspected Position Display */}
      <div className="flex items-center gap-2 font-mono text-xs">
        {currentPly === 0 ? (
          <span className="text-stone-400">Start Position</span>
        ) : moveSan ? (
          <div className="flex items-center gap-1">
            <span className="text-stone-500 font-bold">
              {formatPlyToMoveNumber(currentPly, turn || 'white')}
            </span>
            <span className="text-amber-400 font-bold">{moveSan}</span>
          </div>
        ) : (
          <span className="text-stone-400">Ply {currentPly}</span>
        )}
      </div>

      {/* 3. Live Status & Snap-Back Pill */}
      <div>
        {isLive ? (
          <div className="flex items-center gap-1.5 px-2 py-0.5 rounded-full bg-rose-500/10 border border-rose-500/30 text-rose-400 text-[10px] font-bold font-mono">
            <span className="w-1.5 h-1.5 rounded-full bg-rose-500 animate-pulse" />
            LIVE
          </div>
        ) : (
          <button
            onClick={onGoLive}
            className="flex items-center gap-1.5 px-2.5 py-0.5 rounded-full bg-amber-500/15 border border-amber-500/40 text-amber-300 hover:bg-amber-500/25 text-[10px] font-bold transition-all shadow-sm"
            title="Return to latest live position"
          >
            <Radio className="w-3 h-3 text-amber-400 animate-pulse" />
            SNAP TO LIVE
          </button>
        )}
      </div>
    </div>
  );
};