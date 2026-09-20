// src/utils/formatters.ts

import type { MoveClassification, CommentaryEmotion } from '../types/broadcast';

/**
 * Formats raw clock seconds into mm:ss or h:mm:ss.
 */
export function formatClock(seconds: number | null | undefined): string {
  if (seconds == null || isNaN(seconds) || seconds < 0) return '--:--';
  const totalSeconds = Math.floor(seconds);
  const hours = Math.floor(totalSeconds / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const secs = totalSeconds % 60;

  if (hours > 0) {
    return `${hours}:${minutes.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  }
  return `${minutes.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
}

/**
 * Formats engine centipawns or mate distance into broadcast labels (+1.4, -0.6, M2).
 */
export function formatEval(scoreCp?: number | null, mateIn?: number | null): string {
  if (mateIn != null) {
    return mateIn > 0 ? `M${mateIn}` : `-M${Math.abs(mateIn)}`;
  }
  if (scoreCp != null) {
    const pawns = scoreCp / 100;
    return pawns > 0 ? `+${pawns.toFixed(1)}` : pawns.toFixed(1);
  }
  return '0.0';
}

/**
 * Calculates White's percentage share (0% to 100%) for the vertical Eval Bar.
 * 50% = Dead equal, 100% = Forced mate for White, 0% = Forced mate for Black.
 */
export function getEvalBarPercentage(scoreCp?: number | null, mateIn?: number | null): number {
  if (mateIn != null) {
    return mateIn > 0 ? 98 : 2;
  }
  if (scoreCp == null) return 50;

  // Clamped logistic scaling (400cp scale)
  const clamped = Math.max(-1500, Math.min(1500, scoreCp));
  const winProb = 1 / (1 + Math.pow(10, -clamped / 400));
  return Math.max(5, Math.min(95, Math.round(winProb * 100)));
}

/**
 * Converts ply number to standard chess notation number (e.g., Ply 14 -> "7...").
 */
export function formatPlyToMoveNumber(ply: number, turn: 'white' | 'black'): string {
  const moveNumber = Math.floor((ply + 1) / 2);
  return turn === 'white' ? `${moveNumber}.` : `${moveNumber}...`;
}

/**
 * Returns styling classes for move quality badges.
 */
export function getClassificationStyles(classification?: MoveClassification): {
  bg: string;
  text: string;
  border: string;
} {
  switch (classification) {
    case 'BRILLIANT':
      return { bg: 'bg-cyan-500/20', text: 'text-cyan-400', border: 'border-cyan-500/50' };
    case 'BEST':
      return { bg: 'bg-emerald-500/20', text: 'text-emerald-400', border: 'border-emerald-500/50' };
    case 'EXCELLENT':
      return { bg: 'bg-green-500/20', text: 'text-green-400', border: 'border-green-500/50' };
    case 'GOOD':
      return { bg: 'bg-blue-500/20', text: 'text-blue-400', border: 'border-blue-500/50' };
    case 'BOOK':
      return { bg: 'bg-purple-500/20', text: 'text-purple-400', border: 'border-purple-500/50' };
    case 'INACCURACY':
      return { bg: 'bg-yellow-500/20', text: 'text-yellow-400', border: 'border-yellow-500/50' };
    case 'MISTAKE':
      return { bg: 'bg-orange-500/20', text: 'text-orange-400', border: 'border-orange-500/50' };
    case 'BLUNDER':
      return { bg: 'bg-red-500/20', text: 'text-red-400', border: 'border-red-500/50' };
    default:
      return { bg: 'bg-slate-700/20', text: 'text-slate-300', border: 'border-slate-600/50' };
  }
}

/**
 * Formats commentary emotion to broadcast card tags.
 */
export function getEmotionBadge(emotion: CommentaryEmotion): { label: string; color: string } {
  switch (emotion) {
    case 'excited':
      return { label: '🔥 Excited', color: 'text-amber-400 border-amber-500/30' };
    case 'shocked':
      return { label: '⚡ Shocked', color: 'text-rose-400 border-rose-500/30' };
    case 'tense':
      return { label: '⏱️ Tense', color: 'text-orange-400 border-orange-500/30' };
    case 'analytical':
      return { label: '🧠 Analytical', color: 'text-cyan-400 border-cyan-500/30' };
    case 'humorous':
      return { label: '😄 Humorous', color: 'text-yellow-400 border-yellow-500/30' };
    case 'neutral':
    default:
      return { label: '🎙️ Play-by-Play', color: 'text-slate-400 border-slate-700' };
  }
}