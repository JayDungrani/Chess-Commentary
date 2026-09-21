// src/components/common/NeuralDecisionTreeBackground.tsx

import React, { useEffect, useRef } from 'react';
import { useTheme } from '../../context/ThemeContext';

interface NodeData {
  id: string;
  x: number;
  y: number;
  z: number;
  label: string;
  evalStr: string;
  depth: number;
  isPV?: boolean; // Principal Variation (Stockfish best line)
  children?: NodeData[];
}

export const NeuralDecisionTreeBackground: React.FC = () => {
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
    let rotationAngle = 0;

    // Build realistic Stockfish MCTS Opening Decision Tree in 3D
    const rootNode: NodeData = {
      id: 'root',
      x: 0,
      y: -2.2,
      z: 0,
      label: 'START',
      evalStr: '+0.2',
      depth: 0,
      isPV: true,
      children: [
        {
          id: 'e4',
          x: 0.1,
          y: -1.3,
          z: 0.3,
          label: '1. e4',
          evalStr: '+0.32',
          depth: 1,
          isPV: true,
          children: [
            {
              id: 'e4_c5',
              x: 0.3,
              y: -0.4,
              z: 0.5,
              label: '1... c5',
              evalStr: '+0.28',
              depth: 2,
              isPV: true,
              children: [
                {
                  id: 'e4_c5_Nf3',
                  x: 0.5,
                  y: 0.5,
                  z: 0.6,
                  label: '2. Nf3',
                  evalStr: '+0.35',
                  depth: 3,
                  isPV: true,
                  children: [
                    {
                      id: 'e4_c5_Nf3_d6',
                      x: 0.7,
                      y: 1.3,
                      z: 0.7,
                      label: '2... d6',
                      evalStr: '+0.34',
                      depth: 4,
                      isPV: true,
                      children: [
                        {
                          id: 'e4_c5_Nf3_d6_d4',
                          x: 0.9,
                          y: 2.1,
                          z: 0.8,
                          label: '3. d4 cxd4 4. Nxd4',
                          evalStr: '+0.38 [NAJDORF]',
                          depth: 5,
                          isPV: true,
                        },
                        {
                          id: 'e4_c5_Nf3_d6_Bb5',
                          x: 0.3,
                          y: 2.0,
                          z: 1.2,
                          label: '3. Bb5+ [MOSCOW]',
                          evalStr: '+0.21',
                          depth: 5,
                        },
                      ],
                    },
                    {
                      id: 'e4_c5_Nf3_Nc6',
                      x: 1.1,
                      y: 1.2,
                      z: 0.2,
                      label: '2... Nc6',
                      evalStr: '+0.25',
                      depth: 4,
                      children: [
                        {
                          id: 'e4_c5_Nf3_Nc6_d4',
                          x: 1.5,
                          y: 2.0,
                          z: 0.3,
                          label: '3. d4 [OPEN]',
                          evalStr: '+0.30',
                          depth: 5,
                        },
                      ],
                    },
                    {
                      id: 'e4_c5_Nf3_e6',
                      x: 0.1,
                      y: 1.2,
                      z: 1.0,
                      label: '2... e6 [PAULSEN]',
                      evalStr: '+0.22',
                      depth: 4,
                    },
                  ],
                },
                {
                  id: 'e4_c5_Nc3',
                  x: -0.2,
                  y: 0.4,
                  z: 0.8,
                  label: '2. Nc3 [CLOSED]',
                  evalStr: '+0.15',
                  depth: 3,
                },
                {
                  id: 'e4_c5_c3',
                  x: 0.8,
                  y: 0.4,
                  z: 0.1,
                  label: '2. c3 [ALAPIN]',
                  evalStr: '+0.12',
                  depth: 3,
                },
              ],
            },
            {
              id: 'e4_e5',
              x: -0.6,
              y: -0.4,
              z: 0.2,
              label: '1... e5',
              evalStr: '+0.30',
              depth: 2,
              children: [
                {
                  id: 'e4_e5_Nf3',
                  x: -0.9,
                  y: 0.5,
                  z: 0.3,
                  label: '2. Nf3 Nc6 3. Bb5',
                  evalStr: '+0.33 [RUY LOPEZ]',
                  depth: 3,
                },
                {
                  id: 'e4_e5_Bc4',
                  x: -1.3,
                  y: 0.5,
                  z: -0.2,
                  label: '2. Bc4 [ITALIAN]',
                  evalStr: '+0.24',
                  depth: 3,
                },
              ],
            },
            {
              id: 'e4_c6',
              x: 0.6,
              y: -0.4,
              z: -0.5,
              label: '1... c6 [CARO-KANN]',
              evalStr: '+0.35',
              depth: 2,
              children: [
                {
                  id: 'e4_c6_d4',
                  x: 0.9,
                  y: 0.5,
                  z: -0.7,
                  label: '2. d4 d5 3. e5',
                  evalStr: '+0.41',
                  depth: 3,
                },
              ],
            },
            {
              id: 'e4_e6',
              x: -0.2,
              y: -0.4,
              z: -0.8,
              label: '1... e6 [FRENCH]',
              evalStr: '+0.29',
              depth: 2,
            },
          ],
        },
        {
          id: 'd4',
          x: -1.2,
          y: -1.3,
          z: -0.4,
          label: '1. d4',
          evalStr: '+0.25',
          depth: 1,
          children: [
            {
              id: 'd4_Nf6',
              x: -1.6,
              y: -0.4,
              z: -0.2,
              label: '1... Nf6',
              evalStr: '+0.22',
              depth: 2,
              children: [
                {
                  id: 'd4_Nf6_c4',
                  x: -2.0,
                  y: 0.5,
                  z: -0.3,
                  label: '2. c4 e6 3. Nc3 Bb4',
                  evalStr: '+0.26 [NIMZO]',
                  depth: 3,
                },
                {
                  id: 'd4_Nf6_Nf3',
                  x: -1.8,
                  y: 0.5,
                  z: 0.4,
                  label: '2. Nf3 g6 [KID]',
                  evalStr: '+0.28',
                  depth: 3,
                },
              ],
            },
            {
              id: 'd4_d5',
              x: -1.1,
              y: -0.4,
              z: -1.0,
              label: '1... d5 2. c4',
              evalStr: '+0.31 [QGD]',
              depth: 2,
            },
          ],
        },
        {
          id: 'Nf3',
          x: 1.2,
          y: -1.3,
          z: -0.5,
          label: '1. Nf3',
          evalStr: '+0.18',
          depth: 1,
          children: [
            {
              id: 'Nf3_d5',
              x: 1.6,
              y: -0.4,
              z: -0.3,
              label: '1... d5 2. g3 [RETI]',
              evalStr: '+0.20',
              depth: 2,
            },
          ],
        },
        {
          id: 'c4',
          x: -0.6,
          y: -1.3,
          z: -1.2,
          label: '1. c4',
          evalStr: '+0.15 [ENGLISH]',
          depth: 1,
        },
      ],
    };

    // Flatten nodes and edges for rendering and pulse animation
    interface Edge {
      from: NodeData;
      to: NodeData;
      isPV: boolean;
    }
    const allNodes: NodeData[] = [];
    const allEdges: Edge[] = [];

    function traverse(node: NodeData) {
      allNodes.push(node);
      if (node.children) {
        for (const child of node.children) {
          allEdges.push({
            from: node,
            to: child,
            isPV: Boolean(node.isPV && child.isPV),
          });
          traverse(child);
        }
      }
    }
    traverse(rootNode);

    // Dynamic signal pulses traveling along edges
    interface Pulse {
      edgeIndex: number;
      progress: number; // 0..1
      speed: number;
      color: string;
    }
    const pulses: Pulse[] = [];
    const NUM_PULSES = 16;
    for (let i = 0; i < NUM_PULSES; i++) {
      pulses.push({
        edgeIndex: Math.floor(Math.random() * allEdges.length),
        progress: Math.random(),
        speed: 0.004 + Math.random() * 0.007,
        color: Math.random() > 0.4 ? '#e05338' : '#ffffff',
      });
    }

    const resizeCanvas = () => {
      const parent = canvas.parentElement;
      const width = parent ? parent.clientWidth : window.innerWidth;
      const height = parent ? parent.clientHeight : window.innerHeight;
      const dpr = window.devicePixelRatio || 1;
      canvas.width = width * dpr;
      canvas.height = height * dpr;
      canvas.style.width = `${width}px`;
      canvas.style.height = `${height}px`;
      ctx.scale(dpr, dpr);
    };

    resizeCanvas();
    window.addEventListener('resize', resizeCanvas);
    const resizeObserver = new ResizeObserver(() => resizeCanvas());
    if (canvas.parentElement) {
      resizeObserver.observe(canvas.parentElement);
    }

    // 3D Projection Math
    const project = (
      node: { x: number; y: number; z: number },
      centerX: number,
      centerY: number,
      baseScale: number,
      tiltX: number
    ) => {
      const cosY = Math.cos(rotationAngle);
      const sinY = Math.sin(rotationAngle);
      const cosX = Math.cos(tiltX);
      const sinX = Math.sin(tiltX);

      // Rotate Y
      const x1 = node.x * cosY + node.z * sinY;
      const y1 = node.y;
      const z1 = -node.x * sinY + node.z * cosY;

      // Tilt X
      const x2 = x1;
      const y2 = y1 * cosX - z1 * sinX;
      const z2 = y1 * sinX + z1 * cosX;

      const camDist = 5.5;
      const fov = camDist / (camDist + z2);

      return {
        x: centerX + x2 * fov * baseScale,
        y: centerY + y2 * fov * baseScale,
        scale: fov,
        z: z2,
      };
    };

    const render = () => {
      const parent = canvas.parentElement;
      const width = parent ? parent.clientWidth : window.innerWidth;
      const height = parent ? parent.clientHeight : window.innerHeight;
      const dark = isDarkRef.current;

      ctx.clearRect(0, 0, width, height);

      const isWide = width >= 1024;
      const centerX = isWide ? width * 0.35 : width * 0.5;
      const centerY = isWide ? height * 0.5 : height * 0.36;
      const baseScale = isWide ? Math.min(width * 0.7, height) * 0.35 : Math.min(width, height) * 0.30;
      const tiltX = 0.25; // Gentle tilt forward to see branches in 3D

      // 1. Draw Tree Branch Filaments (Edges)
      for (let i = 0; i < allEdges.length; i++) {
        const edge = allEdges[i];
        const p1 = project(edge.from, centerX, centerY, baseScale, tiltX);
        const p2 = project(edge.to, centerX, centerY, baseScale, tiltX);

        ctx.beginPath();
        ctx.moveTo(p1.x, p1.y);

        // Gentle curved spline
        const midX = (p1.x + p2.x) * 0.5;
        const midY = (p1.y + p2.y) * 0.5 - 6 * p1.scale;
        ctx.quadraticCurveTo(midX, midY, p2.x, p2.y);

        if (edge.isPV) {
          // Principal Variation (best line): Signal Orange
          ctx.strokeStyle = dark ? 'rgba(224, 83, 56, 0.75)' : 'rgba(224, 83, 56, 0.85)';
          ctx.lineWidth = 1.6 * p1.scale;
        } else {
          ctx.strokeStyle = dark
            ? `rgba(225, 230, 240, ${Math.max(0.06, 0.18 - edge.to.depth * 0.03)})`
            : `rgba(20, 25, 35, ${Math.max(0.06, 0.16 - edge.to.depth * 0.025)})`;
          ctx.lineWidth = 0.75 * p1.scale;
        }
        ctx.stroke();
      }

      // 2. Animate and Draw Traveling Data Pulses (Signal Packets)
      for (let i = 0; i < pulses.length; i++) {
        const pulse = pulses[i];
        pulse.progress += pulse.speed;
        if (pulse.progress >= 1.0) {
          pulse.progress = 0;
          pulse.edgeIndex = Math.floor(Math.random() * allEdges.length);
        }

        const edge = allEdges[pulse.edgeIndex];
        const p1 = project(edge.from, centerX, centerY, baseScale, tiltX);
        const p2 = project(edge.to, centerX, centerY, baseScale, tiltX);

        // Interpolate position
        const t = pulse.progress;
        const midX = (p1.x + p2.x) * 0.5;
        const midY = (p1.y + p2.y) * 0.5 - 6 * p1.scale;

        // Quadratic curve interpolation
        const invT = 1 - t;
        const curX = invT * invT * p1.x + 2 * invT * t * midX + t * t * p2.x;
        const curY = invT * invT * p1.y + 2 * invT * t * midY + t * t * p2.y;

        ctx.beginPath();
        ctx.arc(curX, curY, 1.8 * p1.scale, 0, Math.PI * 2);
        ctx.fillStyle = edge.isPV
          ? '#e05338'
          : dark
          ? 'rgba(255, 255, 255, 0.85)'
          : 'rgba(20, 25, 35, 0.8)';
        ctx.fill();
      }

      // 3. Draw Nodes and Micro-Labels
      for (const node of allNodes) {
        const p = project(node, centerX, centerY, baseScale, tiltX);
        const radius = node.isPV ? 3.5 * p.scale : 2.2 * p.scale;

        // Node circle
        ctx.beginPath();
        ctx.arc(p.x, p.y, radius, 0, Math.PI * 2);

        if (node.isPV) {
          ctx.fillStyle = '#e05338';
          ctx.fill();
          // Subtle halo ring around PV nodes
          ctx.beginPath();
          ctx.arc(p.x, p.y, radius + 2.5 * p.scale, 0, Math.PI * 2);
          ctx.strokeStyle = 'rgba(224, 83, 56, 0.35)';
          ctx.lineWidth = 0.8;
          ctx.stroke();
        } else {
          ctx.fillStyle = dark ? 'rgba(225, 230, 240, 0.5)' : 'rgba(20, 25, 35, 0.45)';
          ctx.fill();
        }

        // Monospace Move Label & Evaluation Text
        const fontSize = Math.max(7, Math.round(9 * p.scale));
        ctx.font = `${fontSize}px monospace`;
        ctx.textAlign = 'left';
        ctx.textBaseline = 'middle';

        // Offset label slightly right
        const textX = p.x + radius + 4;
        const textY = p.y;

        if (node.isPV) {
          ctx.fillStyle = dark ? '#ffffff' : '#111318';
          ctx.fillText(node.label, textX, textY - fontSize * 0.55);
          ctx.fillStyle = '#e05338';
          ctx.fillText(node.evalStr, textX, textY + fontSize * 0.55);
        } else if (node.depth <= 3) {
          ctx.fillStyle = dark ? 'rgba(200, 205, 220, 0.45)' : 'rgba(50, 55, 70, 0.55)';
          ctx.fillText(`${node.label} (${node.evalStr})`, textX, textY);
        }
      }

      // 4. Industrial Telemetry Subtitle at bottom
      ctx.font = '10px monospace';
      ctx.textAlign = isWide ? 'left' : 'center';
      ctx.fillStyle = dark ? 'rgba(225, 230, 240, 0.22)' : 'rgba(20, 25, 35, 0.22)';
      const textX = isWide ? Math.max(32, width * 0.04) : width * 0.5;
      ctx.fillText(
        'MCTS EVALUATION TREE // DEPTH 26 // 18.4M NODES',
        textX,
        height * 0.965
      );

      // Slow 360-degree rotation (~45 seconds per turn)
      rotationAngle += 0.0022;

      animationFrameId = requestAnimationFrame(render);
    };

    render();

    return () => {
      window.removeEventListener('resize', resizeCanvas);
      resizeObserver.disconnect();
      cancelAnimationFrame(animationFrameId);
    };
  }, []);

  return (
    <div className="absolute inset-0 pointer-events-none overflow-hidden select-none z-0">
      <canvas ref={canvasRef} className="w-full h-full block" />
    </div>
  );
};
