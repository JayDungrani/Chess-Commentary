// src/components/commentary/CommentaryStudio.tsx

import React from 'react';
import { Radio, Volume2, Sparkles } from 'lucide-react';
import type {
  CommentaryExchange,
  CommentatorRole,
  DialogueTurn,
} from '../../types/broadcast';
import { SpeakerAvatar } from './SpeakerAvatar';
import { TranscriptFeed } from './TranscriptFeed';

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
      <div className="relative p-4 rounded-2xl bg-[#12151d] border border-stone-800 shadow-xl overflow-hidden min-h-[115px] shrink-0 flex flex-col justify-between">
        {/* Subtle Top Accent Line */}
        <div
          className={`absolute top-0 left-0 right-0 h-[2px] transition-colors duration-500 ${
            isSpeaking
              ? isHost
                ? 'bg-amber-400 shadow-[0_0_8px_rgba(251,191,36,0.3)]'
                : 'bg-stone-300 shadow-[0_0_8px_rgba(214,211,209,0.3)]'
              : 'bg-stone-800'
          }`}
        />

        <div className="space-y-2">
          {/* Header metadata */}
          <div className="flex items-center justify-between text-[11px]">
            <div className="flex items-center gap-1.5 font-bold tracking-wider uppercase">
              <Sparkles
                className={`w-3.5 h-3.5 ${
                  isSpeaking ? 'text-amber-400' : 'text-stone-500'
                }`}
              />
              <span className={isHost ? 'text-amber-300' : 'text-stone-300'}>
                {displayTurn
                  ? `${displayTurn.speaker === 'HOST' ? 'James' : 'Peter'} Speaking`
                  : 'Live Broadcast'}
              </span>
            </div>

            {isSpeaking && (
              <div className="flex items-center gap-1.5 text-rose-400 font-mono text-[10px] font-bold">
                <Volume2 className="w-3.5 h-3.5 animate-bounce" />
                <span>NARRATING</span>
              </div>
            )}
          </div>

          {/* Spoken Narration Script */}
          <p className="text-sm font-medium text-stone-200 leading-relaxed select-text italic">
            {displayTurn ? (
              `"${displayTurn.text}"`
            ) : (
              <span className="not-italic text-stone-500">
                Waiting for the first move to hit the broadcast board...
              </span>
            )}
          </p>
        </div>

        {/* Audio Duration Estimate Footer */}
        {displayTurn?.estimated_duration_seconds != null && (
          <div className="flex items-center justify-end text-[10px] font-mono text-stone-500 pt-1">
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