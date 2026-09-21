// src/components/common/GhostMasterpieceBackground.tsx

import React, { useEffect, useRef } from 'react';
import { Chess } from 'chess.js';
import { useTheme } from '../../context/ThemeContext';

// Paul Morphy's Opera Game (1858) - Paris Opera House
const OPERA_PGN = `
1. e4 e5 2. Nf3 d6 3. d4 Bg4 4. dxe5 Bxf3 5. Qxf3 dxe5 6. Bc4 Nf6
7. Qb3 Qe7 8. Nc3 c6 9. Bg5 b5 10. Nxb5 cxb5 11. Bxb5+ Nbd7
12. O-O-O Rd8 13. Rxd7 Rxd7 14. Rd1 Qe6 15. Bxd7+ Nxd7 16. Qb8+ Nxb8 17. Rd8#
`;

export const GhostMasterpieceBackground: React.FC = () => {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const { isDark } = useTheme();
  const isDarkRef = useRef(isDark);
  isDarkRef.current = isDark;

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    let animationFrameId: number;

    // Parse PGN moves
    const game = new Chess();
    game.loadPgn(OPERA_PGN);
    const history = game.history({ verbose: true });

    // Game playback state
    let moveIndex = 0;
    let currentBoard = new Chess();
    let moveProgress = 1.0; // 0..1 interpolation during move animation
    let lastMoveTime = performance.now();
    const MOVE_DURATION = 900; // ms for piece slide
    const PAUSE_BETWEEN_MOVES = 1400; // ms between moves
    const END_PAUSE = 4500; // ms pause on checkmate

    let activeMovingPiece: {
      fromCol: number;
      fromRow: number;
      toCol: number;
      toRow: number;
      pieceType: string;
      pieceColor: 'w' | 'b';
    } | null = null;

    let currentSan = '1858 // MORPHY OPERA GAME';

    // 3D Perspective settings
    const tiltX = 0.96; // ~55 degree backward tilt for dramatic board perspective
    const cosTilt = Math.cos(tiltX);
    const sinTilt = Math.sin(tiltX);
    let rotationY = 0.08; // subtle angle for isometric depth

    const resizeCanvas = () => {
      const dpr = window.devicePixelRatio || 1;
      canvas.width = window.innerWidth * dpr;
      canvas.height = window.innerHeight * dpr;
      canvas.style.width = `${window.innerWidth}px`;
      canvas.style.height = `${window.innerHeight}px`;
      ctx.scale(dpr, dpr);
    };

    resizeCanvas();
    window.addEventListener('resize', resizeCanvas);

    // Project 3D board coordinates (x: -4..4, y: altitude, z: -4..4) to 2D screen
    const project = (
      x3: number,
      y3: number,
      z3: number,
      centerX: number,
      centerY: number,
      baseScale: number
    ) => {
      const cosY = Math.cos(rotationY);
      const sinY = Math.sin(rotationY);

      // Rotate Y
      const x1 = x3 * cosY + z3 * sinY;
      const y1 = y3;
      const z1 = -x3 * sinY + z3 * cosY;

      // Tilt X
      const x2 = x1;
      const y2 = y1 * cosTilt - z1 * sinTilt;
      const z2 = y1 * sinTilt + z1 * cosTilt;

      const camDist = 9.5;
      const fov = camDist / (camDist + z2);

      return {
        x: centerX + x2 * fov * baseScale,
        y: centerY - y2 * fov * baseScale,
        scale: fov,
        z: z2,
      };
    };

    const render = (now: number) => {
      const width = window.innerWidth;
      const height = window.innerHeight;
      const dark = isDarkRef.current;

      ctx.clearRect(0, 0, width, height);

      // Step Move Logic
      const elapsedSinceMove = now - lastMoveTime;

      if (moveIndex < history.length) {
        if (elapsedSinceMove < MOVE_DURATION) {
          // In motion
          moveProgress = Math.min(1.0, elapsedSinceMove / MOVE_DURATION);
        } else if (elapsedSinceMove >= MOVE_DURATION && activeMovingPiece) {
          // Commit move
          currentBoard.move(history[moveIndex]);
          activeMovingPiece = null;
          moveIndex++;
          lastMoveTime = now;
        } else if (elapsedSinceMove >= PAUSE_BETWEEN_MOVES && !activeMovingPiece) {
          // Start next move
          const nextMove = history[moveIndex];
          const fromSquare = nextMove.from;
          const toSquare = nextMove.to;

          const fromCol = fromSquare.charCodeAt(0) - 97; // a=0..h=7
          const fromRow = parseInt(fromSquare[1], 10) - 1; // 1=0..8=7
          const toCol = toSquare.charCodeAt(0) - 97;
          const toRow = parseInt(toSquare[1], 10) - 1;

          activeMovingPiece = {
            fromCol,
            fromRow,
            toCol,
            toRow,
            pieceType: nextMove.piece,
            pieceColor: nextMove.color,
          };
          currentSan = `${nextMove.san}`;
          moveProgress = 0.0;
          lastMoveTime = now;
        }
      } else {
        // Game finished - wait and reset
        if (elapsedSinceMove > END_PAUSE) {
          currentBoard = new Chess();
          moveIndex = 0;
          activeMovingPiece = null;
          lastMoveTime = now;
          currentSan = '1858 // MORPHY OPERA GAME';
        }
      }

      // Smooth camera sway (gentle breathing)
      rotationY = 0.08 + Math.sin(now * 0.0003) * 0.04;

      const centerX = width * 0.5;
      const centerY = height * 0.52;
      const baseScale = Math.min(width, height) * 0.16;

      // Color tokens
      const strokeColor = dark
        ? 'rgba(225, 230, 240, 0.12)'
        : 'rgba(20, 25, 35, 0.11)';
      const tileLightColor = dark
        ? 'rgba(255, 255, 255, 0.02)'
        : 'rgba(0, 0, 0, 0.025)';
      const activeSquareColor = dark
        ? 'rgba(224, 83, 56, 0.15)'
        : 'rgba(224, 83, 56, 0.12)';

      // 1. Draw 3D Chessboard Grid & Squares
      for (let r = 0; r < 8; r++) {
        for (let c = 0; c < 8; c++) {
          const x0 = c - 4;
          const z0 = r - 4;

          const p1 = project(x0, 0, z0, centerX, centerY, baseScale);
          const p2 = project(x0 + 1, 0, z0, centerX, centerY, baseScale);
          const p3 = project(x0 + 1, 0, z0 + 1, centerX, centerY, baseScale);
          const p4 = project(x0, 0, z0 + 1, centerX, centerY, baseScale);

          // Alternating square tint
          const isLight = (r + c) % 2 === 1;
          const isSource = activeMovingPiece && activeMovingPiece.fromCol === c && activeMovingPiece.fromRow === r;
          const isTarget = activeMovingPiece && activeMovingPiece.toCol === c && activeMovingPiece.toRow === r;

          ctx.beginPath();
          ctx.moveTo(p1.x, p1.y);
          ctx.lineTo(p2.x, p2.y);
          ctx.lineTo(p3.x, p3.y);
          ctx.lineTo(p4.x, p4.y);
          ctx.closePath();

          if (isSource || isTarget) {
            ctx.fillStyle = activeSquareColor;
            ctx.fill();
          } else if (isLight) {
            ctx.fillStyle = tileLightColor;
            ctx.fill();
          }

          ctx.strokeStyle = strokeColor;
          ctx.lineWidth = 0.7;
          ctx.stroke();
        }
      }

      // Outer board border
      const b1 = project(-4.1, 0, -4.1, centerX, centerY, baseScale);
      const b2 = project(4.1, 0, -4.1, centerX, centerY, baseScale);
      const b3 = project(4.1, 0, 4.1, centerX, centerY, baseScale);
      const b4 = project(-4.1, 0, 4.1, centerX, centerY, baseScale);

      ctx.beginPath();
      ctx.moveTo(b1.x, b1.y);
      ctx.lineTo(b2.x, b2.y);
      ctx.lineTo(b3.x, b3.y);
      ctx.lineTo(b4.x, b4.y);
      ctx.closePath();
      ctx.strokeStyle = dark ? 'rgba(255, 255, 255, 0.16)' : 'rgba(0, 0, 0, 0.16)';
      ctx.lineWidth = 1.2;
      ctx.stroke();

      // 2. Draw Standing Pieces on Board
      const boardState = currentBoard.board();

      // We render back-to-front (r=7 down to 0) for correct depth layering
      for (let r = 7; r >= 0; r--) {
        for (let c = 0; c < 8; c++) {
          // If this square is currently being moved from, skip it (drawn in motion phase)
          if (activeMovingPiece && activeMovingPiece.fromCol === c && activeMovingPiece.fromRow === r) {
            continue;
          }

          const squarePiece = boardState[7 - r][c];
          if (!squarePiece) continue;

          drawPiece(
            c,
            r,
            0,
            squarePiece.type,
            squarePiece.color,
            dark,
            centerX,
            centerY,
            baseScale
          );
        }
      }

      // 3. Draw Currently Moving Piece in Flight (with arc height)
      if (activeMovingPiece) {
        // Smooth easing: easeInOutCubic
        const t = moveProgress < 0.5
          ? 4 * moveProgress * moveProgress * moveProgress
          : 1 - Math.pow(-2 * moveProgress + 2, 3) / 2;

        const curCol = activeMovingPiece.fromCol + (activeMovingPiece.toCol - activeMovingPiece.fromCol) * t;
        const curRow = activeMovingPiece.fromRow + (activeMovingPiece.toRow - activeMovingPiece.fromRow) * t;

        // Lift piece into air in an arc
        const arcHeight = Math.sin(moveProgress * Math.PI) * 0.9;

        // Faint trajectory path
        const pStart = project(
          activeMovingPiece.fromCol + 0.5 - 4,
          0,
          activeMovingPiece.fromRow + 0.5 - 4,
          centerX,
          centerY,
          baseScale
        );
        const pMid = project(
          curCol + 0.5 - 4,
          arcHeight * 0.6,
          curRow + 0.5 - 4,
          centerX,
          centerY,
          baseScale
        );
        const pEnd = project(
          activeMovingPiece.toCol + 0.5 - 4,
          0,
          activeMovingPiece.toRow + 0.5 - 4,
          centerX,
          centerY,
          baseScale
        );

        ctx.beginPath();
        ctx.moveTo(pStart.x, pStart.y);
        ctx.quadraticCurveTo(pMid.x, pMid.y, pEnd.x, pEnd.y);
        ctx.strokeStyle = dark ? 'rgba(224, 83, 56, 0.35)' : 'rgba(224, 83, 56, 0.4)';
        ctx.lineWidth = 1.0;
        ctx.stroke();

        // Moving piece itself
        drawPiece(
          curCol,
          curRow,
          arcHeight,
          activeMovingPiece.pieceType,
          activeMovingPiece.pieceColor,
          dark,
          centerX,
          centerY,
          baseScale
        );
      }

      // 4. Subtle Telemetry Subtitle at bottom of canvas
      ctx.font = '10px monospace';
      ctx.textAlign = 'center';
      ctx.fillStyle = dark ? 'rgba(225, 230, 240, 0.35)' : 'rgba(20, 25, 35, 0.4)';
      ctx.fillText(
        `HISTORIC TELEMETRY: ${currentSan.toUpperCase()} • PLY ${moveIndex}/${history.length}`,
        centerX,
        height * 0.92
      );

      animationFrameId = requestAnimationFrame(render);
    };

    // Helper: Draw Minimalist Architectural Piece Token
    function drawPiece(
      col: number,
      row: number,
      altitude: number,
      type: string,
      color: 'w' | 'b',
      dark: boolean,
      centerX: number,
      centerY: number,
      baseScale: number
    ) {
      const x = col + 0.5 - 4;
      const z = row + 0.5 - 4;
      const isWhite = color === 'w';

      // Height of piece token based on rank
      const heightMap: Record<string, number> = {
        p: 0.35,
        n: 0.50,
        b: 0.55,
        r: 0.50,
        q: 0.72,
        k: 0.80,
      };
      const tokenHeight = heightMap[type] || 0.4;
      const radius = type === 'p' ? 0.22 : 0.28;

      // Base point on ground
      const pBase = project(x, altitude, z, centerX, centerY, baseScale);
      // Top point
      const pTop = project(x, altitude + tokenHeight, z, centerX, centerY, baseScale);

      const rScreen = radius * pBase.scale * baseScale;

      // Draw subtle shadow ellipse under piece
      ctx.beginPath();
      ctx.ellipse(pBase.x, pBase.y, rScreen, rScreen * 0.45, 0, 0, Math.PI * 2);
      ctx.fillStyle = dark ? 'rgba(0, 0, 0, 0.35)' : 'rgba(0, 0, 0, 0.08)';
      ctx.fill();

      // Cylinder stem connecting base to top
      ctx.beginPath();
      ctx.moveTo(pBase.x - rScreen, pBase.y);
      ctx.lineTo(pTop.x - rScreen * 0.85, pTop.y);
      ctx.lineTo(pTop.x + rScreen * 0.85, pTop.y);
      ctx.lineTo(pBase.x + rScreen, pBase.y);
      ctx.closePath();

      if (isWhite) {
        ctx.fillStyle = dark ? 'rgba(225, 230, 240, 0.14)' : 'rgba(255, 255, 255, 0.85)';
        ctx.strokeStyle = dark ? 'rgba(225, 230, 240, 0.45)' : 'rgba(20, 25, 35, 0.55)';
      } else {
        ctx.fillStyle = dark ? 'rgba(15, 18, 25, 0.5)' : 'rgba(50, 55, 68, 0.2)';
        ctx.strokeStyle = dark ? 'rgba(160, 170, 190, 0.3)' : 'rgba(20, 25, 35, 0.35)';
      }
      ctx.lineWidth = 0.85;
      ctx.fill();
      ctx.stroke();

      // Top cap disk
      ctx.beginPath();
      ctx.ellipse(pTop.x, pTop.y, rScreen * 0.85, rScreen * 0.38, 0, 0, Math.PI * 2);
      ctx.fillStyle = isWhite
        ? dark
          ? 'rgba(240, 245, 255, 0.3)'
          : 'rgba(255, 255, 255, 0.95)'
        : dark
        ? 'rgba(20, 24, 32, 0.85)'
        : 'rgba(70, 75, 90, 0.5)';
      ctx.fill();
      ctx.stroke();

      // Stylized Monospace Piece Symbol on Top Cap
      ctx.font = `${Math.max(8, Math.round(9 * pTop.scale))}px monospace`;
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      ctx.fillStyle = isWhite
        ? dark
          ? 'rgba(255, 255, 255, 0.9)'
          : 'rgba(10, 12, 18, 0.9)'
        : dark
        ? 'rgba(200, 205, 220, 0.8)'
        : 'rgba(255, 255, 255, 0.95)';

      const label = type.toUpperCase();
      ctx.fillText(label, pTop.x, pTop.y - 0.5);
    }

    animationFrameId = requestAnimationFrame(render);

    return () => {
      window.removeEventListener('resize', resizeCanvas);
      cancelAnimationFrame(animationFrameId);
    };
  }, []);

  return (
    <div className="absolute inset-0 pointer-events-none overflow-hidden select-none z-0">
      <canvas ref={canvasRef} className="w-full h-full block" />
      <div className="absolute inset-0 bg-radial from-transparent via-[#f5f6f9]/30 to-[#f5f6f9]/90 dark:via-[#0b0c0f]/40 dark:to-[#0b0c0f]/95 pointer-events-none" />
    </div>
  );
};
