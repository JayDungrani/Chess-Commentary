// src/views/EventRoundView.tsx

import React, { useEffect, useState, useMemo } from 'react';
import {
  Trophy,
  ArrowLeft,
  RotateCw,
  Search,
  Radio,
  ExternalLink,
  Users,
  CheckCircle2,
  Clock,
} from 'lucide-react';
import { Chessboard } from 'react-chessboard';
import type { BroadcastGameSummary } from '../types/broadcast';
import { CountryFlag } from '../components/common/CountryFlag';

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
    <div className="h-screen h-[100dvh] max-h-screen w-full bg-[#0a0c10] text-stone-100 flex flex-col justify-between overflow-hidden select-none">
      {/* 1. Header Bar */}
      <header className="shrink-0 bg-[#10131a] border-b border-stone-800/90 px-4 py-3 flex items-center justify-between shadow-lg z-30">
        <div className="flex items-center gap-3">
          <button
            onClick={onBack}
            className="p-1.5 rounded-lg bg-[#181c26] hover:bg-stone-800 text-stone-400 hover:text-stone-100 border border-stone-800 transition-colors"
            title="Back to Home"
          >
            <ArrowLeft className="w-4 h-4" />
          </button>

          <div className="flex items-center gap-2.5">
            <div className="p-2 rounded-xl bg-amber-500/10 border border-amber-500/30 text-amber-400">
              <Trophy className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h1 className="font-bold text-base text-stone-100 tracking-tight">
                  Tournament Round Broadcast
                </h1>
                <span className="text-[10px] font-mono font-bold bg-[#181c26] text-amber-300 px-2 py-0.5 rounded border border-stone-700">
                  ROUND {roundId.slice(0, 8)}
                </span>
              </div>
              <p className="text-[11px] text-stone-400 font-mono">
                {games.length} Board Pairings Loaded
              </p>
            </div>
          </div>
        </div>

        {/* Header Right Actions */}
        <div className="flex items-center gap-3">
          {/* Search bar */}
          <div className="relative hidden sm:block">
            <Search className="w-3.5 h-3.5 absolute left-3 top-1/2 -translate-y-1/2 text-stone-500" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Filter players or board..."
              className="bg-[#181c26] border border-stone-800 rounded-lg pl-8 pr-3 py-1.5 text-xs text-stone-200 placeholder-stone-600 focus:outline-none focus:border-amber-400/80 font-mono w-48 sm:w-64"
            />
          </div>

          {/* Refresh Button */}
          <button
            onClick={() => fetchRoundGames(false)}
            disabled={isRefreshing}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-[#181c26] hover:bg-stone-800 text-stone-300 border border-stone-800 text-xs font-semibold transition-all disabled:opacity-50"
            title="Refresh round boards"
          >
            <RotateCw className={`w-3.5 h-3.5 ${isRefreshing ? 'animate-spin text-amber-400' : ''}`} />
            <span className="hidden md:inline">Refresh</span>
          </button>
        </div>
      </header>

      {/* 2. Scrollable Board Grid */}
      <main className="flex-1 min-h-0 overflow-y-auto p-4 lg:p-6">
        <div className="max-w-7xl mx-auto">
          {loading ? (
            <div className="h-96 flex flex-col items-center justify-center gap-3 text-stone-400">
              <RotateCw className="w-7 h-7 animate-spin text-amber-400" />
              <p className="text-sm font-mono">Loading tournament boards from Lichess relay...</p>
            </div>
          ) : error ? (
            <div className="h-96 flex flex-col items-center justify-center gap-3 text-center">
              <p className="text-rose-400 text-sm font-semibold">{error}</p>
              <button
                onClick={() => fetchRoundGames()}
                className="px-4 py-2 bg-amber-500 text-stone-950 font-bold rounded-lg text-xs"
              >
                Try Again
              </button>
            </div>
          ) : filteredGames.length === 0 ? (
            <div className="h-96 flex flex-col items-center justify-center gap-2 text-stone-500 text-sm">
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
                    className="group relative bg-[#12151d] hover:bg-[#161a24] border border-stone-800 hover:border-amber-500/50 rounded-2xl p-4 transition-all duration-200 shadow-lg cursor-pointer flex flex-col justify-between"
                  >
                    {/* Top: Board number & Game Status */}
                    <div className="flex items-center justify-between mb-3">
                      <span className="text-xs font-mono font-bold px-2 py-0.5 rounded bg-stone-900 border border-stone-800 text-stone-300">
                        BOARD {boardNum}
                      </span>

                      {isOngoing ? (
                        <span className="flex items-center gap-1.5 text-[11px] font-bold text-rose-400 font-mono">
                          <span className="w-2 h-2 rounded-full bg-rose-500 animate-pulse" />
                          LIVE
                        </span>
                      ) : (
                        <span className="flex items-center gap-1 text-[11px] font-mono text-stone-400 font-semibold">
                          <CheckCircle2 className="w-3.5 h-3.5 text-stone-500" />
                          {game.result && game.result !== '*' ? game.result : (game.status || 'Finished')}
                        </span>
                      )}
                    </div>

                    {/* Middle: Mini Chessboard Preview & Match Details */}
                    <div className="flex items-center gap-3 my-1">
                      {/* Mini Board thumbnail */}
                      <div className="w-24 h-24 shrink-0 rounded-lg overflow-hidden border border-stone-800/80 pointer-events-none">
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
                            <span className="w-2.5 h-2.5 rounded-sm bg-stone-200 border border-stone-400 shrink-0" />
                            <CountryFlag countryCode={whiteFed} playerName={whiteName} />
                            {whiteTitle && (
                              <span className="bg-amber-500/15 text-amber-300 text-[9px] font-bold px-1 rounded border border-amber-500/30">
                                {whiteTitle}
                              </span>
                            )}
                            <span className="font-semibold text-stone-200 truncate">
                              {whiteName}
                            </span>
                          </div>
                          {whiteRating && (
                            <span className="text-[11px] font-mono text-stone-400 shrink-0 ml-1">
                              {whiteRating}
                            </span>
                          )}
                        </div>

                        {/* Black Player */}
                        <div className="flex items-center justify-between text-xs">
                          <div className="flex items-center gap-1.5 truncate">
                            <span className="w-2.5 h-2.5 rounded-sm bg-stone-800 border border-stone-600 shrink-0" />
                            <CountryFlag countryCode={blackFed} playerName={blackName} />
                            {blackTitle && (
                              <span className="bg-amber-500/15 text-amber-300 text-[9px] font-bold px-1 rounded border border-amber-500/30">
                                {blackTitle}
                              </span>
                            )}
                            <span className="font-semibold text-stone-200 truncate">
                              {blackName}
                            </span>
                          </div>
                          {blackRating && (
                            <span className="text-[11px] font-mono text-stone-400 shrink-0 ml-1">
                              {blackRating}
                            </span>
                          )}
                        </div>
                      </div>
                    </div>

                    {/* Bottom: Action CTA */}
                    <div className="mt-3 pt-2.5 border-t border-stone-800/80 flex items-center justify-between">
                      <span className="text-[11px] font-mono text-stone-500">
                        {game.lastMove ? `Last: ${game.lastMove}` : (game.ply_count ? `Move ${Math.floor((game.ply_count + 1) / 2)}` : 'Ready')}
                      </span>
                      <div className="flex items-center gap-1 text-xs font-bold text-amber-400 group-hover:text-amber-300 transition-colors">
                        <Radio className="w-3.5 h-3.5" />
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
      <footer className="shrink-0 max-w-7xl mx-auto w-full py-2.5 px-4 text-center text-xs text-stone-500 border-t border-stone-800/80 flex items-center justify-between">
        <span className="font-mono text-[11px]">Event Broadcast Engine Active</span>
        <div className="flex items-center gap-4 text-stone-500 text-[11px]">
          <span>Auto-updates live</span>
        </div>
      </footer>
    </div>
  );
};