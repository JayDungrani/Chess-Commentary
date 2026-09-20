// src/hooks/useChessClock.ts

import { useState, useEffect, useRef } from 'react';

interface UseChessClockProps {
  initialWhiteSeconds?: number | null;
  initialBlackSeconds?: number | null;
  activeTurn: 'white' | 'black';
  isGameOver: boolean;
  timeTroubleThreshold?: number;
}

export function useChessClock({
  initialWhiteSeconds,
  initialBlackSeconds,
  activeTurn,
  isGameOver,
  timeTroubleThreshold = 30.0,
}: UseChessClockProps) {
  const [whiteClock, setWhiteClock] = useState<number | null>(initialWhiteSeconds ?? null);
  const [blackClock, setBlackClock] = useState<number | null>(initialBlackSeconds ?? null);

  const lastUpdateRef = useRef<number>(Date.now());

  // Resync whenever server sends an authoritative clock snapshot
  useEffect(() => {
    if (initialWhiteSeconds != null) setWhiteClock(initialWhiteSeconds);
  }, [initialWhiteSeconds]);

  useEffect(() => {
    if (initialBlackSeconds != null) setBlackClock(initialBlackSeconds);
  }, [initialBlackSeconds]);

  // High-precision tick interval
  useEffect(() => {
    if (isGameOver) return;

    lastUpdateRef.current = Date.now();

    const timer = setInterval(() => {
      const now = Date.now();
      const elapsed = (now - lastUpdateRef.current) / 1000;
      lastUpdateRef.current = now;

      if (activeTurn === 'white') {
        setWhiteClock((prev) => (prev != null ? Math.max(0, prev - elapsed) : null));
      } else {
        setBlackClock((prev) => (prev != null ? Math.max(0, prev - elapsed) : null));
      }
    }, 100);

    return () => clearInterval(timer);
  }, [activeTurn, isGameOver]);

  const isWhiteTimeTrouble = whiteClock != null && whiteClock <= timeTroubleThreshold && whiteClock > 0;
  const isBlackTimeTrouble = blackClock != null && blackClock <= timeTroubleThreshold && blackClock > 0;

  return {
    whiteClock,
    blackClock,
    isWhiteTimeTrouble,
    isBlackTimeTrouble,
  };
}