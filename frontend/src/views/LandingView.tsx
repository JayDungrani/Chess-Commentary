// src/views/LandingView.tsx

import React, { useState } from 'react';
import { ArrowRight, Volume2, VolumeX, Zap, RotateCcw, Clipboard } from 'lucide-react';
import { NeuralDecisionTreeBackground } from '../components/common/NeuralDecisionTreeBackground';
import { ThemeToggle } from '../components/common/ThemeToggle';
import { useTheme } from '../context/ThemeContext';
import { parseLichessTarget } from '../utils/urlParser';

interface LandingViewProps {
  onStartBroadcast: (config: {
    gameId?: string;
    roundId?: string;
    enableTts: boolean;
    replayAll: boolean;
  }) => void;
}

export const LandingView: React.FC<LandingViewProps> = ({ onStartBroadcast }) => {
  const [urlInput, setUrlInput] = useState('');
  const [enableTts, setEnableTts] = useState(true);
  const [replayAll, setReplayAll] = useState(false);
  const [validationError, setValidationError] = useState<string | null>(null);
  const { isDark } = useTheme();

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setValidationError(null);

    const parsed = parseLichessTarget(urlInput);
    if (!parsed || (!parsed.gameId && !parsed.roundId)) {
      setValidationError('Please enter a valid Lichess game URL, broadcast round, or ID.');
      return;
    }

    onStartBroadcast({
      gameId: parsed.gameId,
      roundId: parsed.roundId,
      enableTts,
      replayAll,
    });
  };

  const handlePasteClipboard = async () => {
    try {
      if (navigator.clipboard && navigator.clipboard.readText) {
        const text = await navigator.clipboard.readText();
        if (text) {
          setUrlInput(text.trim());
          setValidationError(null);
        }
      }
    } catch {
      // Browser permission restricted; ignore gracefully
    }
  };

  return (
    <div
      className={`h-screen h-[100dvh] max-h-screen w-full relative flex flex-col lg:flex-row select-none overflow-hidden transition-colors duration-200 ${
        isDark ? 'bg-[#0b0c0f] text-neutral-100' : 'bg-[#f5f6f9] text-neutral-900'
      }`}
    >
      {/* Full-Page 3D Neural Decision Tree Background - Spans entire viewport, anchored to left */}
      <div className="absolute inset-0 pointer-events-none z-0">
        <NeuralDecisionTreeBackground />
      </div>

      {/* Top Right Tactile Theme Switcher */}
      <header className="absolute top-4 right-4 sm:top-6 sm:right-6 z-30">
        <ThemeToggle />
      </header>

      {/* LEFT COLUMN: Telemetry HUD overlay */}
      <div className="w-full lg:w-1/2 h-[35vh] lg:h-full relative z-10 flex flex-col justify-between p-6 sm:p-8 lg:p-12 pointer-events-none shrink-0 bg-transparent">
        {/* Top Left Telemetry Tag */}
        <div className="flex items-center justify-between pointer-events-auto">
          <div className="flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-[#e05338] animate-pulse" />
            <span
              className={`font-mono text-[11px] uppercase tracking-widest font-semibold ${
                isDark ? 'text-neutral-400' : 'text-neutral-600'
              }`}
            >
              MCTS DECISION TREE
            </span>
          </div>
          <span
            className={`font-mono text-[10px] uppercase tracking-wider ${
              isDark ? 'text-neutral-600' : 'text-neutral-400'
            }`}
          >
            STOCKFISH 17 NNUE
          </span>
        </div>

        {/* Bottom Left Telemetry Tag */}
        <div
          className={`pointer-events-auto flex items-center justify-between font-mono text-[10px] tracking-wider pt-2 ${
            isDark ? 'text-neutral-500' : 'text-neutral-500'
          }`}
        >
          <span>PV: 1. e4 c5 2. Nf3 d6 3. d4 cxd4 4. Nxd4 [NAJDORF]</span>
          <span className="text-[#e05338] font-bold">+0.38 EVAL</span>
        </div>
      </div>

      {/* RIGHT COLUMN: Minimalist Input Console & Controls */}
      <div className="w-full lg:w-1/2 flex-1 flex items-center justify-center p-6 sm:p-8 lg:p-12 z-20 bg-transparent">
        <div className="w-full max-w-md">
          <div
            className={`backdrop-blur-xl rounded-2xl p-6 sm:p-7 transition-all ${
              isDark
                ? 'bg-[#13151b]/85 border border-white/[0.08] shadow-2xl shadow-black/80'
                : 'bg-white/85 border border-black/[0.08] shadow-2xl shadow-neutral-300/50'
            }`}
          >
            {/* Industrial Micro-Header */}
            <div
              className={`flex items-center justify-between border-b pb-3.5 mb-5 ${
                isDark ? 'border-white/[0.06]' : 'border-black/[0.06]'
              }`}
            >
              <div className="flex items-center gap-2">
                <span className="w-1.5 h-1.5 rounded-full bg-[#e05338]" />
                <span
                  className={`font-mono text-[11px] uppercase tracking-widest font-semibold ${
                    isDark ? 'text-neutral-300' : 'text-neutral-800'
                  }`}
                >
                  CHESS STUDIO // AI-01
                </span>
              </div>
              <span
                className={`font-mono text-[10px] uppercase tracking-wider ${
                  isDark ? 'text-neutral-500' : 'text-neutral-400'
                }`}
              >
                TELEMETRY READY
              </span>
            </div>

            <form onSubmit={handleSubmit} className="space-y-4">
              {/* Precision Input Field */}
              <div className="space-y-1.5">
                <div className="relative flex items-center">
                  <input
                    type="text"
                    value={urlInput}
                    onChange={(e) => {
                      setUrlInput(e.target.value);
                      if (validationError) setValidationError(null);
                    }}
                    placeholder="Paste Lichess URL or Game ID..."
                    className={`w-full rounded-xl pl-3.5 pr-10 py-3 text-xs sm:text-sm font-mono transition-all outline-none ${
                      isDark
                        ? 'bg-[#0b0c0f]/90 border border-white/[0.1] text-neutral-100 placeholder-neutral-500 focus:border-white/30 focus:ring-1 focus:ring-white/20'
                        : 'bg-neutral-50/90 border border-neutral-300 text-neutral-900 placeholder-neutral-400 focus:border-neutral-900 focus:ring-1 focus:ring-neutral-900/10'
                    }`}
                    autoFocus
                  />
                  <button
                    type="button"
                    onClick={handlePasteClipboard}
                    title="Paste from clipboard"
                    className={`absolute right-2.5 p-1.5 rounded-lg transition-colors ${
                      isDark
                        ? 'text-neutral-400 hover:text-neutral-100 hover:bg-white/[0.06]'
                        : 'text-neutral-400 hover:text-neutral-800 hover:bg-black/[0.04]'
                    }`}
                  >
                    <Clipboard className="w-4 h-4" />
                  </button>
                </div>

                {validationError && (
                  <p className="text-[#e05338] text-xs font-mono pl-1">
                    {validationError}
                  </p>
                )}
              </div>

              {/* Industrial Segmented Switches */}
              <div className="grid grid-cols-2 gap-2.5 pt-1">
                {/* Voice Switch */}
                <button
                  type="button"
                  onClick={() => setEnableTts(!enableTts)}
                  className={`flex items-center justify-center gap-2 py-2.5 px-3 rounded-xl border text-xs font-mono transition-all ${
                    enableTts
                      ? isDark
                        ? 'bg-[#1a1d26] border-white/20 text-neutral-100'
                        : 'bg-neutral-100 border-neutral-300 text-neutral-900 shadow-sm'
                      : isDark
                      ? 'bg-[#0b0c0f]/70 border-white/[0.05] text-neutral-500 hover:text-neutral-400'
                      : 'bg-white/60 border-neutral-200 text-neutral-400 hover:text-neutral-700'
                  }`}
                >
                  <span
                    className={`w-1.5 h-1.5 rounded-full shrink-0 ${
                      enableTts ? 'bg-[#e05338]' : isDark ? 'bg-neutral-600' : 'bg-neutral-400'
                    }`}
                  />
                  {enableTts ? (
                    <Volume2
                      className={`w-3.5 h-3.5 shrink-0 ${
                        isDark ? 'text-neutral-300' : 'text-neutral-700'
                      }`}
                    />
                  ) : (
                    <VolumeX
                      className={`w-3.5 h-3.5 shrink-0 ${
                        isDark ? 'text-neutral-500' : 'text-neutral-400'
                      }`}
                    />
                  )}
                  <span>{enableTts ? 'VOICE ON' : 'VOICE OFF'}</span>
                </button>

                {/* Sync Switch */}
                <button
                  type="button"
                  onClick={() => setReplayAll(!replayAll)}
                  className={`flex items-center justify-center gap-2 py-2.5 px-3 rounded-xl border text-xs font-mono transition-all ${
                    !replayAll
                      ? isDark
                        ? 'bg-[#1a1d26] border-white/20 text-neutral-100'
                        : 'bg-neutral-100 border-neutral-300 text-neutral-900 shadow-sm'
                      : isDark
                      ? 'bg-[#0b0c0f]/70 border-white/[0.05] text-neutral-400 hover:text-neutral-300'
                      : 'bg-white/60 border-neutral-200 text-neutral-500 hover:text-neutral-800'
                  }`}
                >
                  <span
                    className={`w-1.5 h-1.5 rounded-full shrink-0 ${
                      !replayAll ? 'bg-[#e05338]' : isDark ? 'bg-neutral-600' : 'bg-neutral-400'
                    }`}
                  />
                  {!replayAll ? (
                    <Zap
                      className={`w-3.5 h-3.5 shrink-0 ${
                        isDark ? 'text-neutral-300' : 'text-neutral-700'
                      }`}
                    />
                  ) : (
                    <RotateCcw
                      className={`w-3.5 h-3.5 shrink-0 ${
                        isDark ? 'text-neutral-400' : 'text-neutral-500'
                      }`}
                    />
                  )}
                  <span>{!replayAll ? 'LIVE SYNC' : 'REPLAY'}</span>
                </button>
              </div>

              {/* Tactile Signal Orange Action Button */}
              <button
                type="submit"
                className="w-full py-3 px-4 rounded-xl bg-[#e05338] hover:bg-[#eb5e43] active:bg-[#c9452c] text-white font-mono font-bold text-xs tracking-widest uppercase shadow-md shadow-[#e05338]/15 active:scale-[0.99] transition-all flex items-center justify-center gap-2 mt-2"
              >
                <span>INITIALIZE STREAM</span>
                <ArrowRight className="w-4 h-4" />
              </button>
            </form>
          </div>
        </div>
      </div>
    </div>
  );
};