// src/components/common/RotatingKingBackground.tsx

import React, { useEffect, useRef } from 'react';
import { useTheme } from '../../context/ThemeContext';

export const RotatingKingBackground: React.FC = () => {
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
    let angleY = 0;

    // 2D silhouette profile of a Chess King: [normalized y (0..1.12), radius r (0..0.45)]
    const profile: [number, number][] = [
      [0.00, 0.44],
      [0.02, 0.44],
      [0.05, 0.41],
      [0.08, 0.36],
      [0.11, 0.38],
      [0.13, 0.33],
      [0.17, 0.28],
      [0.24, 0.23],
      [0.32, 0.20],
      [0.42, 0.19],
      [0.52, 0.21],
      [0.61, 0.24],
      [0.69, 0.28],
      [0.72, 0.32],
      [0.75, 0.27],
      [0.78, 0.26],
      [0.83, 0.32],
      [0.89, 0.35],
      [0.94, 0.34],
      [0.98, 0.26],
      [1.00, 0.12],
    ];

    const SLICES = 28;
    const tiltX = 0.22;
    const cosTilt = Math.cos(tiltX);
    const sinTilt = Math.sin(tiltX);

    // Cross definition at top of crown [startPoint, endPoint]
    const crossSegments: [[number, number, number], [number, number, number]][] = [
      [[0, 1.00, 0], [0, 1.15, 0]],
      [[-0.065, 1.09, 0], [0.065, 1.09, 0]],
      [[-0.02, 1.15, 0], [0.02, 1.15, 0]],
      [[-0.065, 1.075, 0], [-0.065, 1.105, 0]],
      [[0.065, 1.075, 0], [0.065, 1.105, 0]],
    ];

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

    const render = () => {
      const width = window.innerWidth;
      const height = window.innerHeight;
      const dark = isDarkRef.current;
      const strokeRgb = dark ? '225, 230, 240' : '20, 25, 35';

      ctx.clearRect(0, 0, width, height);

      const centerX = width * 0.5;
      const centerY = height * 0.48;
      const baseScale = Math.min(width, height) * 0.72;
      const camDist = 2.4;

      const cosY = Math.cos(angleY);
      const sinY = Math.sin(angleY);

      const meshRings: { px: number; py: number; z: number; alpha: number }[][] = [];

      for (let i = 0; i < profile.length; i++) {
        const [rawY, r] = profile[i];
        const y0 = rawY - 0.55;

        const ring: { px: number; py: number; z: number; alpha: number }[] = [];
        for (let j = 0; j < SLICES; j++) {
          const phi = (j * 2 * Math.PI) / SLICES;
          const x0 = r * Math.cos(phi);
          const z0 = r * Math.sin(phi);

          const x1 = x0 * cosY + z0 * sinY;
          const y1 = y0;
          const z1 = -x0 * sinY + z0 * cosY;

          const x2 = x1;
          const y2 = y1 * cosTilt - z1 * sinTilt;
          const z2 = y1 * sinTilt + z1 * cosTilt;

          const fov = camDist / (camDist + z2);
          const px = centerX + x2 * fov * baseScale;
          const py = centerY - y2 * fov * baseScale;

          const normZ = (z2 + 0.4) / 0.8;
          const alpha = Math.max(0.04, Math.min(0.38, 0.42 - normZ * 0.32));

          ring.push({ px, py, z: z2, alpha });
        }
        meshRings.push(ring);
      }

      // Draw subtle ambient gradient centered on the King
      const radialGlow = ctx.createRadialGradient(
        centerX,
        centerY,
        baseScale * 0.1,
        centerX,
        centerY,
        baseScale * 0.65
      );
      if (dark) {
        radialGlow.addColorStop(0, 'rgba(255, 255, 255, 0.02)');
        radialGlow.addColorStop(0.6, 'rgba(200, 205, 215, 0.005)');
        radialGlow.addColorStop(1, 'rgba(11, 12, 15, 0)');
      } else {
        radialGlow.addColorStop(0, 'rgba(0, 0, 0, 0.025)');
        radialGlow.addColorStop(0.6, 'rgba(0, 0, 0, 0.006)');
        radialGlow.addColorStop(1, 'rgba(245, 246, 249, 0)');
      }
      ctx.fillStyle = radialGlow;
      ctx.beginPath();
      ctx.arc(centerX, centerY, baseScale * 0.7, 0, Math.PI * 2);
      ctx.fill();

      // 1. Draw horizontal rings (latitudes)
      for (let i = 0; i < meshRings.length; i++) {
        const ring = meshRings[i];
        let avgZ = 0;
        for (let j = 0; j < SLICES; j++) avgZ += ring[j].z;
        avgZ /= SLICES;

        const isFeatureRing = i === 0 || i === 4 || i === 11 || i === 13 || i === 17 || i === ring.length - 1;
        const baseAlpha = isFeatureRing ? (dark ? 0.16 : 0.14) : (dark ? 0.07 : 0.06);
        const depthFactor = Math.max(0.3, 1.0 - (avgZ + 0.3) * 0.9);
        const strokeAlpha = (baseAlpha * depthFactor).toFixed(3);

        ctx.beginPath();
        for (let j = 0; j < SLICES; j++) {
          const pt = ring[j];
          if (j === 0) ctx.moveTo(pt.px, pt.py);
          else ctx.lineTo(pt.px, pt.py);
        }
        ctx.closePath();
        ctx.strokeStyle = `rgba(${strokeRgb}, ${strokeAlpha})`;
        ctx.lineWidth = isFeatureRing ? 0.95 : 0.6;
        ctx.stroke();
      }

      // 2. Draw vertical longitudinal ribs
      const RIB_STEP = 2;
      for (let j = 0; j < SLICES; j += RIB_STEP) {
        ctx.beginPath();
        let ribAvgZ = 0;
        for (let i = 0; i < meshRings.length; i++) {
          const pt = meshRings[i][j];
          ribAvgZ += pt.z;
          if (i === 0) ctx.moveTo(pt.px, pt.py);
          else ctx.lineTo(pt.px, pt.py);
        }
        ribAvgZ /= meshRings.length;
        const ribDepthFactor = Math.max(0.2, 1.0 - (ribAvgZ + 0.3) * 0.95);
        const ribAlpha = ((dark ? 0.08 : 0.07) * ribDepthFactor).toFixed(3);

        ctx.strokeStyle = `rgba(${strokeRgb}, ${ribAlpha})`;
        ctx.lineWidth = 0.65;
        ctx.stroke();
      }

      // 3. Draw King's Finial Cross on top of the Crown
      ctx.lineWidth = 1.2;
      for (const [p1, p2] of crossSegments) {
        const transformPoint = (p: [number, number, number]) => {
          const x0 = p[0];
          const y0 = p[1] - 0.55;
          const z0 = p[2];

          const x1 = x0 * cosY + z0 * sinY;
          const y1 = y0;
          const z1 = -x0 * sinY + z0 * cosY;

          const x2 = x1;
          const y2 = y1 * cosTilt - z1 * sinTilt;
          const z2 = y1 * sinTilt + z1 * cosTilt;

          const fov = camDist / (camDist + z2);
          return {
            px: centerX + x2 * fov * baseScale,
            py: centerY - y2 * fov * baseScale,
            z: z2,
          };
        };

        const v1 = transformPoint(p1);
        const v2 = transformPoint(p2);
        const crossAlpha = Math.max(0.12, Math.min(0.4, 0.4 - ((v1.z + v2.z) / 2) * 0.4)).toFixed(3);

        ctx.beginPath();
        ctx.moveTo(v1.px, v1.py);
        ctx.lineTo(v2.px, v2.py);
        ctx.strokeStyle = `rgba(${strokeRgb}, ${crossAlpha})`;
        ctx.stroke();
      }

      angleY += 0.005;

      animationFrameId = requestAnimationFrame(render);
    };

    render();

    return () => {
      window.removeEventListener('resize', resizeCanvas);
      cancelAnimationFrame(animationFrameId);
    };
  }, []);

  return (
    <div className="absolute inset-0 pointer-events-none overflow-hidden select-none z-0">
      <canvas ref={canvasRef} className="w-full h-full block" />
      <div className="absolute inset-0 bg-radial from-transparent via-[#f5f6f9]/50 to-[#f5f6f9]/95 dark:via-[#0b0c0f]/50 dark:to-[#0b0c0f]/95 pointer-events-none" />
    </div>
  );
};
