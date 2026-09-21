// src/components/layout/BroadcastHeader.tsx

import React from 'react';
import {
  Volume2,
  VolumeX,
  Mic,
  MicOff,
  ArrowLeft,
  Trophy,
  RotateCw,
  LayoutGrid,
} from 'lucide-react';
import { type GameMetadata } from '../../types/broadcast';
import { ThemeToggle } from '../common/ThemeToggle';
import { useTheme } from '../../context/ThemeContext';

interface BroadcastHeaderProps {
  metadata?: GameMetadata | null;
  status: 'idle' | 'connecting' | 'connected' | 'ended' | 'error';
  isMuted: boolean;
  onToggleMute: () => void;
  enableTts: boolean;
  onToggleTts: () => void;
  onExit: () => void;
  boardOrientation: 'white' | 'black';
  onFlipBoard: () => void;
  round_id?: string;
}

export const BroadcastHeader: React.FC<BroadcastHeaderProps> = ({
  metadata,
  status,
  isMuted,
  onToggleMute,
  enableTts,
  onToggleTts,
  onExit,
  boardOrientation,
  onFlipBoard,
}) => {
  const { isDark } = useTheme();
  const eventName = metadata?.event_name || 'Live Match Broadcast';
  const speed = metadata?.speed ? metadata.speed.toUpperCase() : 'LIVE';
  const whiteName = metadata?.white_player?.username || 'White';
  const blackName = metadata?.black_player?.username || 'Black';

  return (
    <header
      className={`w-full border-b px-3 sm:px-4 py-2 sm:py-2.5 flex items-center justify-between shadow-sm z-30 select-none transition-colors duration-200 ${
        isDark ? 'bg-[#13151b] border-white/[0.08]' : 'bg-white border-neutral-200'
      }`}
    >
      {/* Left: Exit button & Match branding */}
      <div className="flex items-center gap-2 sm:gap-3 min-w-0">
        <button
          onClick={onExit}
          className={`p-1.5 rounded-lg border transition-colors shrink-0 ${
            isDark
              ? 'bg-[#181c26] hover:bg-neutral-800 text-neutral-400 hover:text-neutral-100 border-white/[0.08]'
              : 'bg-neutral-100 hover:bg-neutral-200 text-neutral-600 hover:text-neutral-900 border-neutral-200'
          }`}
          title="Exit Broadcast Studio"
        >
          <ArrowLeft className="w-4 h-4" />
        </button>

        <div className="flex items-center gap-2 sm:gap-2.5 min-w-0">
          <div className="p-1.5 rounded-lg bg-[#e05338]/10 border border-[#e05338]/25 text-[#e05338] shrink-0">
            <Trophy className="w-4 h-4" />
          </div>

          <div className="flex flex-col min-w-0">
            <div className="flex items-center gap-1.5 sm:gap-2">
              <h1
                className={`font-bold text-xs sm:text-sm truncate tracking-tight ${
                  isDark ? 'text-neutral-100' : 'text-neutral-900'
                }`}
              >
                {eventName}
              </h1>
              <span
                className={`text-[9px] sm:text-[10px] font-mono font-bold px-1.5 py-0.2 rounded border shrink-0 ${
                  isDark
                    ? 'bg-[#181c26] text-[#e05338] border-white/[0.08]'
                    : 'bg-neutral-100 text-[#e05338] border-neutral-200'
                }`}
              >
                {speed}
              </span>
            </div>
            {metadata && (
              <p
                className={`text-[10px] sm:text-[11px] truncate ${
                  isDark ? 'text-neutral-400' : 'text-neutral-500'
                }`}
              >
                {whiteName} vs {blackName}
              </p>
            )}
          </div>
        </div>
      </div>

      {/* Center: Live Broadcast Status Pill */}
      <div
        className={`hidden lg:flex items-center gap-2 px-3 py-1 rounded-full border shadow-inner ${
          isDark ? 'bg-[#0b0c0f] border-white/[0.08]' : 'bg-neutral-100 border-neutral-200'
        }`}
      >
        {status === 'connected' && (
          <>
            <span className="w-2 h-2 rounded-full bg-[#e05338] animate-pulse" />
            <span className="text-xs font-bold text-[#e05338] tracking-wider">LIVE ON AIR</span>
          </>
        )}
        {status === 'connecting' && (
          <>
            <span className="w-2 h-2 rounded-full bg-amber-500 animate-pulse" />
            <span className="text-xs font-bold text-amber-500 tracking-wider">CONNECTING</span>
          </>
        )}
        {status === 'ended' && (
          <>
            <span className="w-2 h-2 rounded-full bg-neutral-400" />
            <span
              className={`text-xs font-bold tracking-wider ${
                isDark ? 'text-neutral-400' : 'text-neutral-500'
              }`}
            >
              CONCLUDED
            </span>
          </>
        )}
        {status === 'error' && (
          <>
            <span className="w-2 h-2 rounded-full bg-[#e05338]" />
            <span className="text-xs font-bold text-[#e05338] tracking-wider">RECONNECTING</span>
          </>
        )}
      </div>

      {/* Right: Feature & Audio Controls */}
      <div className="flex items-center gap-1.5 sm:gap-2 shrink-0">
        {/* Return to Round Boards (Shown only when in an event round) */}
        {metadata?.round_id && (
          <button
            onClick={onExit}
            className={`flex items-center gap-1.5 px-2 sm:px-2.5 py-1.5 rounded-lg border text-xs font-semibold transition-all ${
              isDark
                ? 'border-white/[0.08] bg-[#181c26] hover:bg-neutral-800 text-neutral-300 hover:text-white'
                : 'border-neutral-200 bg-neutral-100 hover:bg-neutral-200 text-neutral-700 hover:text-neutral-900'
            }`}
            title="View all pairings in this round"
          >
            <LayoutGrid className="w-3.5 h-3.5 text-[#e05338]" />
            <span className="hidden md:inline">Round Boards</span>
          </button>
        )}

        {/* Flip Board Orientation */}
        <button
          onClick={onFlipBoard}
          className={`flex items-center gap-1.5 px-2 sm:px-2.5 py-1.5 rounded-lg border text-xs font-semibold transition-all ${
            isDark
              ? 'border-white/[0.08] bg-[#181c26] hover:bg-neutral-800 text-neutral-300 hover:text-white'
              : 'border-neutral-200 bg-neutral-100 hover:bg-neutral-200 text-neutral-700 hover:text-neutral-900'
          }`}
          title={`Flip Board (Currently ${boardOrientation === 'white' ? 'White' : 'Black'})`}
        >
          <RotateCw className={`w-3.5 h-3.5 ${isDark ? 'text-neutral-400' : 'text-neutral-500'}`} />
          <span className="hidden sm:inline capitalize">{boardOrientation}</span>
        </button>

        {/* Toggle AI Voice Commentary (TTS) */}
        <button
          onClick={onToggleTts}
          className={`flex items-center gap-1.5 px-2 sm:px-2.5 py-1.5 rounded-lg border text-xs font-semibold transition-all ${
            enableTts
              ? 'bg-[#e05338]/15 border-[#e05338]/30 text-[#e05338] hover:bg-[#e05338]/20'
              : isDark
              ? 'bg-[#181c26] border-white/[0.08] text-neutral-500 hover:text-neutral-400'
              : 'bg-neutral-100 border-neutral-200 text-neutral-400 hover:text-neutral-600'
          }`}
          title={enableTts ? 'AI Voice Commentary Active' : 'AI Voice Generation Disabled'}
        >
          {enableTts ? (
            <Mic className="w-3.5 h-3.5 text-[#e05338]" />
          ) : (
            <MicOff className="w-3.5 h-3.5" />
          )}
          <span className="hidden sm:inline">AI Voice: {enableTts ? 'ON' : 'OFF'}</span>
        </button>

        {/* Radio Audio Mute / Unmute */}
        <button
          onClick={onToggleMute}
          className={`flex items-center gap-1.5 px-2 sm:px-2.5 py-1.5 rounded-lg border text-xs font-semibold transition-all ${
            !isMuted
              ? isDark
                ? 'bg-[#181c26] border-white/[0.08] text-neutral-200 hover:bg-neutral-800'
                : 'bg-neutral-100 border-neutral-200 text-neutral-800 hover:bg-neutral-200'
              : 'bg-[#e05338]/15 border-[#e05338]/30 text-[#e05338] hover:bg-[#e05338]/20'
          }`}
          title={isMuted ? 'Unmute Commentary Audio' : 'Mute Commentary Audio'}
        >
          {!isMuted ? (
            <Volume2 className="w-4 h-4 text-[#e05338]" />
          ) : (
            <VolumeX className="w-4 h-4 text-[#e05338]" />
          )}
          <span className="hidden sm:inline">{!isMuted ? 'RADIO ON' : 'MUTED'}</span>
        </button>

        {/* Dark / Light Theme Toggle */}
        <ThemeToggle showLabel={false} />
      </div>
    </header>
  );
};