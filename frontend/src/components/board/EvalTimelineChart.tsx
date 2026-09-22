// frontend/src/components/board/EvalTimelineChart.tsx

import React, { useMemo, useState, useRef, useEffect } from 'react';
import type { MoveEvaluation, ParsedMoveEvent, VisualCue } from '../../types/broadcast';
import { useTheme } from '../../context/ThemeContext';
import { formatEval } from '../../utils/formatters';

export interface MoveSnapshot {
  ply: number;
  fen: string;
  move: ParsedMoveEvent | null;
  evaluation: MoveEvaluation | null;
  visualCues: VisualCue | null;
}

interface EvalTimelineChartProps {
  history: MoveSnapshot[];
  currentPly: number;
  onSelectPly: (ply: number) => void;
  height?: number;
}

export const EvalTimelineChart: React.FC<EvalTimelineChartProps> = ({
  history,
  currentPly,
  onSelectPly,
  height = 40,
}) => {
  const { isDark } = useTheme();
  const [hoveredIndex, setHoveredIndex] = useState<number | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [containerWidth, setContainerWidth] = useState<number>(480);

  // Dynamically measure container width to prevent any non-uniform SVG stretching
  useEffect(() => {
    if (!containerRef.current) return;
    const updateWidth = () => {
      if (containerRef.current) {
        const w = containerRef.current.clientWidth;
        if (w > 0) {
          setContainerWidth(Math.max(100, w - 24)); // subtract padding
        }
      }
    };
    updateWidth();
    const observer = new ResizeObserver(updateWidth);
    observer.observe(containerRef.current);
    return () => observer.disconnect();
  }, []);

  // Normalize history plies with evaluations
  const timelinePoints = useMemo(() => {
    if (!history || history.length === 0) return [];

    return history.map((snap) => {
      let cp = snap.evaluation?.eval_cp_after;
      const mate = snap.evaluation?.mate_in_after;

      if (mate !== undefined && mate !== null) {
        cp = mate > 0 ? 1000 : -1000;
      } else if (cp === undefined || cp === null) {
        // Fallback: neutral or carry previous eval
        cp = 0;
      }

      // Clamp centipawns to [-600, 600] for visual aesthetics
      const clampedCp = Math.max(-600, Math.min(600, cp));
      // Normalized advantage: -1.0 (black win) to +1.0 (white win)
      const norm = clampedCp / 600.0;

      return {
        ply: snap.ply,
        san: snap.move?.san || (snap.ply % 2 === 1 ? '1. ?' : '1... ?'),
        turn: snap.move?.turn || (snap.ply % 2 === 1 ? 'white' : 'black'),
        scoreCp: snap.evaluation?.eval_cp_after ?? null,
        mateIn: snap.evaluation?.mate_in_after ?? null,
        classification: snap.evaluation?.classification || null,
        norm,
        hasEval: snap.evaluation !== null,
      };
    });
  }, [history]);

  if (timelinePoints.length < 2) {
    return null;
  }

  const svgWidth = containerWidth;
  const svgHeight = height;
  const zeroY = svgHeight / 2;

  // Build SVG path coordinates with true 1:1 pixel metrics
  const points = timelinePoints.map((pt, idx) => {
    const x = (idx / Math.max(1, timelinePoints.length - 1)) * svgWidth;
    // norm +1.0 is White advantage (top), -1.0 is Black advantage (bottom)
    const y = zeroY - pt.norm * (zeroY - 4);
    return { ...pt, x, y };
  });

  // Polyline points string
  const linePointsStr = points.map((p) => `${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(' ');

  // White advantage area (top filled down to zeroY)
  const whiteAreaStr = `${points[0].x.toFixed(1)},${zeroY} ` +
    points.map((p) => `${p.x.toFixed(1)},${Math.min(p.y, zeroY).toFixed(1)}`).join(' ') +
    ` ${points[points.length - 1].x.toFixed(1)},${zeroY}`;

  // Black advantage area (bottom filled up to zeroY)
  const blackAreaStr = `${points[0].x.toFixed(1)},${zeroY} ` +
    points.map((p) => `${p.x.toFixed(1)},${Math.max(p.y, zeroY).toFixed(1)}`).join(' ') +
    ` ${points[points.length - 1].x.toFixed(1)},${zeroY}`;

  // Current active ply needle X position
  const activePoint = points.find((p) => p.ply === currentPly) || points[points.length - 1];
  const activeX = activePoint?.x ?? points[points.length - 1].x;

  const hoveredPoint = hoveredIndex !== null && hoveredIndex >= 0 && hoveredIndex < points.length ? points[hoveredIndex] : null;

  return (
    <div
      ref={containerRef}
      className={`w-full select-none rounded-xl border px-3 py-1 transition-colors relative overflow-hidden font-mono ${
        isDark ? 'bg-[#13151b] border-white/[0.08]' : 'bg-white border-neutral-200'
      }`}
    >
      {/* Header Info */}
      <div className="flex items-center justify-between text-[10px] uppercase tracking-wider mb-0.5">
        <div className="flex items-center gap-1.5">
          <span className="w-1.5 h-1.5 rounded-full bg-[#e05338]" />
          <span className={isDark ? 'text-neutral-400 font-semibold' : 'text-neutral-600 font-semibold'}>
            EVAL TIMELINE
          </span>
        </div>
        <div className="flex items-center gap-2">
          {hoveredPoint ? (
            <span className="text-xs font-bold text-[#e05338]">
              {hoveredPoint.san} ({formatEval(hoveredPoint.scoreCp, hoveredPoint.mateIn)})
            </span>
          ) : (
            <span className={isDark ? 'text-neutral-500' : 'text-neutral-400'}>
              CLICK TO JUMP
            </span>
          )}
        </div>
      </div>

      {/* SVG Canvas */}
      <div
        className="w-full relative cursor-pointer"
        style={{ height: `${svgHeight}px` }}
        onMouseLeave={() => setHoveredIndex(null)}
      >
        <svg
          viewBox={`0 0 ${svgWidth} ${svgHeight}`}
          className="w-full h-full overflow-visible"
        >
          <defs>
            {/* White advantage subtle glow */}
            <linearGradient id="whiteAdvGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#f5f6f9" stopOpacity="0.25" />
              <stop offset="100%" stopColor="#f5f6f9" stopOpacity="0.0" />
            </linearGradient>
            {/* Black advantage subtle glow */}
            <linearGradient id="blackAdvGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#1a1d26" stopOpacity="0.0" />
              <stop offset="100%" stopColor="#0b0c0f" stopOpacity="0.35" />
            </linearGradient>
          </defs>

          {/* Zero baseline */}
          <line
            x1="0"
            y1={zeroY}
            x2={svgWidth}
            y2={zeroY}
            stroke={isDark ? 'rgba(255,255,255,0.1)' : 'rgba(0,0,0,0.1)'}
            strokeWidth="1"
            strokeDasharray="2 2"
          />

          {/* Advantage Area Fills */}
          <polygon points={whiteAreaStr} fill="url(#whiteAdvGrad)" />
          <polygon points={blackAreaStr} fill="url(#blackAdvGrad)" />

          {/* Advantage Contour Stroke */}
          <polyline
            points={linePointsStr}
            fill="none"
            stroke={isDark ? '#e05338' : '#e05338'}
            strokeWidth="1.8"
            strokeLinecap="round"
            strokeLinejoin="round"
          />

          {/* Critical Tactical Turning Points */}
          {points.map((p, idx) => {
            const isBlunder = p.classification === 'BLUNDER';
            const isBrilliant = p.classification === 'BRILLIANT';
            const isMistake = p.classification === 'MISTAKE';

            if (!isBlunder && !isBrilliant && !isMistake) return null;

            return (
              <circle
                key={idx}
                cx={p.x}
                cy={p.y}
                r={isBrilliant ? 3.5 : isBlunder ? 3.2 : 2.5}
                fill={isBrilliant ? '#e05338' : isBlunder ? '#ef4444' : '#f97316'}
                stroke={isDark ? '#0b0c0f' : '#ffffff'}
                strokeWidth="1.2"
                className="animate-pulse"
              />
            );
          })}

          {/* Active Ply Needle Indicator */}
          <line
            x1={activeX}
            y1={2}
            x2={activeX}
            y2={svgHeight - 2}
            stroke="#e05338"
            strokeWidth="1.5"
            strokeDasharray="1 1"
          />
          <circle
            cx={activeX}
            cy={activePoint.y}
            r="3"
            fill="#e05338"
            stroke={isDark ? '#13151b' : '#ffffff'}
            strokeWidth="1"
          />
        </svg>

        {/* Click & Hover Target Overlay */}
        <div
          className="absolute inset-0 flex"
          onMouseMove={(e) => {
            const rect = e.currentTarget.getBoundingClientRect();
            const relX = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width));
            const targetIdx = Math.round(relX * (points.length - 1));
            setHoveredIndex(targetIdx);
          }}
          onClick={(e) => {
            const rect = e.currentTarget.getBoundingClientRect();
            const relX = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width));
            const targetIdx = Math.round(relX * (points.length - 1));
            if (points[targetIdx]) {
              onSelectPly(points[targetIdx].ply);
            }
          }}
        />
      </div>

      {/* Floating Tooltip */}
      {hoveredPoint && (
        <div
          className={`absolute bottom-full left-1/2 -translate-x-1/2 mb-1 pointer-events-none px-2.5 py-1 rounded-lg text-[10px] font-mono shadow-xl border z-30 flex items-center gap-2 whitespace-nowrap ${
            isDark ? 'bg-[#1a1d26] border-white/15 text-neutral-100' : 'bg-white border-neutral-300 text-neutral-900'
          }`}
        >
          <span className="font-bold">
            {Math.ceil(hoveredPoint.ply / 2)}
            {hoveredPoint.turn === 'white' ? '.' : '...'} {hoveredPoint.san}
          </span>
          <span className="text-[#e05338] font-bold">
            {formatEval(hoveredPoint.scoreCp, hoveredPoint.mateIn)}
          </span>
          {hoveredPoint.classification && (
            <span
              className={`px-1.5 py-0.2 rounded text-[9px] font-bold ${
                hoveredPoint.classification === 'BLUNDER'
                  ? 'bg-rose-500/20 text-rose-400'
                  : hoveredPoint.classification === 'BRILLIANT'
                  ? 'bg-[#e05338]/20 text-[#e05338]'
                  : 'bg-amber-500/20 text-amber-400'
              }`}
            >
              {hoveredPoint.classification}
            </span>
          )}
        </div>
      )}
    </div>
  );
};
