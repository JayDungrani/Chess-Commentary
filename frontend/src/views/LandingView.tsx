// src/views/LandingView.tsx

import React, { useState, useRef } from 'react';
import {
  ArrowRight,
  Volume2,
  VolumeX,
  Zap,
  RotateCcw,
  Clipboard,
  Upload,
  BookOpen,
  Globe,
  FileText,
} from 'lucide-react';
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
    initialSnapshots?: any[];
    initialMetadata?: any;
    initialMoveDelay?: number;
  }) => void;
}

const HISTORICAL_PRESETS = [
  {
    name: 'Opera Game (Morphy 1858)',
    pgn: `[Event "A Night at the Opera"]
[Site "Paris FRA"]
[Date "1858.11.02"]
[White "Paul Morphy"]
[Black "Duke Karl / Count Isouard"]
[Result "1-0"]

1. e4 e5 2. Nf3 d6 3. d4 Bg4 4. dxe5 Bxf3 5. Qxf3 dxe5 6. Bc4 Nf6 7. Qb3 Qe7 8. Nc3 c6 9. Bg5 b5 10. Nxb5 cxb5 11. Bxb5+ Nbd7 12. O-O-O Rd8 13. Rxd7 Rxd7 14. Rd1 Qe6 15. Bxd7+ Nxd7 16. Qb8+ Nxb8 17. Rd8# 1-0`,
  },
  {
    name: 'Kasparov vs Deep Blue (1996)',
    pgn: `[Event "ACM Chess Challenge"]
[Site "Philadelphia, PA USA"]
[Date "1996.02.10"]
[White "Deep Blue"]
[Black "Garry Kasparov"]
[Result "1-0"]

1. e4 c5 2. c3 d5 3. exd5 Qxd5 4. d4 Nf6 5. Nf3 Bg4 6. Be2 e6 7. h3 Bh5 8. O-O Nc6 9. Be3 cxd4 10. cxd4 Bb4 11. a3 Ba5 12. Nc3 Qd6 13. Nb5 Qe7 14. Ne5 Bxe2 15. Qxe2 O-O 16. Rac1 Rac8 17. Bg5 Bb6 18. Bxf6 gxf6 19. Nc4 Rfd8 20. Nxb6 axb6 21. Rfd1 f5 22. Qe3 Qf6 23. d5 Rxd5 24. Rxd5 exd5 25. b3 Kh8 26. Qxb6 Rg8 27. Qc5 d4 28. Nd6 f4 29. Nxb7 Ne5 30. Qd5 f3 31. g3 Nd3 32. Rc7 Re8 33. Nd6 Re1+ 34. Kh2 Nxf2 35. Nxf7+ Kg7 36. Ng5+ Kh6 37. Rxh7+ 1-0`,
  },
  {
    name: 'The Immortal Game (1851)',
    pgn: `[Event "The Immortal Game"]
[Site "London ENG"]
[Date "1851.06.21"]
[White "Adolf Anderssen"]
[Black "Lionel Kieseritzky"]
[Result "1-0"]

1. e4 e5 2. f4 exf4 3. Bc4 Qh4+ 4. Kf1 b5 5. Bxb5 Nf6 6. Nf3 Qh6 7. d3 Nh5 8. Nh4 Qg5 9. Nf5 c6 10. g4 Nf6 11. Rg1 cxb5 12. h4 Qg6 13. h5 Qg5 14. Qf3 Ng8 15. Bxf4 Qf6 16. Nc3 Bc5 17. Nd5 Qxb2 18. Bd6 Bxg1 19. e5 Qxa1+ 20. Ke2 Na6 21. Nxg7+ Kd8 22. Qf6+ Nxf6 23. Be7# 1-0`,
  },
];

export const LandingView: React.FC<LandingViewProps> = ({ onStartBroadcast }) => {
  const [activeTab, setActiveTab] = useState<'lichess' | 'custom'>('lichess');
  const [urlInput, setUrlInput] = useState('');
  const [customText, setCustomText] = useState('');
  const [customMode, setCustomMode] = useState<'pgn' | 'fen'>('pgn');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [enableTts, setEnableTts] = useState(true);
  const [replayAll, setReplayAll] = useState(false);
  const [validationError, setValidationError] = useState<string | null>(null);

  const fileInputRef = useRef<HTMLInputElement>(null);
  const { isDark } = useTheme();

  // 1. Submit Lichess URL / ID
  const handleLichessSubmit = (e: React.FormEvent) => {
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

  // 2. Submit Custom PGN / FEN
  const handleCustomSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setValidationError(null);

    const trimmed = customText.trim();
    if (!trimmed) {
      setValidationError(
        customMode === 'pgn'
          ? 'Please enter or paste a PGN chess game string.'
          : 'Please enter a valid FEN position string.'
      );
      return;
    }

    setIsSubmitting(true);
    try {
      const payload =
        customMode === 'pgn'
          ? { pgn: trimmed, title: 'Custom PGN Studio', move_delay: 2.0 }
          : { fen: trimmed, title: 'Custom Position Studio', move_delay: 2.0 };

      const resp = await fetch('/api/custom/game', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });

      if (!resp.ok) {
        const errData = await resp.json().catch(() => ({}));
        throw new Error(errData.detail || 'Failed to upload custom game.');
      }

      const data = await resp.json();
      onStartBroadcast({
        gameId: data.game_id,
        enableTts,
        replayAll: true, // Custom games replay through all moves with live commentary
        initialSnapshots: data.snapshots,
        initialMetadata: data.metadata,
        initialMoveDelay: data.move_delay,
      });
    } catch (err: any) {
      setValidationError(err.message || 'Error initializing custom game.');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handlePasteClipboard = async () => {
    try {
      if (navigator.clipboard && navigator.clipboard.readText) {
        const text = await navigator.clipboard.readText();
        if (text) {
          if (activeTab === 'lichess') {
            setUrlInput(text.trim());
          } else {
            setCustomText(text.trim());
          }
          setValidationError(null);
        }
      }
    } catch {
      // Browser permission restricted; ignore gracefully
    }
  };

  const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = (event) => {
      const content = event.target?.result as string;
      if (content) {
        setCustomText(content);
        setCustomMode('pgn');
        setValidationError(null);
      }
    };
    reader.readAsText(file);
  };

  return (
    <div
      className={`h-screen h-[100dvh] max-h-screen w-full relative flex flex-col lg:flex-row select-none overflow-hidden transition-colors duration-200 ${
        isDark ? 'bg-[#0b0c0f] text-neutral-100' : 'bg-[#f5f6f9] text-neutral-900'
      }`}
    >
      {/* Full-Page 3D Neural Decision Tree Background - Spans entire viewport */}
      <div className="absolute inset-0 pointer-events-none z-0">
        <NeuralDecisionTreeBackground />
      </div>

      {/* Top Right Tactile Theme Switcher */}
      <header className="absolute top-4 right-4 sm:top-6 sm:right-6 z-30">
        <ThemeToggle />
      </header>

      {/* LEFT COLUMN: Telemetry HUD overlay */}
      <div className="w-full lg:w-1/2 h-[30vh] lg:h-full relative z-10 flex flex-col justify-between p-6 sm:p-8 lg:p-12 pointer-events-none shrink-0 bg-transparent">
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
      <div className="w-full lg:w-1/2 flex-1 flex items-center justify-center p-4 sm:p-6 lg:p-12 z-20 bg-transparent">
        <div className="w-full max-w-md">
          <div
            className={`backdrop-blur-xl rounded-2xl p-5 sm:p-6 transition-all ${
              isDark
                ? 'bg-[#13151b]/90 border border-white/[0.08] shadow-2xl shadow-black/80'
                : 'bg-white/90 border border-black/[0.08] shadow-2xl shadow-neutral-300/50'
            }`}
          >
            {/* Industrial Micro-Header */}
            <div
              className={`flex items-center justify-between border-b pb-3 mb-4 ${
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

            {/* Industrial Tab Selector */}
            <div
              className={`grid grid-cols-2 gap-1.5 p-1 rounded-xl mb-4 text-xs font-mono border ${
                isDark
                  ? 'bg-[#0b0c0f]/80 border-white/[0.06]'
                  : 'bg-neutral-100 border-neutral-200'
              }`}
            >
              <button
                type="button"
                onClick={() => {
                  setActiveTab('lichess');
                  setValidationError(null);
                }}
                className={`flex items-center justify-center gap-1.5 py-2 px-3 rounded-lg transition-all font-semibold ${
                  activeTab === 'lichess'
                    ? isDark
                      ? 'bg-[#1a1d26] text-neutral-100 shadow border border-white/10'
                      : 'bg-white text-neutral-900 shadow border border-neutral-200'
                    : isDark
                    ? 'text-neutral-500 hover:text-neutral-300'
                    : 'text-neutral-500 hover:text-neutral-800'
                }`}
              >
                <Globe className="w-3.5 h-3.5" />
                <span>LICHESS URL</span>
              </button>

              <button
                type="button"
                onClick={() => {
                  setActiveTab('custom');
                  setValidationError(null);
                }}
                className={`flex items-center justify-center gap-1.5 py-2 px-3 rounded-lg transition-all font-semibold ${
                  activeTab === 'custom'
                    ? isDark
                      ? 'bg-[#1a1d26] text-neutral-100 shadow border border-white/10'
                      : 'bg-white text-neutral-900 shadow border border-neutral-200'
                    : isDark
                    ? 'text-neutral-500 hover:text-neutral-300'
                    : 'text-neutral-500 hover:text-neutral-800'
                }`}
              >
                <FileText className="w-3.5 h-3.5" />
                <span>CUSTOM PGN / FEN</span>
              </button>
            </div>

            {/* TAB 1: LICHESS URL / ID INPUT */}
            {activeTab === 'lichess' ? (
              <form onSubmit={handleLichessSubmit} className="space-y-4">
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
                    className={`flex items-center justify-center gap-2 py-2 px-3 rounded-xl border text-xs font-mono transition-all ${
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
                    className={`flex items-center justify-center gap-2 py-2 px-3 rounded-xl border text-xs font-mono transition-all ${
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
            ) : (
              /* TAB 2: CUSTOM PGN / FEN INPUT */
              <form onSubmit={handleCustomSubmit} className="space-y-3.5">
                {/* Format Toggle & File Upload */}
                <div className="flex items-center justify-between gap-2 text-xs font-mono">
                  <div className="flex items-center gap-2">
                    <button
                      type="button"
                      onClick={() => setCustomMode('pgn')}
                      className={`px-2.5 py-1 rounded-lg border text-[11px] font-bold ${
                        customMode === 'pgn'
                          ? 'bg-[#e05338]/20 border-[#e05338] text-[#e05338]'
                          : isDark
                          ? 'border-white/10 text-neutral-400 hover:text-neutral-200'
                          : 'border-neutral-300 text-neutral-600 hover:text-neutral-900'
                      }`}
                    >
                      PGN GAME
                    </button>
                    <button
                      type="button"
                      onClick={() => setCustomMode('fen')}
                      className={`px-2.5 py-1 rounded-lg border text-[11px] font-bold ${
                        customMode === 'fen'
                          ? 'bg-[#e05338]/20 border-[#e05338] text-[#e05338]'
                          : isDark
                          ? 'border-white/10 text-neutral-400 hover:text-neutral-200'
                          : 'border-neutral-300 text-neutral-600 hover:text-neutral-900'
                      }`}
                    >
                      FEN POSITION
                    </button>
                  </div>

                  <div className="flex items-center gap-1">
                    <input
                      type="file"
                      ref={fileInputRef}
                      accept=".pgn,.txt"
                      onChange={handleFileUpload}
                      className="hidden"
                    />
                    <button
                      type="button"
                      onClick={() => fileInputRef.current?.click()}
                      title="Upload PGN file"
                      className={`flex items-center gap-1 px-2 py-1 rounded-lg border text-[11px] ${
                        isDark
                          ? 'border-white/10 text-neutral-400 hover:text-neutral-200 hover:bg-white/5'
                          : 'border-neutral-300 text-neutral-600 hover:text-neutral-900 hover:bg-black/5'
                      }`}
                    >
                      <Upload className="w-3.5 h-3.5" />
                      <span>UPLOAD</span>
                    </button>

                    <button
                      type="button"
                      onClick={handlePasteClipboard}
                      title="Paste from clipboard"
                      className={`p-1 rounded-lg border ${
                        isDark
                          ? 'border-white/10 text-neutral-400 hover:text-neutral-200 hover:bg-white/5'
                          : 'border-neutral-300 text-neutral-600 hover:text-neutral-900 hover:bg-black/5'
                      }`}
                    >
                      <Clipboard className="w-3.5 h-3.5" />
                    </button>
                  </div>
                </div>

                {/* Multiline Text Area */}
                <div className="space-y-1.5">
                  <textarea
                    rows={4}
                    value={customText}
                    onChange={(e) => {
                      setCustomText(e.target.value);
                      if (validationError) setValidationError(null);
                    }}
                    placeholder={
                      customMode === 'pgn'
                        ? 'Paste standard PGN text (e.g., 1. e4 e5 2. Nf3...)'
                        : 'Paste FEN position string...'
                    }
                    className={`w-full rounded-xl p-3 text-xs font-mono transition-all outline-none resize-none ${
                      isDark
                        ? 'bg-[#0b0c0f]/90 border border-white/[0.1] text-neutral-100 placeholder-neutral-500 focus:border-white/30 focus:ring-1 focus:ring-white/20'
                        : 'bg-neutral-50/90 border border-neutral-300 text-neutral-900 placeholder-neutral-400 focus:border-neutral-900 focus:ring-1 focus:ring-neutral-900/10'
                    }`}
                  />

                  {validationError && (
                    <p className="text-[#e05338] text-xs font-mono pl-1">
                      {validationError}
                    </p>
                  )}
                </div>

                {/* Historical Presets */}
                <div className="space-y-1">
                  <div className="flex items-center gap-1.5 text-[10px] font-mono text-neutral-500 uppercase tracking-wider">
                    <BookOpen className="w-3 h-3" />
                    <span>Quick Historical Presets:</span>
                  </div>
                  <div className="flex flex-wrap gap-1.5">
                    {HISTORICAL_PRESETS.map((preset, idx) => (
                      <button
                        key={idx}
                        type="button"
                        onClick={() => {
                          setCustomText(preset.pgn);
                          setCustomMode('pgn');
                          setValidationError(null);
                        }}
                        className={`text-[10px] font-mono px-2 py-1 rounded border transition-all ${
                          isDark
                            ? 'border-white/10 bg-[#1a1d26]/80 text-neutral-300 hover:border-white/25 hover:text-white'
                            : 'border-neutral-300 bg-neutral-100 text-neutral-700 hover:border-neutral-400 hover:text-neutral-900'
                        }`}
                      >
                        {preset.name.split(' ')[0]}
                      </button>
                    ))}
                  </div>
                </div>

                {/* Voice Switch */}
                <div className="pt-1">
                  <button
                    type="button"
                    onClick={() => setEnableTts(!enableTts)}
                    className={`w-full flex items-center justify-center gap-2 py-2 px-3 rounded-xl border text-xs font-mono transition-all ${
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
                    <span>{enableTts ? 'AI COMMENTARY AUDIO ON' : 'AI COMMENTARY AUDIO OFF'}</span>
                  </button>
                </div>

                {/* Submit Custom Broadcast Button */}
                <button
                  type="submit"
                  disabled={isSubmitting}
                  className="w-full py-3 px-4 rounded-xl bg-[#e05338] hover:bg-[#eb5e43] active:bg-[#c9452c] disabled:opacity-50 text-white font-mono font-bold text-xs tracking-widest uppercase shadow-md shadow-[#e05338]/15 active:scale-[0.99] transition-all flex items-center justify-center gap-2 mt-2"
                >
                  <span>{isSubmitting ? 'ANALYZING GAME...' : 'START CUSTOM BROADCAST'}</span>
                  <ArrowRight className="w-4 h-4" />
                </button>
              </form>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};