// src/components/commentary/SpeakerAvatar.tsx

import React from 'react';
import { Radio, Award } from 'lucide-react';
import type { CommentatorRole, CommentaryEmotion } from '../../types/broadcast';
import { getEmotionBadge } from '../../utils/formatters';

interface SpeakerAvatarProps {
  role: CommentatorRole;
  isSpeaking: boolean;
  currentEmotion?: CommentaryEmotion | null;
}

const SPEAKER_PROFILES = {
  HOST: {
    name: 'James',
    title: 'Lead Play-by-Play',
    badgeClass: 'bg-amber-500/15 text-amber-300 border-amber-500/30',
    glowClass: 'border-amber-500/60 shadow-[0_0_16px_rgba(245,158,11,0.12)]',
    avatarBg: 'from-amber-950/40 to-[#12151d] text-amber-300 border-amber-500/30',
    waveBar: 'bg-amber-400',
    dotPing: 'bg-amber-400',
    dotBase: 'bg-amber-500',
  },
  ANALYST: {
    name: 'Peter',
    title: 'Grandmaster Analyst',
    badgeClass: 'bg-stone-700/30 text-stone-300 border-stone-600/40',
    glowClass: 'border-stone-400/50 shadow-[0_0_16px_rgba(214,211,209,0.10)]',
    avatarBg: 'from-stone-800/50 to-[#12151d] text-stone-200 border-stone-700/60',
    waveBar: 'bg-stone-300',
    dotPing: 'bg-stone-300',
    dotBase: 'bg-stone-200',
  },
};

export const SpeakerAvatar: React.FC<SpeakerAvatarProps> = ({
  role,
  isSpeaking,
  currentEmotion,
}) => {
  const profile = SPEAKER_PROFILES[role];
  const emotionInfo = currentEmotion ? getEmotionBadge(currentEmotion) : null;

  return (
    <div
      className={`relative flex-1 p-3.5 rounded-2xl border transition-all duration-300 ${
        isSpeaking
          ? `${profile.glowClass} bg-[#181c26] scale-[1.01]`
          : 'bg-[#12151d]/90 border-stone-800'
      }`}
    >
      {/* On-Air / Standby Status Chip */}
      <div className="flex items-center justify-between mb-2">
        <span
          className={`text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-full flex items-center gap-1.5 border ${
            isSpeaking
              ? 'bg-rose-500/20 text-rose-300 border-rose-500/40 animate-pulse'
              : 'bg-[#0a0c10] text-stone-500 border-stone-800'
          }`}
        >
          {isSpeaking ? (
            <>
              <span className="w-1.5 h-1.5 rounded-full bg-rose-500 animate-ping" />
              ON AIR
            </>
          ) : (
            'STANDBY'
          )}
        </span>

        {/* Dynamic Emotion Badge when speaking */}
        {isSpeaking && emotionInfo && (
          <span
            className={`text-[10px] font-bold px-2 py-0.5 rounded-md border ${emotionInfo.color} bg-[#0a0c10]/90`}
          >
            {emotionInfo.label}
          </span>
        )}
      </div>

      {/* Avatar Header & Identity */}
      <div className="flex items-center gap-3">
        <div
          className={`relative w-11 h-11 rounded-xl bg-gradient-to-b ${profile.avatarBg} border flex items-center justify-center shadow-lg shrink-0`}
        >
          {role === 'HOST' ? (
            <Radio className="w-5 h-5" />
          ) : (
            <Award className="w-5 h-5" />
          )}

          {/* Active Speaking Indicator Dot */}
          {isSpeaking && (
            <span className="absolute -top-1 -right-1 flex h-3 w-3">
              <span
                className={`animate-ping absolute inline-flex h-full w-full rounded-full ${profile.dotPing} opacity-75`}
              />
              <span
                className={`relative inline-flex rounded-full h-3 w-3 ${profile.dotBase} border-2 border-[#12151d]`}
              />
            </span>
          )}
        </div>

        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-1.5">
            <h4 className="font-bold text-sm text-stone-100 tracking-tight">
              {profile.name}
            </h4>
            <span
              className={`text-[9px] font-bold px-1.5 py-0.2 rounded border uppercase ${profile.badgeClass}`}
            >
              {role}
            </span>
          </div>
          <p className="text-[11px] text-stone-400 truncate">{profile.title}</p>
        </div>
      </div>

      {/* Live Audio Equalizer Waveform Animation */}
      <div className="mt-3 h-2.5 flex items-end justify-center gap-1 bg-[#0a0c10]/70 rounded-md px-2 py-0.5 border border-stone-800/80">
        {[0.4, 0.9, 0.6, 1.0, 0.5, 0.8, 0.3].map((heightMultiplier, idx) => (
          <span
            key={idx}
            style={{
              height: isSpeaking ? `${Math.max(20, heightMultiplier * 100)}%` : '25%',
              animationDuration: `${0.4 + (idx % 3) * 0.2}s`,
            }}
            className={`w-1 rounded-full transition-all duration-150 ${
              isSpeaking ? `${profile.waveBar} animate-pulse` : 'bg-stone-800'
            }`}
          />
        ))}
      </div>
    </div>
  );
};