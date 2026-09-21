// src/components/commentary/TranscriptFeed.tsx

import React, { useEffect, useRef } from 'react';
import { Volume2, History } from 'lucide-react';
import type { CommentaryExchange } from '../../types/broadcast';
import { getEmotionBadge } from '../../utils/formatters';
import { useTheme } from '../../context/ThemeContext';

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
  const { isDark } = useTheme();
  const bottomAnchorRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to latest dialogue line
  useEffect(() => {
    bottomAnchorRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [transcript]);

  return (
    <div
      className={`flex flex-col h-full rounded-2xl border overflow-hidden shadow-inner transition-colors duration-200 ${
        isDark ? 'bg-[#13151b]/70 border-white/[0.08]' : 'bg-white/90 border-black/[0.08]'
      }`}
    >
      {/* Feed Header */}
      <div
        className={`px-4 py-2.5 border-b flex items-center justify-between shrink-0 ${
          isDark ? 'border-white/[0.06] bg-[#13151b]' : 'border-black/[0.06] bg-neutral-50'
        }`}
      >
        <div className="flex items-center gap-2">
          <History className="w-4 h-4 text-[#e05338]" />
          <span
            className={`text-xs font-bold uppercase tracking-wider ${
              isDark ? 'text-neutral-200' : 'text-neutral-800'
            }`}
          >
            Broadcast Log
          </span>
        </div>
        <span className="text-[11px] font-mono text-neutral-500">
          {transcript.length} turns
        </span>
      </div>

      {/* Transcript Scroll Area */}
      <div className="flex-1 p-3 overflow-y-auto space-y-3.5 min-h-0">
        {transcript.length === 0 ? (
          <div className="h-32 flex flex-col items-center justify-center text-neutral-500 text-xs gap-1.5">
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
                className={`space-y-2 pb-2.5 border-b last:border-b-0 ${
                  isDark ? 'border-white/[0.05]' : 'border-black/[0.05]'
                }`}
              >
                {/* Ply Header Tag */}
                {exchange.move_san && (
                  <div className="flex items-center gap-1.5 text-[11px] font-mono text-neutral-500">
                    <span className="text-[#e05338] font-bold">
                      {movePrefix} {exchange.move_san}
                    </span>
                    <span className={isDark ? 'text-neutral-600' : 'text-neutral-400'}>•</span>
                    <span className="text-[10px] uppercase tracking-wide font-medium">
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
                        borderColor: isHost ? '#e05338' : isDark ? '#52525b' : '#a1a1aa',
                      }}
                    >
                      <div className="flex items-center gap-2">
                        <span
                          className={`font-bold text-[11px] tracking-tight ${
                            isHost
                              ? 'text-[#e05338]'
                              : isDark
                              ? 'text-neutral-300'
                              : 'text-neutral-700'
                          }`}
                        >
                          {isHost ? 'James' : 'Peter'}
                        </span>
                        <span
                          className={`text-[9px] px-1.5 py-0.2 rounded border font-medium ${
                            emotionInfo.color
                          } ${isDark ? 'bg-[#0b0c0f]' : 'bg-neutral-100'}`}
                        >
                          {emotionInfo.label}
                        </span>
                      </div>
                      <p
                        className={`leading-relaxed font-sans select-text ${
                          isDark ? 'text-neutral-300' : 'text-neutral-700'
                        }`}
                      >
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