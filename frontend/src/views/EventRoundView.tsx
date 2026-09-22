import React, { useEffect, useState, useMemo } from 'react';
import {
  Trophy,
  ArrowLeft,
  RotateCw,
  Search,
  Radio,
  Users,
  CheckCircle2,
} from 'lucide-react';
import { Chessboard } from 'react-chessboard';
import type { BroadcastGameSummary } from '../types/broadcast';
import { CountryFlag } from '../components/common/CountryFlag';
import { ThemeToggle } from '../components/common/ThemeToggle';
import { useTheme } from '../context/ThemeContext';

interface EventRoundViewProps {
  roundId: string;
  onSelectGame: (gameId: string) => void;
  onBack: () => void;
}

export const EventRoundView: React.FC<EventRoundViewProps> = ({
  roundId,
  onSelectGame,
  onBack,
}) => {
  const { isDark } = useTheme();
  const [games, setGames] = useState<BroadcastGameSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [isRefreshing, setIsRefreshing] = useState(false);

  const fetchRoundGames = async (silent = false) => {
    if (!silent) setIsRefreshing(true);
    setError(null);
    try {
      const response = await fetch(`/api/broadcast/${encodeURIComponent(roundId)}/games`);
      if (!response.ok) {
        throw new Error(`Failed to load round data (HTTP ${response.status})`);
      }
      const data: BroadcastGameSummary[] = await response.json();
      setGames(data);
    } catch (err: any) {
      setError(err.message || 'Unable to fetch tournament round pairings.');
    } finally {
      setLoading(false);
      setIsRefreshing(false);
    }
  };

  // Initial load + polling every 12 seconds
  useEffect(() => {
    fetchRoundGames();
    const interval = setInterval(() => {
      fetchRoundGames(true);
    }, 12000);
    return () => clearInterval(interval);
  }, [roundId]);

  // Filter games by player names or board number
  const filteredGames = useMemo(() => {
    if (!searchQuery.trim()) return games;
    const query = searchQuery.toLowerCase();
    return games.filter((g, index) => {
      const boardNum = (g.board ?? index + 1).toString();
      const whiteName = (g.white_name || g.white?.name || g.white?.username || '').toLowerCase();
      const blackName = (g.black_name || g.black?.name || g.black?.username || '').toLowerCase();
      return (
        boardNum.includes(query) ||
        whiteName.includes(query) ||
        blackName.includes(query)
      );
    });
  }, [games, searchQuery]);

  return (
    <div
      className={`h-screen h-[100dvh] max-h-screen w-full flex flex-col justify-between overflow-hidden select-none transition-colors duration-200 ${
        isDark ? 'bg-[#0b0c0f] text-neutral-100' : 'bg-[#f5f6f9] text-neutral-900'
      }`}
    >
      {/* 1. Header Bar */}
      <header
        className={`shrink-0 border-b px-4 py-3 flex items-center justify-between shadow-sm z-30 transition-colors duration-200 ${
          isDark ? 'bg-[#13151b] border-white/[0.08]' : 'bg-white border-neutral-200'
        }`}
      >
        <div className="flex items-center gap-3">
          <button
            onClick={onBack}
            className={`p-1.5 rounded-lg border transition-colors ${
              isDark
                ? 'bg-[#181c26] hover:bg-neutral-800 text-neutral-400 hover:text-neutral-100 border-white/[0.08]'
                : 'bg-neutral-100 hover:bg-neutral-200 text-neutral-600 hover:text-neutral-900 border-neutral-200'
            }`}
            title="Back to Home"
          >
            <ArrowLeft className="w-4 h-4" />
          </button>

          <div className="flex items-center gap-2.5">
            <div className="p-2 rounded-xl bg-[#e05338]/10 border border-[#e05338]/25 text-[#e05338]">
              <Trophy className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h1
                  className={`font-bold text-base tracking-tight ${
                    isDark ? 'text-neutral-100' : 'text-neutral-900'
                  }`}
                >
                  Tournament Round Broadcast
                </h1>
                <span
                  className={`text-[10px] font-mono font-bold px-2 py-0.5 rounded border ${
                    isDark
                      ? 'bg-[#181c26] text-[#e05338] border-white/[0.08]'
                      : 'bg-neutral-100 text-[#e05338] border-neutral-200'
                  }`}
                >
                  ROUND {roundId.slice(0, 8)}
                </span>
              </div>
              <p className={`text-[11px] font-mono ${isDark ? 'text-neutral-400' : 'text-neutral-500'}`}>
                {games.length} Board Pairings Loaded
              </p>
            </div>
          </div>
        </div>

        {/* Header Right Actions */}
        <div className="flex items-center gap-3">
          {/* Search bar */}
          <div className="relative hidden sm:block">
            <Search className="w-3.5 h-3.5 absolute left-3 top-1/2 -translate-y-1/2 text-neutral-500" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Filter players or board..."
              className={`border rounded-lg pl-8 pr-3 py-1.5 text-xs font-mono w-48 sm:w-64 focus:outline-none focus:border-[#e05338] transition-colors ${
                isDark
                  ? 'bg-[#0b0c0f] border-white/[0.08] text-neutral-200 placeholder-neutral-500'
                  : 'bg-neutral-50 border-neutral-300 text-neutral-800 placeholder-neutral-400'
              }`}
            />
          </div>

          {/* Refresh button */}
          <button
            onClick={() => fetchRoundGames()}
            disabled={isRefreshing}
            className={`p-2 rounded-lg border transition-colors disabled:opacity-50 ${
              isDark
                ? 'bg-[#181c26] hover:bg-neutral-800 text-neutral-400 hover:text-white border-white/[0.08]'
                : 'bg-neutral-100 hover:bg-neutral-200 text-neutral-600 hover:text-neutral-900 border-neutral-200'
            }`}
            title="Refresh pairings"
          >
            <RotateCw className={`w-4 h-4 ${isRefreshing ? 'animate-spin text-[#e05338]' : ''}`} />
          </button>

          {/* Theme Toggle */}
          <ThemeToggle showLabel={false} />
        </div>
      </header>

      {/* 2. Scrollable Board Grid */}
      <main className="flex-1 min-h-0 overflow-y-auto p-4 lg:p-6">
        <div className="max-w-7xl mx-auto">
          {loading ? (
            <div className={`h-96 flex flex-col items-center justify-center gap-3 ${isDark ? 'text-neutral-400' : 'text-neutral-600'}`}>
              <RotateCw className="w-7 h-7 animate-spin text-[#e05338]" />
              <p className="text-sm font-mono">Loading tournament boards from Lichess relay...</p>
            </div>
          ) : error ? (
            <div className="h-96 flex flex-col items-center justify-center gap-3 text-center">
              <p className="text-[#e05338] text-sm font-semibold">{error}</p>
              <button
                onClick={() => fetchRoundGames()}
                className="px-4 py-2 bg-[#e05338] hover:bg-[#eb5e43] text-white font-bold rounded-lg text-xs transition-colors"
              >
                Try Again
              </button>
            </div>
          ) : filteredGames.length === 0 ? (
            <div className={`h-96 flex flex-col items-center justify-center gap-2 text-sm ${isDark ? 'text-neutral-500' : 'text-neutral-400'}`}>
              <Users className="w-8 h-8 opacity-40" />
              <p>No tournament pairings match your filter.</p>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
              {filteredGames.map((game, idx) => {
                const gameId = game.game_id || game.id || (game.board ? String(game.board) : '');
                const boardNum = game.board ?? idx + 1;
                const whiteName = game.white_name || game.white?.name || game.white?.username || 'White';
                const whiteTitle = game.white_title || game.white?.title;
                const whiteRating = game.white_elo || game.white?.rating;
                const whiteFed = game.white_fed || game.white_team || game.white?.federation;

                const blackName = game.black_name || game.black?.name || game.black?.username || 'Black';
                const blackTitle = game.black_title || game.black?.title;
                const blackRating = game.black_elo || game.black?.rating;
                const blackFed = game.black_fed || game.black_team || game.black?.federation;

                const isOngoing = !game.status || game.status === 'started' || game.status === 'live' || game.result === '*';
                const fen = game.current_fen || game.fen || 'start';
                const cardKey = game.game_id || game.id || `board-card-${boardNum}-${idx}`;

                return (
                  <div
                    key={cardKey}
                    onClick={() => onSelectGame(gameId)}
                    className={`group relative rounded-2xl p-4 transition-all duration-200 border cursor-pointer flex flex-col justify-between ${
                      isDark
                        ? 'bg-[#13151b] hover:bg-[#181c26] border-white/[0.08] hover:border-[#e05338]/50 shadow-lg'
                        : 'bg-white hover:bg-neutral-50 border-black/[0.08] hover:border-[#e05338]/50 shadow-sm'
                    }`}
                  >
                    {/* Top: Board number & Game Status */}
                    <div className="flex items-center justify-between mb-3">
                      <span
                        className={`text-xs font-mono font-bold px-2 py-0.5 rounded border ${
                          isDark
                            ? 'bg-[#0b0c0f] border-white/[0.06] text-neutral-300'
                            : 'bg-neutral-100 border-neutral-200 text-neutral-700'
                        }`}
                      >
                        BOARD {boardNum}
                      </span>

                      {isOngoing ? (
                        <span className="flex items-center gap-1.5 text-[11px] font-bold text-[#e05338] font-mono">
                          <span className="w-2 h-2 rounded-full bg-[#e05338] animate-pulse" />
                          LIVE
                        </span>
                      ) : (
                        <span
                          className={`flex items-center gap-1 text-[11px] font-mono font-semibold ${
                            isDark ? 'text-neutral-400' : 'text-neutral-500'
                          }`}
                        >
                          <CheckCircle2 className="w-3.5 h-3.5 text-neutral-500" />
                          {game.result && game.result !== '*' ? game.result : (game.status || 'Finished')}
                        </span>
                      )}
                    </div>

                    {/* Middle: Mini Chessboard Preview & Match Details */}
                    <div className="flex items-center gap-3 my-1">
                      {/* Mini Board thumbnail */}
                      <div
                        className={`w-24 h-24 shrink-0 rounded-lg overflow-hidden border pointer-events-none ${
                          isDark ? 'border-white/[0.08]' : 'border-neutral-200'
                        }`}
                      >
                        <Chessboard
                          position={fen}
                          boardWidth={96}
                          arePiecesDraggable={false}
                          customDarkSquareStyle={{ backgroundColor: '#7a6652' }}
                          customLightSquareStyle={{ backgroundColor: '#e2d7c0' }}
                        />
                      </div>

                      {/* Players & Ratings */}
                      <div className="flex-1 min-w-0 space-y-2">
                        {/* White Player */}
                        <div className="flex items-center justify-between text-xs">
                          <div className="flex items-center gap-1.5 truncate">
                            <span className="w-2.5 h-2.5 rounded-sm bg-neutral-100 border border-neutral-300 shrink-0" />
                            <CountryFlag countryCode={whiteFed} playerName={whiteName} />
                            {whiteTitle && (
                              <span className="bg-[#e05338]/15 text-[#e05338] text-[9px] font-bold px-1 rounded border border-[#e05338]/30">
                                {whiteTitle}
                              </span>
                            )}
                            <span
                              className={`font-semibold truncate ${
                                isDark ? 'text-neutral-200' : 'text-neutral-800'
                              }`}
                            >
                              {whiteName}
                            </span>
                          </div>
                          {whiteRating && (
                            <span
                              className={`text-[11px] font-mono shrink-0 ml-1 ${
                                isDark ? 'text-neutral-500' : 'text-neutral-400'
                              }`}
                            >
                              {whiteRating}
                            </span>
                          )}
                        </div>

                        {/* Black Player */}
                        <div className="flex items-center justify-between text-xs">
                          <div className="flex items-center gap-1.5 truncate">
                            <span className="w-2.5 h-2.5 rounded-sm bg-neutral-800 border border-neutral-600 shrink-0" />
                            <CountryFlag countryCode={blackFed} playerName={blackName} />
                            {blackTitle && (
                              <span className="bg-[#e05338]/15 text-[#e05338] text-[9px] font-bold px-1 rounded border border-[#e05338]/30">
                                {blackTitle}
                              </span>
                            )}
                            <span
                              className={`font-semibold truncate ${
                                isDark ? 'text-neutral-200' : 'text-neutral-800'
                              }`}
                            >
                              {blackName}
                            </span>
                          </div>
                          {blackRating && (
                            <span
                              className={`text-[11px] font-mono shrink-0 ml-1 ${
                                isDark ? 'text-neutral-500' : 'text-neutral-400'
                              }`}
                            >
                              {blackRating}
                            </span>
                          )}
                        </div>
                      </div>
                    </div>

                    {/* Bottom: Action CTA */}
                    <div
                      className={`mt-3 pt-2.5 border-t flex items-center justify-between ${
                        isDark ? 'border-white/[0.06]' : 'border-black/[0.06]'
                      }`}
                    >
                      <span className="text-[11px] font-mono text-neutral-500">
                        {game.lastMove ? `Last: ${game.lastMove}` : (game.ply_count ? `Move ${Math.floor((game.ply_count + 1) / 2)}` : 'Ready')}
                      </span>
                      <div className="flex items-center gap-1 text-xs font-bold text-[#e05338] group-hover:opacity-80 transition-opacity">
                        <Radio className="w-3.5 h-3.5 text-[#e05338]" />
                        <span>Tune In</span>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </main>

      {/* 3. Footer */}
      <footer
        className={`shrink-0 max-w-7xl mx-auto w-full py-2.5 px-4 text-center text-xs border-t flex items-center justify-between transition-colors duration-200 ${
          isDark ? 'border-white/[0.06] text-neutral-500' : 'border-black/[0.06] text-neutral-500'
        }`}
      >
        <span className="font-mono text-[11px]">Event Broadcast Engine Active</span>
        <div className="flex items-center gap-4 text-[11px]">
          <span>Auto-updates live</span>
        </div>
      </footer>
    </div>
  );
};