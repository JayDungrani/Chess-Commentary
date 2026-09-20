// src/components/board/ChessStudioBoard.tsx

import React, { useState, useEffect, useRef, useMemo } from 'react';
import { Chessboard } from 'react-chessboard';
import type { Square } from 'chess.js';
import type { VisualCue, ParsedMoveEvent } from '../../types/broadcast';

interface ChessStudioBoardProps {
  fen: string;
  boardOrientation?: 'white' | 'black';
  visualCues?: VisualCue | null;
  lastMove?: ParsedMoveEvent | null;
  boardWidth?: number;
  onHeightChange?: (height: number) => void;
}

// Convert backend color names to tournament broadcast RGBA strokes
const ARROW_COLOR_MAP: Record<string, string> = {
  green: 'rgba(34, 197, 94, 0.85)',    // Best engine continuation
  red: 'rgba(239, 68, 68, 0.85)',      // Tactical blunder / threat
  cyan: 'rgba(245, 158, 11, 0.90)',    // Brilliant sacrifice (mapped to tournament gold)
  gold: 'rgba(245, 158, 11, 0.90)',    // Brilliancy / key idea
  blue: 'rgba(96, 165, 250, 0.85)',    // Prospective candidate move
  orange: 'rgba(249, 115, 22, 0.85)',  // Mistake / inaccurate line
  yellow: 'rgba(234, 179, 8, 0.85)',   // Positional alternative
};

export const ChessStudioBoard: React.FC<ChessStudioBoardProps> = ({
  fen,
  boardOrientation = 'white',
  visualCues,
  lastMove,
  boardWidth: propBoardWidth,
  onHeightChange,
}) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const [measuredWidth, setMeasuredWidth] = useState<number>(propBoardWidth || 420);

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
      
      // Preserve 1:1 aspect ratio based on available container bounds
      const dimension = clientHeight > 0 ? Math.min(clientWidth, clientHeight) : clientWidth;
      if (dimension > 50) {
        const rounded = Math.floor(dimension);
        setMeasuredWidth(rounded);
        onHeightChange?.(rounded);
      }
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

    // A. Warm tournament gold highlight on the squares of the move just played
    if (lastMove?.uci && lastMove.uci.length >= 4) {
      const fromSquare = lastMove.uci.slice(0, 2);
      const toSquare = lastMove.uci.slice(2, 4);

      styles[fromSquare] = {
        backgroundColor: 'rgba(245, 158, 11, 0.25)',
      };
      styles[toSquare] = {
        backgroundColor: 'rgba(245, 158, 11, 0.40)',
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
      className="relative w-full h-full max-h-full aspect-square flex items-center justify-center p-2 rounded-2xl bg-[#12151d] border border-stone-800 shadow-2xl"
    >
      <div className="rounded-xl overflow-hidden shadow-inner flex items-center justify-center">
        <Chessboard
          position={fen}
          boardOrientation={boardOrientation}
          boardWidth={measuredWidth}
          arePiecesDraggable={false}
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