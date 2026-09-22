import React, { useState, useEffect, useRef, useMemo } from 'react';
import { Chessboard } from 'react-chessboard';
import type { Square } from 'chess.js';
import type { VisualCue, ParsedMoveEvent } from '../../types/broadcast';
import { useTheme } from '../../context/ThemeContext';
import { soundEffects } from '../../utils/soundEffects';

interface ChessStudioBoardProps {
  fen: string;
  boardOrientation?: 'white' | 'black';
  visualCues?: VisualCue | null;
  lastMove?: ParsedMoveEvent | null;
  boardWidth?: number;
  onHeightChange?: (height: number) => void;
  isMuted?: boolean;
  isGameOver?: boolean;
  onMovePiece?: (sourceSquare: string, targetSquare: string) => boolean;
}

// Convert backend color names to tournament broadcast RGBA strokes
const ARROW_COLOR_MAP: Record<string, string> = {
  green: 'rgba(34, 197, 94, 0.85)',    // Best engine continuation
  red: 'rgba(239, 68, 68, 0.85)',      // Tactical blunder / threat
  cyan: 'rgba(224, 83, 56, 0.90)',     // Brilliant sacrifice (mapped to signal orange)
  gold: 'rgba(224, 83, 56, 0.90)',     // Brilliancy / key idea
  blue: 'rgba(96, 165, 250, 0.85)',    // Prospective candidate move
  orange: 'rgba(224, 83, 56, 0.85)',   // Mistake / inaccurate line
  yellow: 'rgba(234, 179, 8, 0.85)',   // Positional alternative
};

export const ChessStudioBoard: React.FC<ChessStudioBoardProps> = ({
  fen,
  boardOrientation = 'white',
  visualCues,
  lastMove,
  boardWidth: propBoardWidth,
  onHeightChange,
  isMuted = false,
  isGameOver = false,
  onMovePiece,
}) => {
  const { isDark } = useTheme();
  const containerRef = useRef<HTMLDivElement>(null);
  const [measuredWidth, setMeasuredWidth] = useState<number>(propBoardWidth || 420);
  const prevMovePlyRef = useRef<number | null>(null);

  // Sync mute state with sound synthesizer
  useEffect(() => {
    soundEffects.setMuted(isMuted);
  }, [isMuted]);

  // Synthesize tactile wooden sound effects on move transitions
  useEffect(() => {
    if (!lastMove || lastMove.ply == null) return;
    if (prevMovePlyRef.current === lastMove.ply) return;
    prevMovePlyRef.current = lastMove.ply;

    const san = lastMove.san || '';
    if (lastMove.is_checkmate || (isGameOver && lastMove.is_check)) {
      soundEffects.playGameOver();
    } else if (lastMove.is_check || san.includes('+')) {
      soundEffects.playCheck();
    } else if (san.startsWith('O-O') || san.startsWith('0-0')) {
      soundEffects.playCastle();
    } else if (san.includes('x')) {
      soundEffects.playCapture();
    } else {
      soundEffects.playMove();
    }
  }, [lastMove, isGameOver]);

  // Measure parent container and notify parent of height changes
  useEffect(() => {
    if (propBoardWidth) {
      setMeasuredWidth(propBoardWidth);
      onHeightChange?.(propBoardWidth);
      return;
    }

    const updateSize = () => {
      if (!containerRef.current) return;
      const { clientWidth, clientHeight } = containerRef.current;
      
      // Preserve 1:1 aspect ratio based on available container bounds minus 16px padding (p-2 = 8px each side)
      const rawDimension = clientHeight > 0 ? Math.min(clientWidth, clientHeight) : clientWidth;
      const dimension = Math.max(50, Math.floor(rawDimension - 16));
      setMeasuredWidth(dimension);
      onHeightChange?.(dimension);
    };

    updateSize();

    const resizeObserver = new ResizeObserver(updateSize);
    if (containerRef.current) {
      resizeObserver.observe(containerRef.current);
    }

    return () => resizeObserver.disconnect();
  }, [propBoardWidth, onHeightChange]);

  // 1. Transform VisualCue arrows into react-chessboard format
  const customArrows = useMemo(() => {
    if (!visualCues?.arrows || visualCues.arrows.length === 0) {
      return [];
    }

    return visualCues.arrows
      .map(([from, to, color]) => {
        if (!from || !to || from.length !== 2 || to.length !== 2) return null;
        const strokeColor = ARROW_COLOR_MAP[color.toLowerCase()] || 'rgba(245, 158, 11, 0.85)';
        return [from as Square, to as Square, strokeColor] as [Square, Square, string];
      })
      .filter((arrow): arrow is [Square, Square, string] => arrow !== null);
  }, [visualCues]);

  // 2. Custom square highlights (Last move from/to + engine key squares)
  const customSquareStyles = useMemo(() => {
    const styles: Record<string, React.CSSProperties> = {};

    // A. Signal orange highlight on the squares of the move just played
    if (lastMove?.uci && lastMove.uci.length >= 4) {
      const fromSquare = lastMove.uci.slice(0, 2);
      const toSquare = lastMove.uci.slice(2, 4);

      styles[fromSquare] = {
        backgroundColor: 'rgba(224, 83, 56, 0.22)',
      };
      styles[toSquare] = {
        backgroundColor: 'rgba(224, 83, 56, 0.38)',
      };
    }

    // B. Target highlights emitted by the engine for critical threat squares
    if (visualCues?.highlights) {
      for (const sq of visualCues.highlights) {
        styles[sq] = {
          backgroundColor: 'rgba(239, 68, 68, 0.35)',
          boxShadow: 'inset 0 0 10px rgba(239, 68, 68, 0.7)',
        };
      }
    }

    return styles;
  }, [lastMove, visualCues]);

  return (
    <div
      ref={containerRef}
      className={`relative w-full h-full max-h-full aspect-square flex items-center justify-center p-2 rounded-2xl border transition-colors duration-200 ${
        isDark
          ? 'bg-[#13151b] border-white/[0.08] shadow-2xl shadow-black/60'
          : 'bg-white border-black/[0.08] shadow-xl shadow-neutral-300/40'
      }`}
    >
      <div className="rounded-xl overflow-hidden shadow-inner flex items-center justify-center">
        <Chessboard
          position={fen}
          boardOrientation={boardOrientation}
          boardWidth={measuredWidth}
          arePiecesDraggable={true}
          onPieceDrop={(sourceSquare, targetSquare) => {
            if (onMovePiece) {
              return onMovePiece(sourceSquare, targetSquare);
            }
            return false;
          }}
          animationDuration={260}
          customArrows={customArrows}
          customSquareStyles={customSquareStyles}
          customDarkSquareStyle={{ backgroundColor: '#7a6652' }}
          customLightSquareStyle={{ backgroundColor: '#e2d7c0' }}
          customBoardStyle={{
            borderRadius: '0.75rem',
          }}
        />
      </div>
    </div>
  );
};