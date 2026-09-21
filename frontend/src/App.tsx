import React, { useState } from 'react';
import { ThemeProvider, useTheme } from './context/ThemeContext';
import { LandingView } from './views/LandingView';
import { StudioView } from './views/StudioView';
import { EventRoundView } from './views/EventRoundView';

interface BroadcastConfig {
  gameId?: string;
  roundId?: string;
  enableTts: boolean;
  replayAll: boolean;
}

type ViewState =
  | { type: 'landing' }
  | { type: 'event'; roundId: string; enableTts: boolean; replayAll: boolean }
  | { type: 'studio'; gameId: string; roundId?: string; enableTts: boolean; replayAll: boolean };

const AppContent: React.FC = () => {
  const [viewState, setViewState] = useState<ViewState>({ type: 'landing' });
  const { isDark } = useTheme();

  // Handle entry from LandingView
  const handleStartBroadcast = (config: BroadcastConfig) => {
    // If a roundId is provided without a specific gameId, route to the Event Round Page
    if (config.roundId && !config.gameId) {
      setViewState({
        type: 'event',
        roundId: config.roundId,
        enableTts: config.enableTts,
        replayAll: config.replayAll,
      });
    } else if (config.gameId) {
      setViewState({
        type: 'studio',
        gameId: config.gameId,
        roundId: config.roundId,
        enableTts: config.enableTts,
        replayAll: config.replayAll,
      });
    }
  };

  // From EventRoundView -> select a game to watch in Studio
  const handleSelectGameFromRound = (gameId: string) => {
    if (viewState.type === 'event') {
      setViewState({
        type: 'studio',
        gameId,
        roundId: viewState.roundId,
        enableTts: viewState.enableTts,
        replayAll: viewState.replayAll,
      });
    }
  };

  // Exit Studio: If we arrived from an event round, go back to EventRoundView; otherwise back to Landing
  const handleExitStudio = () => {
    if (viewState.type === 'studio' && viewState.roundId) {
      setViewState({
        type: 'event',
        roundId: viewState.roundId,
        enableTts: viewState.enableTts,
        replayAll: viewState.replayAll,
      });
    } else {
      setViewState({ type: 'landing' });
    }
  };

  return (
    <div
      className={`w-full h-screen h-[100dvh] max-h-screen flex flex-col overflow-hidden transition-colors duration-200 ${
        isDark ? 'bg-[#0b0c0f] text-neutral-100' : 'bg-[#f5f6f9] text-neutral-900'
      }`}
    >
      {viewState.type === 'landing' && (
        <LandingView onStartBroadcast={handleStartBroadcast} />
      )}

      {viewState.type === 'event' && (
        <EventRoundView
          roundId={viewState.roundId}
          onSelectGame={handleSelectGameFromRound}
          onBack={() => setViewState({ type: 'landing' })}
        />
      )}

      {viewState.type === 'studio' && (
        <StudioView
          gameId={viewState.gameId}
          roundId={viewState.roundId}
          initialEnableTts={viewState.enableTts}
          replayAll={viewState.replayAll}
          onExit={handleExitStudio}
        />
      )}
    </div>
  );
};

export const App: React.FC = () => {
  return (
    <ThemeProvider>
      <AppContent />
    </ThemeProvider>
  );
};

export default App;