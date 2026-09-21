// src/views/StudioView.tsx

import React, { useState, useEffect, useRef, useMemo, useCallback } from 'react';
import { useBroadcastStream } from '../hooks/useBroadcastStream';
import { useChessClock } from '../hooks/useChessClock';
import { useAudioNarrator } from '../hooks/useAudioNarrator';

import { BroadcastHeader } from '../components/layout/BroadcastHeader';
import { TickerBar } from '../components/layout/TickerBar';
import { ChessStudioBoard } from '../components/board/ChessStudioBoard';
import { EvalBar } from '../components/board/EvalBar';
import { PlayerCard } from '../components/board/PlayerCard';
import { CommentaryStudio } from '../components/commentary/CommentaryStudio';
import { MoveNavigator } from '../components/board/MoveNavigator';
import { useTheme } from '../context/ThemeContext';
import type { MoveEvaluation, ParsedMoveEvent, VisualCue, BroadcastFrame } from '../types/broadcast';

const DEFAULT_CHESS_START_FEN = 'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1';

/**
 * Extracts whose turn it is to move directly from the FEN string.
 * FEN format: "<placement> <side_to_move> <castling> <en_passant> <halfmove> <fullmove>"
 */
const getSideToMoveFromFen = (fenString?: string | null): 'white' | 'black' => {
  if (!fenString) return 'white';
  const parts = fenString.trim().split(/\s+/);
  if (parts.length > 1) {
    return parts[1].toLowerCase() === 'b' ? 'black' : 'white';
  }
  return 'white';
};

interface MoveSnapshot {
  ply: number;
  fen: string;
  move: ParsedMoveEvent | null;
  evaluation: MoveEvaluation | null;
  visualCues: VisualCue | null;
}

interface StudioViewProps {
  gameId: string;
  roundId?: string;
  initialEnableTts?: boolean;
  replayAll?: boolean;
  onExit: () => void;
}

export const StudioView: React.FC<StudioViewProps> = ({
  gameId,
  roundId,
  initialEnableTts = true,
  replayAll = false,
  onExit,
}) => {
  const { isDark } = useTheme();
  const [enableTts, setEnableTts] = useState(initialEnableTts);
  const [boardOrientation, setBoardOrientation] = useState<'white' | 'black'>('white');
  const [boardHeight, setBoardHeight] = useState<number | undefined>(undefined);
  const handleFlipBoard = () => {
    setBoardOrientation((prev) => (prev === 'white' ? 'black' : 'white'));
  };
  // Move history and navigation state
  const [history, setHistory] = useState<MoveSnapshot[]>([]);
  const [inspectedPly, setInspectedPly] = useState<number | null>(null);
  const previousLatestPlyRef = useRef<number | null>(null);

  // Initialize start position (ply 0) and reset on match/round change
  useEffect(() => {
    setHistory([
      {
        ply: 0,
        fen: DEFAULT_CHESS_START_FEN,
        move: null,
        evaluation: null,
        visualCues: null,
      },
    ]);
    setInspectedPly(null);
    previousLatestPlyRef.current = null;
  }, [gameId, roundId]);

  // Frame handler to immediately record all incoming moves into history
  const handleFrame = useCallback((frame: BroadcastFrame) => {
    if (frame.event_type === 'MOVE' && frame.ply != null && frame.fen) {
      setHistory((prev) => {
        const snapshot: MoveSnapshot = {
          ply: frame.ply!,
          fen: frame.fen!,
          move: frame.move ?? null,
          evaluation: frame.evaluation ?? null,
          visualCues: frame.visual_cues || frame.evaluation?.visual_cues || null,
        };

        const existingIdx = prev.findIndex((s) => s.ply === frame.ply);
        if (existingIdx >= 0) {
          const updated = [...prev];
          updated[existingIdx] = {
            ...updated[existingIdx],
            ...snapshot,
            evaluation: snapshot.evaluation ?? updated[existingIdx].evaluation,
            visualCues: snapshot.visualCues ?? updated[existingIdx].visualCues,
          };
          return updated;
        }

        const next = [...prev, snapshot];
        next.sort((a, b) => a.ply - b.ply);
        return next;
      });
    }
  }, []);

  // 1. Audio and Radio Commentary Engine
  const {
    activeSpeaker,
    currentTurn,
    isMuted,
    isSpeaking,
    toggleMute,
    stopAudio,
  } = useAudioNarrator();

  // 2. Primary SSE Broadcast Stream Connection
  const {
    status,
    metadata,
    fen,
    turn,
    currentMove,
    evaluation,
    visualCues,
    transcript,
    latestCommentary,
    terminationReason,
    isGameOver,
  } = useBroadcastStream({
    gameId,
    roundId,
    replayAll,
    tts: enableTts,
    autoConnect: true,
    autoPlayAudio: true,
    onFrame: handleFrame,
  });

  // Automatically snap to live when a new forward move arrives during live play
  useEffect(() => {
    if (!currentMove) return;
    const ply = currentMove.ply;

    if (previousLatestPlyRef.current !== null && ply > previousLatestPlyRef.current) {
      setInspectedPly(null);
    }
    previousLatestPlyRef.current = ply;
  }, [currentMove?.ply]);

  // Update evaluation & arrows for current move when analysis finishes
  useEffect(() => {
    if (!currentMove) return;
    setHistory((prev) => {
      const idx = prev.findIndex((s) => s.ply === currentMove.ply);
      if (idx >= 0) {
        const item = prev[idx];
        if (item.evaluation !== evaluation || item.visualCues !== visualCues) {
          const updated = [...prev];
          updated[idx] = {
            ...item,
            evaluation: evaluation ?? item.evaluation,
            visualCues: visualCues ?? item.visualCues,
          };
          return updated;
        }
      }
      return prev;
    });
  }, [evaluation, visualCues, currentMove?.ply]);

  const latestPly = useMemo(() => {
    let max = currentMove?.ply ?? 0;
    for (const snap of history) {
      if (snap.ply > max) max = snap.ply;
    }
    return max;
  }, [currentMove?.ply, history]);

  const isLive = inspectedPly === null || inspectedPly === latestPly;

  const currentSnapshot = useMemo(() => {
    if (isLive) return null;
    return history.find((s) => s.ply === inspectedPly) || null;
  }, [isLive, inspectedPly, history]);

  const activeFen =
    fen && fen.trim().length > 0
      ? fen
      : history.length > 0
      ? history[history.length - 1].fen
      : DEFAULT_CHESS_START_FEN;

  // Synchronized active displays based on navigation
  const displayedFen = isLive ? activeFen : (currentSnapshot?.fen ?? activeFen);
  const displayedEval = isLive ? evaluation : (currentSnapshot?.evaluation ?? null);
  const displayedVisualCues = isLive ? visualCues : (currentSnapshot?.visualCues ?? null);
  const displayedMove = isLive
    ? (currentMove || (history.length > 1 ? history[history.length - 1].move : null))
    : (currentSnapshot?.move ?? null);
  const displayedPly = isLive ? latestPly : (inspectedPly ?? 0);

  // Derive the actual side whose turn it is to move on the board
  const liveActiveSide = useMemo(() => {
    if (isGameOver) return null;
    return getSideToMoveFromFen(activeFen);
  }, [activeFen, isGameOver]);

  // 3. Live Synchronized Clocks (driven by true side-to-move)
  const {
    whiteClock,
    blackClock,
    isWhiteTimeTrouble,
    isBlackTimeTrouble,
  } = useChessClock({
    initialWhiteSeconds: currentMove?.white_clock_seconds,
    initialBlackSeconds: currentMove?.black_clock_seconds,
    activeTurn: liveActiveSide || turn,
    isGameOver,
  });

  // Active side for the currently viewed position (live or history)
  const currentSideToMove = useMemo(() => {
    if (isLive && isGameOver) return null;
    return getSideToMoveFromFen(displayedFen);
  }, [isLive, isGameOver, displayedFen]);

  const handleToggleTts = () => {
    setEnableTts((prev) => {
      const next = !prev;
      if (!next) {
        stopAudio();
      }
      return next;
    });
  };
  const handleExitStudio = () => {
    stopAudio();
    onExit();
  };

  // Helper to determine if a specific color is currently to move
  const isColorTurn = (color: 'white' | 'black') => currentSideToMove === color;

  const topColor: 'white' | 'black' = boardOrientation === 'white' ? 'black' : 'white';
  const bottomColor: 'white' | 'black' = boardOrientation === 'white' ? 'white' : 'black';

  return (
    <div
      className={`h-screen max-h-screen w-full flex flex-col justify-between overflow-y-auto lg:overflow-hidden select-none transition-colors duration-200 ${
        isDark ? 'bg-[#0b0c0f] text-neutral-100' : 'bg-[#f5f6f9] text-neutral-900'
      }`}
    >
      {/* 1. Header Bar */}
      <header
        className={`shrink-0 border-b transition-colors duration-200 ${
          isDark ? 'border-white/[0.08] bg-[#13151b]' : 'border-neutral-200 bg-white'
        }`}
      >
        <BroadcastHeader
          metadata={metadata}
          status={status}
          isMuted={isMuted}
          onToggleMute={toggleMute}
          enableTts={enableTts}
          onToggleTts={handleToggleTts}
          onExit={handleExitStudio}
          boardOrientation={boardOrientation}
          onFlipBoard={handleFlipBoard}
        />
      </header>

      {/* 2. Main Studio Grid */}
      <main className="flex-1 min-h-0 py-2 px-3 lg:px-6 max-w-7xl w-full mx-auto grid grid-cols-1 lg:grid-cols-12 gap-4 lg:gap-6 items-center">
        {/* Left Column: Chessboard, Clocks, Eval Bar & Move Navigator */}
        <div className="lg:col-span-7 h-full min-h-0 flex flex-col items-center justify-between max-w-[540px] mx-auto w-full py-1">
          {/* Top Player (Black by default) */}
          <div className="w-full shrink-0">
            <PlayerCard
              player={boardOrientation === 'white' ? metadata?.black_player : metadata?.white_player}
              color={topColor}
              clockSeconds={topColor === 'black' ? blackClock : whiteClock}
              isActiveTurn={isColorTurn(topColor)}
              isTimeTrouble={topColor === 'black' ? isBlackTimeTrouble : isWhiteTimeTrouble}
              lastMoveTimeSpent={
                displayedMove?.turn === topColor
                  ? displayedMove.move_time_spent_seconds
                  : null
              }
            />
          </div>

          {/* Board & Eval Bar Row */}
          <div className="flex-1 min-h-0 w-full flex items-center justify-center gap-3 my-1">
            {/* Real-time Advantage Bar */}
            <div className="shrink-0 flex items-center">
              <EvalBar
                scoreCp={displayedEval?.eval_cp_after}
                mateIn={displayedEval?.mate_in_after}
                height={boardHeight}
              />
            </div>

            {/* Interactive SVG Chessboard Container */}
            <div className="h-full aspect-square max-h-[calc(100vh-275px)] max-w-[min(100%,calc(100vh-275px))] flex items-center justify-center">
              <ChessStudioBoard
                fen={displayedFen}
                boardOrientation={boardOrientation}
                visualCues={displayedVisualCues}
                lastMove={displayedMove}
                onHeightChange={setBoardHeight}
              />
            </div>
          </div>

          {/* Move History Navigation Bar */}
          <div className="w-full shrink-0 my-1">
            <MoveNavigator
              currentPly={displayedPly}
              maxPly={latestPly}
              minPly={0}
              isLive={isLive}
              onNavigate={(ply) => setInspectedPly(ply)}
              onGoLive={() => setInspectedPly(null)}
              moveSan={displayedMove?.san}
              turn={displayedMove?.turn}
            />
          </div>

          {/* Bottom Player (White by default) */}
          <div className="w-full shrink-0">
            <PlayerCard
              player={boardOrientation === 'white' ? metadata?.white_player : metadata?.black_player}
              color={bottomColor}
              clockSeconds={bottomColor === 'white' ? whiteClock : blackClock}
              isActiveTurn={isColorTurn(bottomColor)}
              isTimeTrouble={bottomColor === 'white' ? isWhiteTimeTrouble : isBlackTimeTrouble}
              lastMoveTimeSpent={
                displayedMove?.turn === bottomColor
                  ? displayedMove.move_time_spent_seconds
                  : null
              }
            />
          </div>
        </div>

        {/* Right Column: Commentary Desk & Transcript */}
        <div className="lg:col-span-5 h-full max-h-[calc(100vh-140px)] w-full min-h-0 flex flex-col py-1">
          <CommentaryStudio
            latestCommentary={latestCommentary}
            transcript={transcript}
            activeSpeaker={activeSpeaker}
            currentTurn={currentTurn}
            isSpeaking={isSpeaking}
          />
        </div>
      </main>

      {/* 3. Lower-Third Ticker Bar */}
      <footer
        className={`shrink-0 border-t transition-colors duration-200 ${
          isDark ? 'border-white/[0.08] bg-[#13151b]' : 'border-neutral-200 bg-white'
        }`}
      >
        <TickerBar
          evaluation={displayedEval}
          lastMove={displayedMove}
          terminationReason={terminationReason}
          isGameOver={isGameOver}
        />
      </footer>
    </div>
  );
};