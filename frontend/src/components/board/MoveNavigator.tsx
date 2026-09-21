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
import { useTheme } from '../../context/ThemeContext';

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
  const { isDark } = useTheme();
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
    <div
      className={`w-full flex items-center justify-between px-3 py-1.5 rounded-xl border shadow-sm select-none shrink-0 transition-colors duration-200 ${
        isDark ? 'bg-[#13151b] border-white/[0.08]' : 'bg-white border-neutral-200'
      }`}
    >
      {/* 1. Step Arrow Controls */}
      <div className="flex items-center gap-1">
        {/* Jump to start */}
        <button
          onClick={() => onNavigate(minPly)}
          disabled={!canGoBack}
          className={`p-1 rounded-md disabled:opacity-30 disabled:pointer-events-none transition-colors ${
            isDark
              ? 'text-neutral-400 hover:text-white hover:bg-white/[0.08]'
              : 'text-neutral-500 hover:text-neutral-900 hover:bg-black/[0.05]'
          }`}
          title="Jump to Start"
        >
          <ChevronsLeft className="w-4 h-4" />
        </button>

        {/* Previous move */}
        <button
          onClick={() => onNavigate(currentPly - 1)}
          disabled={!canGoBack}
          className={`p-1 rounded-md disabled:opacity-30 disabled:pointer-events-none transition-colors ${
            isDark
              ? 'text-neutral-400 hover:text-white hover:bg-white/[0.08]'
              : 'text-neutral-500 hover:text-neutral-900 hover:bg-black/[0.05]'
          }`}
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
          className={`p-1 rounded-md disabled:opacity-30 disabled:pointer-events-none transition-colors ${
            isDark
              ? 'text-neutral-400 hover:text-white hover:bg-white/[0.08]'
              : 'text-neutral-500 hover:text-neutral-900 hover:bg-black/[0.05]'
          }`}
          title="Next Move (→ Arrow)"
        >
          <ChevronRight className="w-4 h-4" />
        </button>

        {/* Jump to live */}
        <button
          onClick={onGoLive}
          disabled={isLive}
          className={`p-1 rounded-md disabled:opacity-30 disabled:pointer-events-none transition-colors ${
            isDark
              ? 'text-neutral-400 hover:text-white hover:bg-white/[0.08]'
              : 'text-neutral-500 hover:text-neutral-900 hover:bg-black/[0.05]'
          }`}
          title="Jump to Latest (Live)"
        >
          <ChevronsRight className="w-4 h-4" />
        </button>
      </div>

      {/* 2. Inspected Position Display */}
      <div className="flex items-center gap-2 font-mono text-xs">
        {currentPly === 0 ? (
          <span className={isDark ? 'text-neutral-500' : 'text-neutral-500'}>Start Position</span>
        ) : moveSan ? (
          <div className="flex items-center gap-1">
            <span className={isDark ? 'text-neutral-500 font-bold' : 'text-neutral-400 font-bold'}>
              {formatPlyToMoveNumber(currentPly, turn || 'white')}
            </span>
            <span className="text-[#e05338] font-bold">{moveSan}</span>
          </div>
        ) : (
          <span className={isDark ? 'text-neutral-500' : 'text-neutral-500'}>
            Ply {currentPly}
          </span>
        )}
      </div>

      {/* 3. Live Status & Snap-Back Pill */}
      <div>
        {isLive ? (
          <div className="flex items-center gap-1.5 px-2 py-0.5 rounded-full bg-[#e05338]/15 border border-[#e05338]/30 text-[#e05338] text-[10px] font-bold font-mono">
            <span className="w-1.5 h-1.5 rounded-full bg-[#e05338] animate-pulse" />
            LIVE
          </div>
        ) : (
          <button
            onClick={onGoLive}
            className="flex items-center gap-1.5 px-2.5 py-0.5 rounded-full bg-[#e05338]/15 border border-[#e05338]/40 text-[#e05338] hover:bg-[#e05338]/25 text-[10px] font-bold transition-all shadow-sm"
            title="Return to latest live position"
          >
            <Radio className="w-3 h-3 text-[#e05338] animate-pulse" />
            SNAP TO LIVE
          </button>
        )}
      </div>
    </div>
  );
};