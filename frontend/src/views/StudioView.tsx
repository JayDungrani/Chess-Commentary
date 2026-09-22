// src/views/StudioView.tsx

import React, { useState, useEffect, useRef, useMemo, useCallback } from 'react';
import { Chess } from 'chess.js';
import { useBroadcastStream } from '../hooks/useBroadcastStream';
import { useChessClock } from '../hooks/useChessClock';
import { useAudioNarrator } from '../hooks/useAudioNarrator';
import { soundEffects } from '../utils/soundEffects';

import { BroadcastHeader } from '../components/layout/BroadcastHeader';
import { TickerBar } from '../components/layout/TickerBar';
import { ChessStudioBoard } from '../components/board/ChessStudioBoard';
import { EvalBar } from '../components/board/EvalBar';
import { PlayerCard } from '../components/board/PlayerCard';
import { CommentaryStudio } from '../components/commentary/CommentaryStudio';
import { MoveNavigator } from '../components/board/MoveNavigator';
import { EvalTimelineChart } from '../components/board/EvalTimelineChart';
import { useTheme } from '../context/ThemeContext';
import type { MoveEvaluation, ParsedMoveEvent, VisualCue, BroadcastFrame, GameMetadata } from '../types/broadcast';

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

export interface MoveSnapshot {
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
  initialSnapshots?: MoveSnapshot[];
  initialMetadata?: GameMetadata;
  initialMoveDelay?: number;
  onExit: () => void;
}

export const StudioView: React.FC<StudioViewProps> = ({
  gameId,
  roundId,
  initialEnableTts = true,
  replayAll = false,
  initialSnapshots,
  initialMetadata,
  initialMoveDelay = 2,
  onExit,
}) => {
  const { isDark } = useTheme();
  const [enableTts, setEnableTts] = useState(initialEnableTts);
  const [boardOrientation, setBoardOrientation] = useState<'white' | 'black'>('white');
  const [boardHeight, setBoardHeight] = useState<number | undefined>(undefined);
  const handleFlipBoard = () => {
    setBoardOrientation((prev) => (prev === 'white' ? 'black' : 'white'));
  };

  // Detect if this session is a custom PGN / FEN replay or live broadcast
  const isCustomGame = useMemo(
    () => gameId.startsWith('custom_'),
    [gameId]
  );

  const [customMetadata, setCustomMetadata] = useState<GameMetadata | null>(initialMetadata || null);

  // Move history and navigation state - populated instantly if pre-analyzed snapshots are provided
  const [history, setHistory] = useState<MoveSnapshot[]>(() => {
    if (initialSnapshots && initialSnapshots.length > 0) {
      return initialSnapshots;
    }
    return [
      {
        ply: 0,
        fen: DEFAULT_CHESS_START_FEN,
        move: null,
        evaluation: null,
        visualCues: null,
      },
    ];
  });
  const [inspectedPly, setInspectedPly] = useState<number | null>(() => (isCustomGame ? 0 : null));
  const previousLatestPlyRef = useRef<number | null>(null);

  // Playback state for PGN games / replays (starts paused at 2 sec delay)
  const [isPlaying, setIsPlaying] = useState(false);
  const [moveDelay, setMoveDelay] = useState(initialMoveDelay || 2);

  // Sandbox Mode: hypothetical piece dragging and exploration
  const [isSandbox, setIsSandbox] = useState(false);
  const [sandboxFen, setSandboxFen] = useState<string | null>(null);
  const [sandboxEval, setSandboxEval] = useState<MoveEvaluation | null>(null);
  const [sandboxVisualCues, setSandboxVisualCues] = useState<VisualCue | null>(null);
  const [sandboxLastMove, setSandboxLastMove] = useState<ParsedMoveEvent | null>(null);

  // Sync initial metadata and move delay props
  useEffect(() => {
    if (initialMetadata) setCustomMetadata(initialMetadata);
  }, [initialMetadata]);

  useEffect(() => {
    if (initialMoveDelay) setMoveDelay(initialMoveDelay);
  }, [initialMoveDelay]);

  // Initialize start position (ply 0) and reset on match/round change or load full pre-analyzed snapshots
  useEffect(() => {
    if (initialSnapshots && initialSnapshots.length > 0) {
      setHistory(initialSnapshots);
    } else if (isCustomGame) {
      // If opened directly without initialSnapshots, fetch pre-calculated snapshots from backend
      fetch(`/api/custom/game/${encodeURIComponent(gameId)}`)
        .then((res) => (res.ok ? res.json() : null))
        .then((data) => {
          if (data?.snapshots && data.snapshots.length > 0) {
            setHistory(data.snapshots);
            if (data.metadata) {
              setCustomMetadata(data.metadata);
            }
          }
        })
        .catch((err) => console.error('Failed to load custom game analysis:', err));
    } else {
      setHistory([
        {
          ply: 0,
          fen: DEFAULT_CHESS_START_FEN,
          move: null,
          evaluation: null,
          visualCues: null,
        },
      ]);
    }

    setInspectedPly(isCustomGame ? 0 : null);
    setIsSandbox(false);
    setSandboxFen(null);
    setSandboxEval(null);
    setSandboxVisualCues(null);
    setSandboxLastMove(null);
    setIsPlaying(false);
    previousLatestPlyRef.current = null;
  }, [gameId, roundId, isCustomGame, initialSnapshots]);

  // Frame handler to immediately record all incoming moves into history
  const handleFrame = useCallback((frame: BroadcastFrame) => {
    if (frame.event_type === 'METADATA' && frame.fen) {
      setHistory((prev) => {
        if (prev.length > 0 && prev[0].ply === 0) {
          const updated = [...prev];
          updated[0] = { ...updated[0], fen: frame.fen! };
          return updated;
        }
        return prev;
      });
    }

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

  // Automatically snap to live when a new forward move arrives during live play (disabled for custom PGN/FEN)
  useEffect(() => {
    if (!currentMove) return;
    const ply = currentMove.ply;

    if (previousLatestPlyRef.current !== null && ply > previousLatestPlyRef.current) {
      if (!isCustomGame && !isSandbox) {
        setInspectedPly(null);
      }
    }
    previousLatestPlyRef.current = ply;
  }, [currentMove?.ply, isSandbox, isCustomGame]);

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

  const isLive = !isCustomGame && (inspectedPly === null || inspectedPly === latestPly);

  // Auto-advance moves when isPlaying is active in PGN/FEN mode
  useEffect(() => {
    if (!isPlaying) return;
    const interval = setInterval(() => {
      setInspectedPly((current) => {
        const activePly = current ?? 0;
        if (activePly >= latestPly) {
          setIsPlaying(false);
          return latestPly;
        }
        const nextPly = activePly + 1;
        if (nextPly >= latestPly) {
          setIsPlaying(false);
          return latestPly;
        }
        return nextPly;
      });
    }, moveDelay * 1000);
    return () => clearInterval(interval);
  }, [isPlaying, latestPly, moveDelay]);

  const handleExitSandbox = useCallback(() => {
    setIsSandbox(false);
    setSandboxFen(null);
    setSandboxEval(null);
    setSandboxVisualCues(null);
    setSandboxLastMove(null);
  }, []);

  const handleNavigate = useCallback(
    (ply: number) => {
      handleExitSandbox();
      setIsPlaying(false);
      setInspectedPly(ply);
    },
    [handleExitSandbox]
  );

  const handleGoLive = useCallback(() => {
    handleExitSandbox();
    setIsPlaying(false);
    setInspectedPly(null);
  }, [handleExitSandbox]);

  const handleTogglePlay = useCallback(() => {
    handleExitSandbox();
    setIsPlaying((prev) => {
      const next = !prev;
      if (next && inspectedPly !== null && inspectedPly >= latestPly && latestPly > 0) {
        setInspectedPly(0);
      }
      return next;
    });
  }, [handleExitSandbox, inspectedPly, latestPly]);

  const currentSnapshot = useMemo(() => {
    if (isLive) return null;
    const target = inspectedPly ?? (isCustomGame ? 0 : latestPly);
    return history.find((s) => s.ply === target) || null;
  }, [isLive, isCustomGame, inspectedPly, latestPly, history]);

  const activeFen =
    fen && fen.trim().length > 0
      ? fen
      : history.length > 0
      ? history[history.length - 1].fen
      : DEFAULT_CHESS_START_FEN;

  // Synchronized active displays based on navigation & sandbox state
  const baseFen = isLive ? activeFen : (currentSnapshot?.fen ?? activeFen);
  const displayedFen = isSandbox && sandboxFen ? sandboxFen : baseFen;

  const baseEval = isLive ? evaluation : (currentSnapshot?.evaluation ?? null);
  const displayedEval = isSandbox ? sandboxEval : baseEval;

  const baseVisualCues = isLive ? visualCues : (currentSnapshot?.visualCues ?? null);
  const displayedVisualCues = isSandbox ? sandboxVisualCues : baseVisualCues;

  const baseMove = isLive
    ? (currentMove || (history.length > 1 ? history[history.length - 1].move : null))
    : (currentSnapshot?.move ?? null);
  const displayedMove = isSandbox ? sandboxLastMove : baseMove;

  const displayedPly = isSandbox
    ? (sandboxLastMove?.ply ?? (inspectedPly ?? latestPly))
    : (isLive ? latestPly : (inspectedPly ?? 0));

  // Drag & drop piece move handler for hypothetical sandbox analysis
  const handleMovePiece = useCallback(
    (sourceSquare: string, targetSquare: string): boolean => {
      try {
        const currentBoardFen = isSandbox && sandboxFen ? sandboxFen : displayedFen;
        const chess = new Chess(currentBoardFen);

        const moveResult = chess.move({
          from: sourceSquare,
          to: targetSquare,
          promotion: 'q',
        });

        if (!moveResult) return false;

        // Pause auto-playback if active
        setIsPlaying(false);

        const newFen = chess.fen();
        const isCheck = chess.inCheck();
        const isCheckmate = chess.isCheckmate();
        const currentPlyCount = displayedPly ?? 0;

        setIsSandbox(true);
        setSandboxFen(newFen);

        const parsedMove: ParsedMoveEvent = {
          san: moveResult.san,
          uci: `${sourceSquare}${targetSquare}${moveResult.promotion || ''}`,
          turn: moveResult.color === 'w' ? 'white' : 'black',
          ply: currentPlyCount + 1,
          white_clock_seconds: null,
          black_clock_seconds: null,
          move_time_spent_seconds: null,
          is_check: isCheck,
          is_checkmate: isCheckmate,
        };
        setSandboxLastMove(parsedMove);

        // Tactile sound effect for user sandbox move
        if (isCheckmate) {
          soundEffects.playGameOver();
        } else if (isCheck || moveResult.san.includes('+')) {
          soundEffects.playCheck();
        } else if (moveResult.san.startsWith('O-O') || moveResult.san.startsWith('0-0')) {
          soundEffects.playCastle();
        } else if (moveResult.captured) {
          soundEffects.playCapture();
        } else {
          soundEffects.playMove();
        }

        // Live Stockfish engine calculation for user's sandbox move
        fetch(`/api/engine/analyze?fen=${encodeURIComponent(newFen)}&depth=12`)
          .then((res) => (res.ok ? res.json() : null))
          .then((analysisData) => {
            if (!analysisData) return;
            const sideToMove = getSideToMoveFromFen(newFen);
            setSandboxEval({
              ...analysisData,
              ply: currentPlyCount + 1,
              turn: sideToMove,
              played_san: moveResult.san,
              played_uci: `${sourceSquare}${targetSquare}`,
              fen_after: newFen,
              is_book: false,
              left_book_now: false,
              eval_swing_cp: 0,
              is_blunder: false,
            });
            setSandboxVisualCues(analysisData.visual_cues || null);
          })
          .catch((err) => {
            console.debug('Sandbox engine analysis error:', err);
          });

        return true;
      } catch (e) {
        console.debug('Invalid move attempt in sandbox:', e);
        return false;
      }
    },
    [isSandbox, sandboxFen, displayedFen, displayedPly]
  );

  // On-demand engine analysis for historical plies without cached evaluations
  const requestedFensRef = useRef<Set<string>>(new Set());
  useEffect(() => {
    if (isLive || isSandbox || !displayedFen || displayedEval) return;
    if (requestedFensRef.current.has(displayedFen)) return;

    requestedFensRef.current.add(displayedFen);
    const targetPly = inspectedPly;

    fetch(`/api/engine/analyze?fen=${encodeURIComponent(displayedFen)}&depth=12`)
      .then((res) => (res.ok ? res.json() : null))
      .then((analysisData) => {
        if (!analysisData) return;
        setHistory((prev) => {
          const idx = prev.findIndex((s) => s.ply === targetPly);
          if (idx >= 0) {
            const updated = [...prev];
            const currentItem = updated[idx];
            const sideToMove = getSideToMoveFromFen(displayedFen);
            updated[idx] = {
              ...currentItem,
              evaluation: {
                ...analysisData,
                ply: targetPly ?? 0,
                turn: sideToMove,
                played_san: currentItem.move?.san || '',
                played_uci: currentItem.move?.uci || '',
                fen_after: displayedFen,
                is_book: false,
                left_book_now: false,
                eval_swing_cp: 0,
                is_blunder: false,
              },
              visualCues: analysisData.visual_cues || null,
            };
            return updated;
          }
          return prev;
        });
      })
      .catch((err) => {
        console.debug('On-demand analysis note:', err);
      });
  }, [isLive, isSandbox, displayedFen, displayedEval, inspectedPly]);

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

  const effectiveMetadata = metadata || customMetadata || initialMetadata || null;

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
          metadata={effectiveMetadata}
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
      <main className="flex-1 min-h-0 py-2 px-3 lg:px-6 max-w-screen-2xl w-full mx-auto grid grid-cols-1 lg:grid-cols-12 gap-4 lg:gap-6 items-center">
        {/* Left Column: Dedicated Large Chessboard & Player Clocks */}
        <div className="lg:col-span-7 h-full min-h-0 flex flex-col items-center justify-between w-full py-1">
          {/* Top Player (Black by default) */}
          <div className="w-full max-w-[min(100%,calc(100vh-185px))] shrink-0">
            <PlayerCard
              player={boardOrientation === 'white' ? effectiveMetadata?.black_player : effectiveMetadata?.white_player}
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
          <div className="flex-1 min-h-0 w-full flex items-center justify-center gap-3 my-1.5">
            {/* Real-time Advantage Bar */}
            <div className="shrink-0 flex items-center">
              <EvalBar
                scoreCp={displayedEval?.eval_cp_after}
                mateIn={displayedEval?.mate_in_after}
                height={boardHeight}
              />
            </div>

            {/* Interactive SVG Chessboard Container - Expanded to Maximize Viewport Area */}
            <div className="h-full aspect-square max-h-[calc(100vh-190px)] max-w-[min(100%,calc(100vh-190px))] flex items-center justify-center">
              <ChessStudioBoard
                fen={displayedFen}
                boardOrientation={boardOrientation}
                visualCues={displayedVisualCues}
                lastMove={displayedMove}
                onHeightChange={setBoardHeight}
                isMuted={isMuted}
                isGameOver={isGameOver}
                onMovePiece={handleMovePiece}
              />
            </div>
          </div>

          {/* Bottom Player (White by default) */}
          <div className="w-full max-w-[min(100%,calc(100vh-185px))] shrink-0">
            <PlayerCard
              player={boardOrientation === 'white' ? effectiveMetadata?.white_player : effectiveMetadata?.black_player}
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

        {/* Right Column: Analysis Hub & Commentary Desk */}
        <div className="lg:col-span-5 h-full max-h-[calc(100vh-130px)] w-full min-h-0 flex flex-col justify-between py-1 gap-2.5">
          {/* 1. Move History Navigation Bar */}
          <div className="w-full shrink-0">
            <MoveNavigator
              currentPly={displayedPly}
              maxPly={latestPly}
              minPly={0}
              isLive={isLive && !isSandbox}
              onNavigate={handleNavigate}
              onGoLive={handleGoLive}
              moveSan={displayedMove?.san}
              turn={displayedMove?.turn}
              isPlaying={isPlaying}
              onTogglePlay={handleTogglePlay}
              moveDelay={moveDelay}
              onChangeMoveDelay={setMoveDelay}
              isSandbox={isSandbox}
              onExitSandbox={handleExitSandbox}
              isPgnMode={isCustomGame}
            />
          </div>

          {/* 2. Interactive Eval Timeline Chart */}
          <div className="w-full shrink-0">
            <EvalTimelineChart
              history={history}
              currentPly={displayedPly}
              onSelectPly={handleNavigate}
            />
          </div>

          {/* 3. Commentary Desk & Live Transcript */}
          <div className="flex-1 min-h-0 w-full flex flex-col overflow-hidden">
            <CommentaryStudio
              latestCommentary={latestCommentary}
              transcript={transcript}
              activeSpeaker={activeSpeaker}
              currentTurn={currentTurn}
              isSpeaking={isSpeaking}
            />
          </div>
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
          isGameOver={isLive && isGameOver}
        />
      </footer>
    </div>
  );
};