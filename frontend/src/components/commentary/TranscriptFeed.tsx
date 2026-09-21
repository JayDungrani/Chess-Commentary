// src/components/commentary/TranscriptFeed.tsx

import React, { useEffect, useRef } from 'react';
import { Volume2, History } from 'lucide-react';
import type { CommentaryExchange } from '../../types/broadcast';
import { getEmotionBadge } from '../../utils/formatters';

interface TranscriptFeedProps {
  transcript: CommentaryExchange[];
}

const DYNAMIC_LABEL_MAP: Record<string, string> = {
  SOLO_HOST: 'Solo Host',
  SOLO_ANALYST: 'Solo Analyst',
  BANTER: 'Studio Banter',
  SILENCE: 'Pondering',
  PLAY_BY_PLAY: 'Play-by-Play',
};

export const TranscriptFeed: React.FC<TranscriptFeedProps> = ({ transcript }) => {
  const bottomAnchorRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to latest dialogue line
  useEffect(() => {
    bottomAnchorRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [transcript]);

  return (
    <div className="flex flex-col h-full bg-[#12151d]/70 rounded-2xl border border-stone-800/90 overflow-hidden shadow-inner">
      {/* Feed Header */}
      <div className="px-4 py-2.5 border-b border-stone-800/80 bg-[#12151d] flex items-center justify-between shrink-0">
        <div className="flex items-center gap-2">
          <History className="w-4 h-4 text-amber-400" />
          <span className="text-xs font-bold text-stone-200 uppercase tracking-wider">
            Broadcast Log
          </span>
        </div>
        <span className="text-[11px] font-mono text-stone-400">
          {transcript.length} turns
        </span>
      </div>

      {/* Transcript Scroll Area */}
      <div className="flex-1 p-3 overflow-y-auto space-y-3.5 min-h-0">
        {transcript.length === 0 ? (
          <div className="h-32 flex flex-col items-center justify-center text-stone-500 text-xs gap-1.5">
            <Volume2 className="w-5 h-5 opacity-40" />
            <span>Awaiting broadcast commentary...</span>
          </div>
        ) : (
          transcript.map((exchange, exIdx) => {
            const movePrefix = exchange.ply
              ? `${Math.floor((exchange.ply + 1) / 2)}${
                  exchange.turn_color === 'white' ? '.' : '...'
                }`
              : '';

            return (
              <div
                key={`${exchange.ply}-${exIdx}`}
                className="space-y-2 pb-2.5 border-b border-stone-800/50 last:border-b-0"
              >
                {/* Ply Header Tag */}
                {exchange.move_san && (
                  <div className="flex items-center gap-1.5 text-[11px] font-mono text-stone-400">
                    <span className="text-amber-400 font-bold">
                      {movePrefix} {exchange.move_san}
                    </span>
                    <span className="text-stone-600">•</span>
                    <span className="text-[10px] uppercase tracking-wide text-stone-500 font-medium">
                      {DYNAMIC_LABEL_MAP[exchange.dynamic] || exchange.dynamic.replace(/_/g, ' ')}
                    </span>
                  </div>
                )}

                {/* Individual Utterances in this Exchange */}
                {exchange.turns.map((turn, tIdx) => {
                  const isHost = turn.speaker === 'HOST';
                  const emotionInfo = getEmotionBadge(turn.emotion);

                  return (
                    <div
                      key={tIdx}
                      className="text-xs pl-2.5 border-l-2 py-0.5 space-y-1 transition-colors"
                      style={{
                        borderColor: isHost ? '#f59e0b' : '#a8a29e',
                      }}
                    >
                      <div className="flex items-center gap-2">
                        <span
                          className={`font-bold text-[11px] tracking-tight ${
                            isHost ? 'text-amber-300' : 'text-stone-300'
                          }`}
                        >
                          {isHost ? 'James' : 'Peter'}
                        </span>
                        <span
                          className={`text-[9px] px-1.5 py-0.2 rounded border font-medium ${emotionInfo.color} bg-[#0a0c10]`}
                        >
                          {emotionInfo.label}
                        </span>
                      </div>
                      <p className="text-stone-300 leading-relaxed font-sans select-text">
                        "{turn.text}"
                      </p>
                    </div>
                  );
                })}
              </div>
            );
          })
        )}
        <div ref={bottomAnchorRef} />
      </div>
    </div>
  );
};