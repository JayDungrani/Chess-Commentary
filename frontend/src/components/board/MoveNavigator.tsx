// src/components/board/MoveNavigator.tsx

import React, { useEffect } from 'react';
import {
  ChevronsLeft,
  ChevronLeft,
  ChevronRight,
  ChevronsRight,
  Radio,
  Play,
  Pause,
  RotateCcw,
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
  isPlaying?: boolean;
  onTogglePlay?: () => void;
  moveDelay?: number;
  onChangeMoveDelay?: (delay: number) => void;
  isSandbox?: boolean;
  onExitSandbox?: () => void;
  isPgnMode?: boolean;
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
  isPlaying = false,
  onTogglePlay,
  moveDelay = 2,
  onChangeMoveDelay,
  isSandbox = false,
  onExitSandbox,
  isPgnMode = false,
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
      } else if (e.code === 'Space') {
        // Spacebar toggles Play/Pause in PGN mode
        if (isPgnMode && onTogglePlay) {
          e.preventDefault();
          onTogglePlay();
        }
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [currentPly, minPly, maxPly, onNavigate, onGoLive, onTogglePlay, isPgnMode]);

  const canGoBack = currentPly > minPly;
  const canGoForward = currentPly < maxPly;

  return (
    <div
      className={`w-full flex items-center justify-between px-3 py-1.5 rounded-xl border shadow-sm select-none shrink-0 transition-colors duration-200 ${
        isDark ? 'bg-[#13151b] border-white/[0.08]' : 'bg-white border-neutral-200'
      }`}
    >
      {/* 1. Step Arrow & Playback Controls */}
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

        {/* Play / Pause Toggle - ONLY IN PGN / FEN SECTION */}
        {isPgnMode && onTogglePlay && (
          <button
            onClick={onTogglePlay}
            className={`p-1 rounded-md transition-colors ${
              isPlaying
                ? 'bg-[#e05338]/20 text-[#e05338]'
                : isDark
                ? 'text-neutral-300 hover:text-white hover:bg-white/[0.08]'
                : 'text-neutral-600 hover:text-neutral-900 hover:bg-black/[0.05]'
            }`}
            title={isPlaying ? 'Pause Auto-Play (Space)' : 'Play Next Moves (Space)'}
          >
            {isPlaying ? (
              <Pause className="w-4 h-4 text-[#e05338]" />
            ) : (
              <Play className="w-4 h-4" />
            )}
          </button>
        )}

        {/* Next move */}
        <button
          onClick={() => {
            const next = currentPly + 1;
            if (next >= maxPly) {
              if (isPgnMode) {
                onNavigate(maxPly);
              } else {
                onGoLive();
              }
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

        {/* Jump to live (or end of PGN) */}
        <button
          onClick={isPgnMode ? () => onNavigate(maxPly) : onGoLive}
          disabled={isLive || currentPly >= maxPly}
          className={`p-1 rounded-md disabled:opacity-30 disabled:pointer-events-none transition-colors ${
            isDark
              ? 'text-neutral-400 hover:text-white hover:bg-white/[0.08]'
              : 'text-neutral-500 hover:text-neutral-900 hover:bg-black/[0.05]'
          }`}
          title={isPgnMode ? 'Jump to End of Game' : 'Jump to Latest (Live)'}
        >
          <ChevronsRight className="w-4 h-4" />
        </button>

        {/* PGN Move Delay Selector - ONLY IN PGN / FEN SECTION, starts from 2s */}
        {isPgnMode && onChangeMoveDelay && (
          <div className="hidden sm:flex items-center gap-0.5 ml-1.5 pl-1.5 border-l border-neutral-700/40 font-mono text-[10px]">
            {[2, 3, 5, 10].map((d) => (
              <button
                key={d}
                type="button"
                onClick={() => onChangeMoveDelay(d)}
                className={`px-1.5 py-0.5 rounded font-bold transition-all ${
                  moveDelay === d
                    ? 'bg-[#e05338] text-white'
                    : isDark
                    ? 'text-neutral-400 hover:text-neutral-200'
                    : 'text-neutral-500 hover:text-neutral-800'
                }`}
                title={`Pacing delay: ${d}s per move`}
              >
                {d}s
              </button>
            ))}
          </div>
        )}
      </div>

      {/* 2. Inspected Position Display */}
      <div className="flex items-center gap-2 font-mono text-xs">
        {isSandbox ? (
          <div className="flex items-center gap-1.5">
            <span className="w-1.5 h-1.5 rounded-full bg-amber-400 animate-pulse" />
            <span className="text-amber-400 font-bold uppercase tracking-wider text-[11px]">
              Sandbox Analysis
            </span>
          </div>
        ) : currentPly === 0 ? (
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

      {/* 3. Live Status / PGN Playback Status / Exit Sandbox Pill */}
      <div>
        {isSandbox ? (
          <button
            onClick={onExitSandbox}
            className="flex items-center gap-1.5 px-2.5 py-0.5 rounded-full bg-amber-500/20 border border-amber-500/50 text-amber-400 hover:bg-amber-500/30 text-[10px] font-bold font-mono transition-all shadow-sm"
            title="Exit sandbox and resume match"
          >
            <RotateCcw className="w-3 h-3 text-amber-400" />
            EXIT SANDBOX
          </button>
        ) : isPgnMode ? (
          isPlaying ? (
            <div className="flex items-center gap-1.5 px-2 py-0.5 rounded-full bg-emerald-500/15 border border-emerald-500/30 text-emerald-400 text-[10px] font-bold font-mono">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
              PLAYING ({moveDelay}s)
            </div>
          ) : currentPly >= maxPly && maxPly > 0 ? (
            <div className="flex items-center gap-1.5 px-2 py-0.5 rounded-full bg-neutral-500/15 border border-neutral-500/30 text-neutral-400 text-[10px] font-bold font-mono">
              END
            </div>
          ) : (
            <div className="flex items-center gap-1.5 px-2 py-0.5 rounded-full bg-amber-500/15 border border-amber-500/30 text-amber-400 text-[10px] font-bold font-mono">
              PAUSED
            </div>
          )
        ) : isLive ? (
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