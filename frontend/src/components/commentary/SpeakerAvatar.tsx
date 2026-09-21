// src/components/commentary/SpeakerAvatar.tsx

import React from 'react';
import { Radio, Award } from 'lucide-react';
import type { CommentatorRole, CommentaryEmotion } from '../../types/broadcast';
import { getEmotionBadge } from '../../utils/formatters';
import { useTheme } from '../../context/ThemeContext';

interface SpeakerAvatarProps {
  role: CommentatorRole;
  isSpeaking: boolean;
  currentEmotion?: CommentaryEmotion | null;
}

const SPEAKER_PROFILES = {
  HOST: {
    name: 'James',
    title: 'Lead Play-by-Play',
    badgeClass: 'bg-[#e05338]/15 text-[#e05338] border-[#e05338]/30',
    glowClass: 'border-[#e05338]/60 shadow-[0_0_16px_rgba(224,83,56,0.12)]',
    avatarBgDark: 'from-[#e05338]/25 to-[#13151b] text-[#e05338] border-[#e05338]/30',
    avatarBgLight: 'from-[#e05338]/15 to-neutral-100 text-[#e05338] border-[#e05338]/25',
    waveBar: 'bg-[#e05338]',
    dotPing: 'bg-[#e05338]',
    dotBase: 'bg-[#e05338]',
  },
  ANALYST: {
    name: 'Peter',
    title: 'Grandmaster Analyst',
    badgeClass: 'bg-neutral-500/15 text-neutral-400 border-neutral-500/30',
    glowClass: 'border-neutral-400/50 shadow-[0_0_16px_rgba(200,200,200,0.08)]',
    avatarBgDark: 'from-neutral-800/60 to-[#13151b] text-neutral-300 border-neutral-700/60',
    avatarBgLight: 'from-neutral-200 to-neutral-100 text-neutral-700 border-neutral-300',
    waveBar: 'bg-neutral-400',
    dotPing: 'bg-neutral-400',
    dotBase: 'bg-neutral-300',
  },
};

export const SpeakerAvatar: React.FC<SpeakerAvatarProps> = ({
  role,
  isSpeaking,
  currentEmotion,
}) => {
  const { isDark } = useTheme();
  const profile = SPEAKER_PROFILES[role];
  const emotionInfo = currentEmotion ? getEmotionBadge(currentEmotion) : null;

  return (
    <div
      className={`relative flex-1 p-3.5 rounded-2xl border transition-all duration-200 ${
        isSpeaking
          ? `${profile.glowClass} ${isDark ? 'bg-[#181c26]' : 'bg-white'} scale-[1.01]`
          : isDark
          ? 'bg-[#13151b]/90 border-white/[0.08]'
          : 'bg-white/90 border-black/[0.08] shadow-sm'
      }`}
    >
      {/* On-Air / Standby Status Chip */}
      <div className="flex items-center justify-between mb-2">
        <span
          className={`text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-full flex items-center gap-1.5 border ${
            isSpeaking
              ? 'bg-[#e05338]/15 text-[#e05338] border-[#e05338]/35 animate-pulse'
              : isDark
              ? 'bg-[#0b0c0f] text-neutral-500 border-white/[0.06]'
              : 'bg-neutral-100 text-neutral-400 border-neutral-200'
          }`}
        >
          {isSpeaking ? (
            <>
              <span className="w-1.5 h-1.5 rounded-full bg-[#e05338] animate-ping" />
              ON AIR
            </>
          ) : (
            'STANDBY'
          )}
        </span>

        {/* Dynamic Emotion Badge when speaking */}
        {isSpeaking && emotionInfo && (
          <span
            className={`text-[10px] font-bold px-2 py-0.5 rounded-md border ${emotionInfo.color} ${
              isDark ? 'bg-[#0b0c0f]/90' : 'bg-neutral-100'
            }`}
          >
            {emotionInfo.label}
          </span>
        )}
      </div>

      {/* Avatar Header & Identity */}
      <div className="flex items-center gap-3">
        <div
          className={`relative w-11 h-11 rounded-xl bg-gradient-to-b ${
            isDark ? profile.avatarBgDark : profile.avatarBgLight
          } border flex items-center justify-center shadow-lg shrink-0`}
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
                className={`relative inline-flex rounded-full h-3 w-3 ${profile.dotBase} border-2 ${
                  isDark ? 'border-[#13151b]' : 'border-white'
                }`}
              />
            </span>
          )}
        </div>

        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-1.5">
            <h4
              className={`font-bold text-sm tracking-tight ${
                isDark ? 'text-neutral-100' : 'text-neutral-900'
              }`}
            >
              {profile.name}
            </h4>
            <span
              className={`text-[9px] font-bold px-1.5 py-0.2 rounded border uppercase ${profile.badgeClass}`}
            >
              {role}
            </span>
          </div>
          <p className={`text-[11px] truncate ${isDark ? 'text-neutral-400' : 'text-neutral-500'}`}>
            {profile.title}
          </p>
        </div>
      </div>

      {/* Live Audio Equalizer Waveform Animation */}
      <div
        className={`mt-3 h-2.5 flex items-end justify-center gap-1 rounded-md px-2 py-0.5 border ${
          isDark
            ? 'bg-[#0b0c0f]/80 border-white/[0.06]'
            : 'bg-neutral-100/80 border-neutral-200'
        }`}
      >
        {[0.4, 0.9, 0.6, 1.0, 0.5, 0.8, 0.3].map((heightMultiplier, idx) => (
          <span
            key={idx}
            style={{
              height: isSpeaking ? `${Math.max(20, heightMultiplier * 100)}%` : '25%',
              animationDuration: `${0.4 + (idx % 3) * 0.2}s`,
            }}
            className={`w-1 rounded-full transition-all duration-150 ${
              isSpeaking
                ? `${profile.waveBar} animate-pulse`
                : isDark
                ? 'bg-neutral-800'
                : 'bg-neutral-300'
            }`}
          />
        ))}
      </div>
    </div>
  );
};