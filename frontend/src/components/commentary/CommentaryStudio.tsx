// src/components/commentary/CommentaryStudio.tsx

import React from 'react';
import { Volume2, Sparkles } from 'lucide-react';
import type {
  CommentaryExchange,
  CommentatorRole,
  DialogueTurn,
} from '../../types/broadcast';
import { SpeakerAvatar } from './SpeakerAvatar';
import { TranscriptFeed } from './TranscriptFeed';
import { useTheme } from '../../context/ThemeContext';

interface CommentaryStudioProps {
  latestCommentary?: CommentaryExchange | null;
  transcript: CommentaryExchange[];
  activeSpeaker: CommentatorRole | null;
  currentTurn: DialogueTurn | null;
  isSpeaking: boolean;
}

export const CommentaryStudio: React.FC<CommentaryStudioProps> = ({
  transcript,
  activeSpeaker,
  currentTurn,
  isSpeaking,
}) => {
  const { isDark } = useTheme();
  // Determine which text to display on the main studio board
  const displayTurn: DialogueTurn | null =
    currentTurn ||
    (transcript.length > 0
      ? transcript[transcript.length - 1].turns[0]
      : null);

  const isHost = activeSpeaker === 'HOST' || displayTurn?.speaker === 'HOST';

  return (
    <div className="flex flex-col h-full space-y-3 min-h-0">
      {/* 1. Commentators Desk (Avatars) */}
      <div className="flex items-center gap-3 shrink-0">
        <SpeakerAvatar
          role="HOST"
          isSpeaking={activeSpeaker === 'HOST'}
          currentEmotion={
            activeSpeaker === 'HOST' ? currentTurn?.emotion : null
          }
        />
        <SpeakerAvatar
          role="ANALYST"
          isSpeaking={activeSpeaker === 'ANALYST'}
          currentEmotion={
            activeSpeaker === 'ANALYST' ? currentTurn?.emotion : null
          }
        />
      </div>

      {/* 2. Active Speech Bubble / Hero Dialogue Card */}
      <div
        className={`relative p-4 rounded-2xl border shadow-xl overflow-hidden min-h-[115px] shrink-0 flex flex-col justify-between transition-colors duration-200 ${
          isDark
            ? 'bg-[#13151b] border-white/[0.08] shadow-black/60'
            : 'bg-white border-black/[0.08] shadow-neutral-300/40'
        }`}
      >
        {/* Subtle Top Accent Line */}
        <div
          className={`absolute top-0 left-0 right-0 h-[2px] transition-colors duration-300 ${
            isSpeaking
              ? isHost
                ? 'bg-[#e05338] shadow-[0_0_8px_rgba(224,83,56,0.4)]'
                : isDark
                ? 'bg-neutral-300 shadow-[0_0_8px_rgba(255,255,255,0.3)]'
                : 'bg-neutral-600'
              : isDark
              ? 'bg-white/[0.05]'
              : 'bg-black/[0.05]'
          }`}
        />

        <div className="space-y-2">
          {/* Header metadata */}
          <div className="flex items-center justify-between text-[11px]">
            <div className="flex items-center gap-1.5 font-bold tracking-wider uppercase">
              <Sparkles
                className={`w-3.5 h-3.5 ${
                  isSpeaking ? 'text-[#e05338]' : isDark ? 'text-neutral-500' : 'text-neutral-400'
                }`}
              />
              <span className={isHost ? 'text-[#e05338]' : isDark ? 'text-neutral-200' : 'text-neutral-800'}>
                {displayTurn
                  ? `${displayTurn.speaker === 'HOST' ? 'James' : 'Peter'} Speaking`
                  : 'Live Broadcast'}
              </span>
            </div>

            {isSpeaking && (
              <div className="flex items-center gap-1.5 text-[#e05338] font-mono text-[10px] font-bold">
                <Volume2 className="w-3.5 h-3.5 animate-bounce" />
                <span>NARRATING</span>
              </div>
            )}
          </div>

          {/* Spoken Narration Script */}
          <p
            className={`text-sm font-medium leading-relaxed select-text italic ${
              isDark ? 'text-neutral-200' : 'text-neutral-800'
            }`}
          >
            {displayTurn ? (
              `"${displayTurn.text}"`
            ) : (
              <span className={`not-italic ${isDark ? 'text-neutral-500' : 'text-neutral-400'}`}>
                Waiting for the first move to hit the broadcast board...
              </span>
            )}
          </p>
        </div>

        {/* Audio Duration Estimate Footer */}
        {displayTurn?.estimated_duration_seconds != null && (
          <div
            className={`flex items-center justify-end text-[10px] font-mono pt-1 ${
              isDark ? 'text-neutral-500' : 'text-neutral-400'
            }`}
          >
            <span>~{displayTurn.estimated_duration_seconds.toFixed(1)}s voice clip</span>
          </div>
        )}
      </div>

      {/* 3. Real-Time Broadcast Transcript Feed */}
      <div className="flex-1 min-h-0 overflow-hidden">
        <TranscriptFeed transcript={transcript} />
      </div>
    </div>
  );
};