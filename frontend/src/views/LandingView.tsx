// src/views/LandingView.tsx

import React, { useState } from 'react';
import { Radio, Mic, Play, Sparkles, ExternalLink, HelpCircle } from 'lucide-react';
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

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setValidationError(null);

    const parsed = parseLichessTarget(urlInput);
    if (!parsed || (!parsed.gameId && !parsed.roundId)) {
      setValidationError(
        'Invalid input. Please enter a valid Lichess game URL, broadcast round URL, or ID.'
      );
      return;
    }

    onStartBroadcast({
      gameId: parsed.gameId,
      roundId: parsed.roundId,
      enableTts,
      replayAll,
    });
  };

  const handleQuickLoad = (exampleUrl: string) => {
    setUrlInput(exampleUrl);
    setValidationError(null);
  };

  return (
    <div className="h-screen h-[100dvh] max-h-screen w-full bg-[#0a0c10] flex flex-col justify-between text-stone-100 px-4 py-2 sm:px-6 sm:py-3 select-none relative overflow-hidden">
      {/* Warm ambient background lighting */}
      <div className="absolute top-[-10%] left-[20%] w-[450px] h-[450px] rounded-full bg-amber-500/5 blur-[140px] pointer-events-none" />
      <div className="absolute bottom-[-10%] right-[20%] w-[450px] h-[450px] rounded-full bg-stone-700/10 blur-[140px] pointer-events-none" />

      {/* Header Branding */}
      <header className="shrink-0 flex items-center justify-between max-w-5xl mx-auto w-full py-2 border-b border-stone-800/80">
        <div className="flex items-center gap-3">
          <div className="p-2 rounded-xl bg-gradient-to-tr from-amber-500 to-amber-600 shadow-md shadow-amber-500/10 text-stone-950 font-black">
            <Radio className="w-4 h-4 text-stone-950" />
          </div>
          <div>
            <h1 className="font-bold text-base tracking-tight text-stone-100">
              CHESS STUDIO AI
            </h1>
            <p className="text-[10px] text-stone-400 font-mono">
              Live Broadcast Commentary & Grandmaster Telemetry
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2 text-xs text-stone-400">
          <span className="w-2 h-2 rounded-full bg-rose-500 animate-pulse" />
          <span className="font-mono text-[11px] font-medium">Gemini 2.5 + Stockfish 17</span>
        </div>
      </header>

      {/* Center Form Card */}
      <main className="flex-1 min-h-0 flex items-center justify-center max-w-lg mx-auto w-full py-2">
        <div className="w-full bg-[#12151d] border border-stone-800 rounded-2xl p-5 sm:p-6 shadow-2xl backdrop-blur-xl relative">
          <div className="text-center space-y-1.5 mb-5">
            <div className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full bg-amber-400/10 border border-amber-400/20 text-amber-300 text-[11px] font-semibold uppercase tracking-wider">
              <Sparkles className="w-3 h-3" />
              Tournament Engine
            </div>
            <h2 className="text-xl sm:text-2xl font-bold tracking-tight text-stone-100">
              Tune In To A Match
            </h2>
            <p className="text-[11px] text-stone-400 max-w-sm mx-auto">
              Stream any live Lichess match, broadcast round, or tournament with automated GM commentary.
            </p>
          </div>

          <form onSubmit={handleSubmit} className="space-y-4">
            {/* Input field */}
            <div className="space-y-1.5">
              <label className="text-xs font-semibold text-stone-300 flex items-center justify-between">
                <span>Lichess Game / Broadcast URL</span>
                <span className="text-stone-500 text-[10px] font-mono">Game ID or Round URL</span>
              </label>
              <div className="relative">
                <input
                  type="text"
                  value={urlInput}
                  onChange={(e) => {
                    setUrlInput(e.target.value);
                    if (validationError) setValidationError(null);
                  }}
                  placeholder="https://lichess.org/broadcast/... or 8-char ID"
                  className="w-full bg-[#0a0c10] border border-stone-700/80 rounded-xl px-3.5 py-2.5 text-xs sm:text-sm text-stone-100 placeholder-stone-600 focus:outline-none focus:border-amber-400/80 focus:ring-1 focus:ring-amber-400/80 font-mono transition-all"
                  autoFocus
                />
              </div>

              {validationError && (
                <p className="text-rose-400 text-xs font-medium pt-0.5">
                  {validationError}
                </p>
              )}
            </div>

            {/* Feature Toggles */}
            <div className="grid grid-cols-2 gap-2.5 pt-0.5">
              {/* Voice Toggle */}
              <button
                type="button"
                onClick={() => setEnableTts(!enableTts)}
                className={`flex items-center gap-2 p-2.5 rounded-xl border text-xs font-semibold text-left transition-all ${
                  enableTts
                    ? 'bg-amber-400/10 border-amber-400/30 text-amber-200'
                    : 'bg-[#0a0c10] border-stone-800 text-stone-500 hover:text-stone-400'
                }`}
              >
                <Mic className={`w-3.5 h-3.5 ${enableTts ? 'text-amber-400' : 'text-stone-600'}`} />
                <div className="flex flex-col">
                  <span>AI Voice Radio</span>
                  <span className="text-[10px] font-normal text-stone-400">
                    {enableTts ? 'ElevenLabs Active' : 'Muted'}
                  </span>
                </div>
              </button>

              {/* Replay vs Live Toggle */}
              <button
                type="button"
                onClick={() => setReplayAll(!replayAll)}
                className={`flex items-center gap-2 p-2.5 rounded-xl border text-xs font-semibold text-left transition-all ${
                  replayAll
                    ? 'bg-stone-800 border-stone-600 text-stone-200'
                    : 'bg-[#0a0c10] border-stone-800 text-stone-500 hover:text-stone-400'
                }`}
              >
                <Play className={`w-3.5 h-3.5 ${replayAll ? 'text-amber-400' : 'text-stone-600'}`} />
                <div className="flex flex-col">
                  <span>Start Mode</span>
                  <span className="text-[10px] font-normal text-stone-400">
                    {replayAll ? 'Replay (Move 1)' : 'Fast-Sync to Live'}
                  </span>
                </div>
              </button>
            </div>

            {/* Launch Button */}
            <button
              type="submit"
              className="w-full py-3 px-4 rounded-xl bg-amber-500 hover:bg-amber-400 text-stone-950 font-bold text-xs tracking-wider uppercase shadow-md shadow-amber-500/10 active:scale-[0.99] transition-all flex items-center justify-center gap-2"
            >
              <Radio className="w-3.5 h-3.5" />
              Enter Tournament / Studio
            </button>
          </form>

          {/* Preset Quick Links */}
          <div className="mt-4 pt-3.5 border-t border-stone-800/80 text-center space-y-1.5">
            <span className="text-[10px] text-stone-500 font-semibold uppercase tracking-wider block">
              Quick Test Inputs
            </span>
            <div className="flex flex-wrap items-center justify-center gap-2">
              <button
                onClick={() => handleQuickLoad('bmI956uk kSOgN8Sy')}
                className="text-[11px] font-mono text-amber-400 hover:text-amber-300 bg-[#0a0c10] border border-stone-800 px-2.5 py-1 rounded-md transition-colors"
              >
                Olympiad Round 3
              </button>
              <button
                onClick={() => handleQuickLoad('https://lichess.org/kSc2w4MX')}
                className="text-[11px] font-mono text-stone-300 hover:text-stone-100 bg-[#0a0c10] border border-stone-800 px-2.5 py-1 rounded-md transition-colors"
              >
                Casual Live Match
              </button>
            </div>
          </div>
        </div>
      </main>

      {/* Footer */}
      <footer className="shrink-0 max-w-5xl mx-auto w-full py-2 text-center text-xs text-stone-500 border-t border-stone-800/80 flex items-center justify-between">
        <span className="text-[11px]">Broadcast Commentary System</span>
        <div className="flex items-center gap-4 text-stone-500 text-[11px]">
          <span className="flex items-center gap-1 hover:text-stone-400 cursor-pointer">
            <HelpCircle className="w-3 h-3" /> Documentation
          </span>
          <span className="flex items-center gap-1 hover:text-stone-400 cursor-pointer">
            <ExternalLink className="w-3 h-3" /> Lichess API
          </span>
        </div>
      </footer>
    </div>
  );
};