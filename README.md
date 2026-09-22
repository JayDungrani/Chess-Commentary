# Grandmaster AI: Real-Time Chess Broadcast & Commentary Studio

A production-grade, real-time chess broadcasting studio and interactive commentary platform. Powered by **Stockfish 17**, **Google Gemini**, **ElevenLabs Voice AI**, **FastAPI**, and **React**, this application delivers dynamic dual-commentator broadcast coverage for live Lichess games, broadcast tournaments, and custom PGN/FEN matches.

---

## Architecture Overview

```
                        ┌────────────────────────────────────────┐
                        │            Lichess API                 │
                        │  (Broadcast Relays & Live Casual Games)│
                        └───────────────────┬────────────────────┘
                                            │ ND-JSON / SSE Stream
                                            ▼
                        ┌────────────────────────────────────────┐
                        │        FastAPI Backend Engine          │
                        ├────────────────────────────────────────┤
                        │ • PacedMoveStreamer (Pacing Buffer)    │
                        │ • Stockfish Pool (Depth 14, Multi-PV)  │
                        │ • BroadcastDirector (Dynamic Pacing)   │
                        │ • Gemini LLM Commentary Agent          │
                        │ • ElevenLabs TTS Audio Engine          │
                        └───────────────────┬────────────────────┘
                                            │ Server-Sent Events (SSE)
                                            ▼
                        ┌────────────────────────────────────────┐
                        │         React + Vite Frontend          │
                        ├────────────────────────────────────────┤
                        │ • Grand Chessboard & Live Eval Bar     │
                        │ • Dual Commentator Desk & Audio Queue  │
                        │ • Interactive Eval Timeline Chart      │
                        │ • Tactile Web Audio Sound Synthesizer  │
                        │ • Drag-and-Drop Hypothetical Sandbox   │
                        └────────────────────────────────────────┘
```

---

## Core Features

### 1. Dual-Commentator Broadcasting Desk
- **James (Host)**: High-energy color commentator focusing on narrative tension, player time management, game stakes, and punchy move calls.
- **Peter (Analyst)**: Grandmaster-level technical analyst breaking down tactical complications, engine evaluation shifts, opening theory, and blunder refutations.
- **Adaptive Dynamics**: The Director intelligently switches between `SOLO_HOST`, `SOLO_ANALYST`, `BANTER` (two-host discussion), `PLAY_BY_PLAY`, and `SILENCE` based on move tempo and match tension.
- **Zero-Latency Play-by-Play**: Instant rapid moves (0.1s - 1.5s) trigger direct natural spoken calls (e.g. *"Knight to f6."*, *"Takes on d4."*) with 0ms LLM latency.
- **Smart Audio Queue & Interrupts**: Blunders and brilliancies immediately cut off stale background audio to spotlight game-changing swings. Play-by-play calls maintain smooth momentum without dead air.

### 2. High-Performance Chess Engine Analysis
- **Stockfish 17+ Integration**: Multi-PV evaluation calculating centipawn evaluations, mate sequences, win probability curves, and tactical threat arrows.
- **Blunder Dossier**: Detects inaccuracies, mistakes, and blunders with tactical punishment continuations and alternative recommendations.
- **Heuristic Fallback Engine**: If a Stockfish binary is not installed, the engine gracefully falls back to static material and mobility heuristics without crashing the server.
- **Full-Game Instant Pre-Analysis**: Uploaded PGN files and FEN positions are evaluated upfront in under one second, populating the full eval graph and turning-point markers instantly.

### 3. Live Broadcast Synchronization
- **Live Sync Catchup**: Jumping into an ongoing match immediately evaluates all historical moves with Stockfish (populating the eval graph and eval bar) while starting commentary and audio synthesis directly on the active live move.
- **Pacing Buffer**: Dynamically respects player clock think time across Bullet, Blitz, Rapid, and Classical formats.
- **Official Lichess Broadcast Relays**: Browse tournament round pairings, player ratings, country flags, and live game states with automatic reconnection.

### 4. Interactive Studio Frontend
- **Grand Chessboard Layout**: Spacious 1080p desktop presentation with real-time responsive eval bar, move indicators, and tactical arrows.
- **Interactive Eval Timeline**: Proportional 1:1 SVG advantage curve with hover tooltips and click-to-jump move scrubbing.
- **Hypothetical Sandbox**: Drag and drop pieces on any move to explore alternative variations with live Stockfish analysis and zero LLM distraction.
- **Tactile Web Audio Effects**: Pure Web Audio API sound synthesis providing organic acoustic wooden taps, captures, checks, and castles with zero external MP3 assets.
- **Dark & Light Mode**: Seamless theme switching with high-contrast board aesthetics and ambient geometric background telemetry.

---

## Repository Structure

```
Chess-Commentary/
├── backend/
│   ├── app/
│   │   ├── api/                 # API route handlers (broadcast, custom games)
│   │   ├── commentary/          # LLM agents, prompt engineering, director logic
│   │   ├── engine/              # Stockfish process pool, heuristics, opening book
│   │   ├── lichess/             # Lichess stream client, NDJSON parser, pacing buffer
│   │   ├── services/            # Broadcast session manager, ElevenLabs TTS service
│   │   ├── config.py            # Pydantic Settings and environment configuration
│   │   └── main.py              # FastAPI application entrypoint & lifespan
│   ├── assets/books/            # Opening books (gm2001.bin Polyglot book)
│   ├── tests/                   # Pytest suite and commentary pacing verification
│   └── Dockerfile               # Production container definition for Python backend
├── frontend/
│   ├── src/
│   │   ├── components/          # Chessboard, eval bar, timeline, commentary desk
│   │   ├── hooks/               # useBroadcastStream (SSE management & state)
│   │   ├── types/               # TypeScript interfaces for broadcast & commentary
│   │   ├── utils/               # Audio queue, Web Audio synthesizer, PGN helpers
│   │   └── views/               # LandingView, StudioView, EventRoundView
│   ├── nginx.conf               # Reverse proxy config with SSE streaming support
│   └── Dockerfile               # Multi-stage production build (Node.js + Nginx)
├── docker-compose.yml           # Unified orchestration for backend and frontend
├── .dockerignore                # Build context optimizations
├── .env.example                 # Template for environment variables
└── pyproject.toml               # Python dependencies and uv build configuration
```

---

## Getting Started

### Option A: Running with Docker (Recommended)

Docker Compose builds and starts both the FastAPI backend (with Stockfish pre-installed) and the React frontend with an Nginx reverse proxy.

1. **Clone the repository**:
   ```bash
   git clone https://github.com/JayDungrani/Chess-Commentary.git
   cd Chess-Commentary
   ```

2. **Configure environment variables**:
   ```bash
   cp .env.example .env
   ```
   Open `.env` and configure your API keys:
   ```env
   # Required for AI Commentary Generation
   GEMINI_API_KEY=your_google_gemini_api_key

   # Optional for Spoken Audio Commentary Playback
   ELEVENLABS_API_KEY=your_elevenlabs_api_key
   ELEVENLABS_HOST_VOICE_ID=your_host_voice_id
   ELEVENLABS_ANALYST_VOICE_ID=your_analyst_voice_id

   # Optional to increase Lichess rate limits
   LICHESS_API_TOKEN=your_lichess_token
   ```

3. **Launch the studio**:
   ```bash
   docker compose up --build
   ```

4. **Access the application**:
   - **Studio Web Interface**: [http://localhost:3000](http://localhost:3000)
   - **Backend API Docs (Swagger)**: [http://localhost:8000/docs](http://localhost:8000/docs)
   - **API Health Check**: [http://localhost:3000/api/health](http://localhost:3000/api/health) or [http://localhost:8000/health](http://localhost:8000/health)

---

### Option B: Local Development Setup

#### Prerequisites
- **Python**: 3.12 or newer (with [`uv`](https://github.com/astral-sh/uv) recommended)
- **Node.js**: 20.x or 22.x with `npm`
- **Stockfish**: Stockfish 16+ binary installed on your system

#### 1. Backend Setup

```bash
# Navigate to project root
cd Chess-Commentary

# Create virtual environment and install dependencies using uv
uv sync

# Copy environment template and fill in keys
cp .env.example .env

# Set STOCKFISH_PATH in your .env if not on system PATH:
# STOCKFISH_PATH=/path/to/stockfish

# Start the FastAPI server
uv run uvicorn app.main:app --app-dir backend --host 0.0.0.0 --port 8000 --reload
```

The backend will start at `http://localhost:8000`.

#### 2. Frontend Setup

```bash
# Navigate to frontend folder
cd frontend

# Install Node dependencies
npm install

# Start Vite development server
npm run dev
```

The frontend will start at `http://localhost:3000` with hot module reloading and API proxying configured to `http://localhost:8000`.

---

## Environment Variables Reference

| Variable | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `GEMINI_API_KEY` | String | *None* | Google Gemini API key for commentary generation |
| `GEMINI_MODEL` | String | `gemini-2.5-flash` | Gemini model variant for structured commentary |
| `ELEVENLABS_API_KEY` | String | *None* | ElevenLabs API key for dual-voice TTS synthesis |
| `ELEVENLABS_HOST_VOICE_ID` | String | *None* | Voice ID for James (Host) |
| `ELEVENLABS_ANALYST_VOICE_ID` | String | *None* | Voice ID for Peter (Analyst) |
| `STOCKFISH_PATH` | String | Auto-detected | Absolute path to Stockfish executable |
| `STOCKFISH_DEPTH` | Integer | `14` | Search depth for real-time move analysis |
| `STOCKFISH_MULTIPV` | Integer | `3` | Number of candidate lines to evaluate |
| `LICHESS_API_TOKEN` | String | *None* | Optional personal access token for Lichess API |
| `HOST` | String | `0.0.0.0` | Backend bind host |
| `PORT` | Integer | `8000` | Backend bind port |
| `BACKEND_PORT` | Integer | `8000` | Host port exposed by Docker Compose for backend |
| `FRONTEND_PORT` | Integer | `3000` | Host port exposed by Docker Compose for frontend |

---

## API Endpoints

### Live Broadcast & Match Streaming
- `GET /api/stream/game/{game_id}`: Stream real-time moves, evaluations, and commentary for a live Lichess casual game via Server-Sent Events (SSE).
- `GET /api/broadcast/{round_id}/{game_id}`: Stream live broadcast tournament match frames via SSE.
- `GET /api/broadcast/{round_id}/games`: Retrieve list of active games, players, and scores for a tournament round.

### Custom PGN & FEN Analysis
- `POST /api/custom/game`: Register and instantly pre-analyze a custom PGN match or FEN position with Stockfish.
- `GET /api/custom/game/{game_id}`: Retrieve cached full-game move snapshots and evaluations.
- `GET /api/broadcast/custom/stream/{game_id}`: Stream custom game moves with configurable pacing delay and commentary.

### Engine & System Utilities
- `GET /api/engine/analyze?fen={fen}&depth={depth}`: On-demand position evaluation and candidate variations.
- `GET /health` and `GET /api/health`: Health check endpoint reporting service availability.

---

## Running Tests

Run the complete backend test suite:

```bash
# Run all pacing, commentary, and director tests
python backend/tests/test_pacing_and_commentary.py

# Run studio enhancement unit tests
pytest backend/tests/test_studio_enhancements.py -v

# Run full test suite with pytest
pytest backend/tests/ -v
```

To run frontend TypeScript and production build checks:

```bash
cd frontend
npm run build
```

---

## Contributing

Contributions are welcome! Please follow these guidelines:
1. Fork the repository and create a feature branch (`git checkout -b feature/amazing-feature`).
2. Ensure all tests pass (`pytest backend/tests/` and `npm run build`).
3. Commit your changes (`git commit -m 'Add amazing feature'`).
4. Push to the branch (`git push origin feature/amazing-feature`).
5. Open a Pull Request.

---

## License

Distributed under the MIT License. See `LICENSE` for details.
