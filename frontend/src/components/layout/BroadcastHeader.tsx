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
  const eventName = metadata?.event_name || 'Live Match Broadcast';
  const speed = metadata?.speed ? metadata.speed.toUpperCase() : 'LIVE';
  const whiteName = metadata?.white_player?.username || 'White';
  const blackName = metadata?.black_player?.username || 'Black';

  return (
    <header className="w-full bg-[#10131a] border-b border-stone-800/90 px-3 sm:px-4 py-2 sm:py-2.5 flex items-center justify-between shadow-lg z-30 select-none">
      {/* Left: Exit button & Match branding */}
      <div className="flex items-center gap-2 sm:gap-3 min-w-0">
        <button
          onClick={onExit}
          className="p-1.5 rounded-lg bg-[#181c26] hover:bg-stone-800 text-stone-400 hover:text-stone-100 border border-stone-800 transition-colors shrink-0"
          title="Exit Broadcast Studio"
        >
          <ArrowLeft className="w-4 h-4" />
        </button>

        <div className="flex items-center gap-2 sm:gap-2.5 min-w-0">
          <div className="p-1.5 rounded-lg bg-amber-500/10 border border-amber-500/30 text-amber-400 shrink-0">
            <Trophy className="w-4 h-4" />
          </div>

          <div className="flex flex-col min-w-0">
            <div className="flex items-center gap-1.5 sm:gap-2">
              <h1 className="font-bold text-xs sm:text-sm text-stone-100 truncate tracking-tight">
                {eventName}
              </h1>
              <span className="text-[9px] sm:text-[10px] font-mono font-bold bg-[#181c26] text-amber-300 px-1.5 py-0.2 rounded border border-stone-700 shrink-0">
                {speed}
              </span>
            </div>
            {metadata && (
              <p className="text-[10px] sm:text-[11px] text-stone-400 truncate">
                {whiteName} vs {blackName}
              </p>
            )}
          </div>
        </div>
      </div>

      {/* Center: Live Broadcast Status Pill */}
      <div className="hidden lg:flex items-center gap-2 px-3 py-1 rounded-full bg-[#0a0c10] border border-stone-800 shadow-inner">
        {status === 'connected' && (
          <>
            <span className="w-2 h-2 rounded-full bg-rose-500 animate-pulse" />
            <span className="text-xs font-bold text-rose-400 tracking-wider">LIVE ON AIR</span>
          </>
        )}
        {status === 'connecting' && (
          <>
            <span className="w-2 h-2 rounded-full bg-amber-400 animate-pulse" />
            <span className="text-xs font-bold text-amber-400 tracking-wider">CONNECTING</span>
          </>
        )}
        {status === 'ended' && (
          <>
            <span className="w-2 h-2 rounded-full bg-stone-500" />
            <span className="text-xs font-bold text-stone-400 tracking-wider">CONCLUDED</span>
          </>
        )}
        {status === 'error' && (
          <>
            <span className="w-2 h-2 rounded-full bg-rose-500" />
            <span className="text-xs font-bold text-rose-400 tracking-wider">RECONNECTING</span>
          </>
        )}
      </div>

      {/* Right: Feature & Audio Controls */}
      <div className="flex items-center gap-1.5 sm:gap-2 shrink-0">
        {/* Return to Round Boards (Shown only when in an event round) */}
        {metadata?.round_id && (
          <button
            onClick={onExit}
            className="flex items-center gap-1.5 px-2 sm:px-2.5 py-1.5 rounded-lg border border-stone-800 bg-[#181c26] hover:bg-stone-800 text-stone-300 hover:text-stone-100 text-xs font-semibold transition-all"
            title="View all pairings in this round"
          >
            <LayoutGrid className="w-3.5 h-3.5 text-amber-400" />
            <span className="hidden md:inline">Round Boards</span>
          </button>
        )}

        {/* Flip Board Orientation */}
        <button
          onClick={onFlipBoard}
          className="flex items-center gap-1.5 px-2 sm:px-2.5 py-1.5 rounded-lg border border-stone-800 bg-[#181c26] hover:bg-stone-800 text-stone-300 hover:text-stone-100 hover:border-stone-700 text-xs font-semibold transition-all"
          title={`Flip Board (Currently ${boardOrientation === 'white' ? 'White' : 'Black'})`}
        >
          <RotateCw className="w-3.5 h-3.5 text-stone-400" />
          <span className="hidden sm:inline capitalize">{boardOrientation}</span>
        </button>

        {/* Toggle AI Voice Commentary (TTS) */}
        <button
          onClick={onToggleTts}
          className={`flex items-center gap-1.5 px-2 sm:px-2.5 py-1.5 rounded-lg border text-xs font-semibold transition-all ${enableTts
              ? 'bg-amber-500/15 border-amber-500/30 text-amber-300 hover:bg-amber-500/20'
              : 'bg-[#181c26] border-stone-800 text-stone-500 hover:text-stone-400'
            }`}
          title={enableTts ? 'AI Voice Commentary Active' : 'AI Voice Generation Disabled'}
        >
          {enableTts ? <Mic className="w-3.5 h-3.5 text-amber-400" /> : <MicOff className="w-3.5 h-3.5" />}
          <span className="hidden sm:inline">AI Voice: {enableTts ? 'ON' : 'OFF'}</span>
        </button>

        {/* Radio Audio Mute / Unmute */}
        <button
          onClick={onToggleMute}
          className={`flex items-center gap-1.5 px-2 sm:px-2.5 py-1.5 rounded-lg border text-xs font-semibold transition-all ${!isMuted
              ? 'bg-stone-800 border-stone-700 text-stone-200 hover:bg-stone-700/80'
              : 'bg-rose-500/15 border-rose-500/30 text-rose-300 hover:bg-rose-500/20'
            }`}
          title={isMuted ? 'Unmute Commentary Audio' : 'Mute Commentary Audio'}
        >
          {!isMuted ? <Volume2 className="w-4 h-4 text-amber-400" /> : <VolumeX className="w-4 h-4 text-rose-400" />}
          <span className="hidden sm:inline">{!isMuted ? 'RADIO ON' : 'MUTED'}</span>
        </button>
      </div>
    </header>
  );
};