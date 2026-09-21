// src/hooks/useBroadcastStream.ts

import { useState, useEffect, useRef, useCallback } from 'react';
import type {
  BroadcastEventType,
  BroadcastFrame,
  CommentaryExchange,
  GameMetadata,
  MoveEvaluation,
  ParsedMoveEvent,
  VisualCue,
} from '../types/broadcast';
import { radioEngine } from '../utils/audioQueue';

export type StreamStatus = 'idle' | 'connecting' | 'connected' | 'ended' | 'error';

export interface UseBroadcastStreamOptions {
  gameId: string | null;
  roundId?: string | null;
  replayAll?: boolean;
  tts?: boolean;
  autoConnect?: boolean;
  autoPlayAudio?: boolean;
  onFrame?: (frame: BroadcastFrame) => void;
  onAudioInterrupt?: () => void;
  onTermination?: (reason: string) => void;
}

const STARTING_FEN = 'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1';

export function useBroadcastStream({
  gameId,
  roundId = null,
  replayAll = false,
  tts = true,
  autoConnect = true,
  autoPlayAudio = true,
  onFrame,
  onAudioInterrupt,
  onTermination,
}: UseBroadcastStreamOptions) {
  // Connection state
  const [status, setStatus] = useState<StreamStatus>('idle');
  const [error, setError] = useState<string | null>(null);

  // Match and chess state
  const [metadata, setMetadata] = useState<GameMetadata | null>(null);
  const [fen, setFen] = useState<string>(STARTING_FEN);
  const [ply, setPly] = useState<number>(0);
  const [turn, setTurn] = useState<'white' | 'black'>('white');
  const [currentMove, setCurrentMove] = useState<ParsedMoveEvent | null>(null);
  const [moveHistory, setMoveHistory] = useState<ParsedMoveEvent[]>([]);

  // Engine analysis & visual signals
  const [evaluation, setEvaluation] = useState<MoveEvaluation | null>(null);
  const [visualCues, setVisualCues] = useState<VisualCue | null>(null);

  // Commentary & transcript state
  const [latestCommentary, setLatestCommentary] = useState<CommentaryExchange | null>(null);
  const [transcript, setTranscript] = useState<CommentaryExchange[]>([]);

  // Termination state
  const [terminationReason, setTerminationReason] = useState<string | null>(null);

  const eventSourceRef = useRef<EventSource | null>(null);

  // References for preferences and callbacks to prevent triggering reconnects/resets mid-game
  const ttsRef = useRef(tts);
  const autoPlayAudioRef = useRef(autoPlayAudio);
  const onFrameRef = useRef(onFrame);
  const onAudioInterruptRef = useRef(onAudioInterrupt);
  const onTerminationRef = useRef(onTermination);

  useEffect(() => {
    ttsRef.current = tts;
    if (!tts) {
      radioEngine.interrupt();
    }
  }, [tts]);

  useEffect(() => {
    autoPlayAudioRef.current = autoPlayAudio;
  }, [autoPlayAudio]);

  useEffect(() => {
    onFrameRef.current = onFrame;
  }, [onFrame]);

  useEffect(() => {
    onAudioInterruptRef.current = onAudioInterrupt;
  }, [onAudioInterrupt]);

  useEffect(() => {
    onTerminationRef.current = onTermination;
  }, [onTermination]);

  const resetState = useCallback(() => {
    setMetadata(null);
    setFen(STARTING_FEN);
    setPly(0);
    setTurn('white');
    setCurrentMove(null);
    setMoveHistory([]);
    setEvaluation(null);
    setVisualCues(null);
    setLatestCommentary(null);
    setTranscript([]);
    setTerminationReason(null);
    setError(null);
  }, []);

  const disconnect = useCallback(() => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      eventSourceRef.current = null;
    }
    radioEngine.interrupt();
    setStatus((prev) => (prev === 'ended' ? 'ended' : 'idle'));
  }, []);

  const connect = useCallback(() => {
    if (!gameId) return;

    disconnect();
    resetState();
    setStatus('connecting');

    // Build API endpoint URL based on route types
    const params = new URLSearchParams({
      replay_all: String(replayAll),
      tts: String(ttsRef.current),
    });

    const endpoint = roundId
      ? `/api/stream/broadcast/${encodeURIComponent(roundId)}/${encodeURIComponent(gameId)}?${params}`
      : `/api/stream/game/${encodeURIComponent(gameId)}?${params}`;

    const es = new EventSource(endpoint);
    eventSourceRef.current = es;

    es.onopen = () => {
      setStatus('connected');
      setError(null);
    };

    es.onmessage = (event) => {
      try {
        const frame: BroadcastFrame = JSON.parse(event.data);
        onFrameRef.current?.(frame);

        switch (frame.event_type) {
          case 'METADATA': {
            if (frame.metadata) {
              setMetadata(frame.metadata);
            }
            if (frame.fen) {
              setFen(frame.fen);
            }
            break;
          }

          case 'MOVE': {
            if (frame.fen) setFen(frame.fen);
            if (frame.ply != null) setPly(frame.ply);
            if (frame.turn) setTurn(frame.turn);

            if (frame.move) {
              setCurrentMove(frame.move);
              setMoveHistory((prev) => [...prev, frame.move!]);
            }

            if (frame.evaluation) {
              setEvaluation(frame.evaluation);
            }

            setVisualCues(frame.visual_cues || frame.evaluation?.visual_cues || null);

            if (frame.commentary) {
              setLatestCommentary(frame.commentary);
              setTranscript((prev) => [...prev, frame.commentary!]);

              // Queue audio turns sequentially for broadcast playback
              if (autoPlayAudioRef.current && ttsRef.current && frame.commentary.turns.length > 0) {
                radioEngine.enqueueTurns(frame.commentary.turns);
              }
            }
            break;
          }

          case 'PONDERING': {
            if (frame.commentary) {
              setLatestCommentary(frame.commentary);
              setTranscript((prev) => [...prev, frame.commentary!]);
              if (autoPlayAudioRef.current && ttsRef.current && frame.commentary.turns.length > 0) {
                radioEngine.enqueueTurns(frame.commentary.turns);
              }
            }
            break;
          }

          case 'AUDIO_INTERRUPT': {
            // Immediate priority override: dump audio buffer for blunders/brilliancies
            radioEngine.interrupt();
            onAudioInterruptRef.current?.();
            break;
          }

          case 'TERMINATION': {
            const reason = frame.termination_reason || 'Game concluded';
            setTerminationReason(reason);
            setStatus('ended');

            if (frame.fen) setFen(frame.fen);
            if (frame.ply != null) setPly(frame.ply);

            // Handle final sign-off commentary if present
            if (frame.commentary) {
              setLatestCommentary(frame.commentary);
              setTranscript((prev) => [...prev, frame.commentary!]);
              if (autoPlayAudioRef.current && ttsRef.current && frame.commentary.turns.length > 0) {
                radioEngine.enqueueTurns(frame.commentary.turns);
              }
            }

            onTerminationRef.current?.(reason);
            es.close();
            eventSourceRef.current = null;
            break;
          }

          case 'ERROR': {
            const errDetail = frame.error || 'Unknown broadcast error';
            setError(errDetail);
            setStatus('error');
            es.close();
            eventSourceRef.current = null;
            break;
          }

          default:
            break;
        }
      } catch (parseErr) {
        console.error('Failed to parse incoming broadcast frame:', parseErr);
      }
    };

    es.onerror = (err) => {
      // If server finished cleanly or connection was aborted
      if (es.readyState === EventSource.CLOSED) {
        setStatus((prev) => (prev === 'ended' ? 'ended' : 'idle'));
      } else {
        console.warn('Broadcast SSE connection error:', err);
        setError('Lost connection to live relay. Reconnecting...');
        setStatus('error');
      }
    };
  }, [
    gameId,
    roundId,
    replayAll,
    disconnect,
    resetState,
  ]);

  // Handle lifecycle and auto-connect
  useEffect(() => {
    if (autoConnect && gameId) {
      connect();
    }
    return () => {
      disconnect();
    };
  }, [autoConnect, gameId, roundId, replayAll, connect, disconnect]);

  return {
    // Stream status
    status,
    isConnected: status === 'connected',
    isGameOver: status === 'ended',
    error,

    // Match metadata & history
    metadata,
    fen,
    ply,
    turn,
    currentMove,
    moveHistory,

    // Engine telemetry
    evaluation,
    visualCues,

    // Commentary & audio transcript
    latestCommentary,
    transcript,
    terminationReason,

    // Controls
    connect,
    disconnect,
  };
}