// src/hooks/useAudioNarrator.ts

import { useState, useEffect, useCallback } from 'react';
import type { CommentatorRole, DialogueTurn } from '../types/broadcast';
import { radioEngine } from '../utils/audioQueue';

export function useAudioNarrator() {
  const [activeSpeaker, setActiveSpeaker] = useState<CommentatorRole | null>(null);
  const [currentTurn, setCurrentTurn] = useState<DialogueTurn | null>(null);
  const [isMuted, setIsMuted] = useState<boolean>(false);

  useEffect(() => {
    radioEngine.setSpeakerCallback((speaker, turn) => {
      setActiveSpeaker(speaker);
      setCurrentTurn(turn);
    });

    return () => {
      radioEngine.setSpeakerCallback(() => {});
    };
  }, []);

  const toggleMute = useCallback(() => {
    setIsMuted((prev) => {
      const next = !prev;
      radioEngine.setMuted(next);
      return next;
    });
  }, []);

  const stopAudio = useCallback(() => {
    radioEngine.interrupt();
    setActiveSpeaker(null);
    setCurrentTurn(null);
  }, []);

  return {
    activeSpeaker,
    currentTurn,
    isMuted,
    isSpeaking: activeSpeaker !== null,
    toggleMute,
    stopAudio,
  };
}