export type BroadcastEventType =
  | 'METADATA'
  | 'MOVE'
  | 'TERMINATION'
  | 'AUDIO_INTERRUPT'
  | 'ERROR';

export type CommentatorRole = 'HOST' | 'ANALYST';

export type CommentaryEmotion =
  | 'neutral'
  | 'excited'
  | 'shocked'
  | 'analytical'
  | 'tense'
  | 'humorous';

export type MoveClassification =
  | 'BOOK'
  | 'BEST'
  | 'EXCELLENT'
  | 'GOOD'
  | 'INACCURACY'
  | 'MISTAKE'
  | 'BLUNDER'
  | 'BRILLIANT';

export interface PlayerInfo {
  username: string;
  rating?: number | null;
  title?: string | null;
}

export interface GameMetadata {
  game_id: string;
  speed: string;
  variant: string;
  rated: boolean;
  white_player: PlayerInfo;
  black_player: PlayerInfo;
  event_name?: string | null;
}

export interface ParsedMoveEvent {
  ply: number;
  turn: 'white' | 'black';
  uci: string;
  san: string;
  fen: string;
  move_time_spent_seconds: number;
  white_clock_seconds?: number | null;
  black_clock_seconds?: number | null;
  is_check: boolean;
  is_checkmate: boolean;
  is_stalemate: boolean;
  is_draw: boolean;
  is_time_trouble: boolean;
  termination_reason?: string | null;
  acting_player?: string | null;
}

export interface VisualCue {
  arrows: [string, string, string][]; // [from, to, color]
  highlights: string[];               // [square]
}

export interface EngineLine {
  rank: number;
  score_cp?: number | null;
  mate_in?: number | null;
  win_probability: number;
  uci_moves: string[];
  san_moves: string[];
  depth: number;
  primary_move_uci?: string;
  primary_move_san?: string;
}

export interface BlunderDossier {
  is_natural_trap: boolean;
  motivation_explanation: string;
  refutation_explanation: string;
  punishment_moves_san: string[];
  missed_best_san?: string | null;
}

export interface MoveEvaluation {
  ply: number;
  turn: 'white' | 'black';
  played_san: string;
  played_uci: string;
  fen_after: string;
  is_book: boolean;
  left_book_now: boolean;
  opening_name?: string | null;
  eval_cp_after?: number | null;
  mate_in_after?: number | null;
  eval_swing_cp: number;
  win_prob_after: number;
  classification: MoveClassification;
  is_blunder: boolean;
  blunder_dossier?: BlunderDossier | null;
  should_have_played?: EngineLine | null;
  candidate_responses: EngineLine[];
  visual_cues: VisualCue;
}

export interface DialogueTurn {
  speaker: CommentatorRole;
  text: string;
  emotion: CommentaryEmotion;
  priority: number;
  estimated_duration_seconds?: number | null;
  audio_url?: string | null;
}

export interface CommentaryExchange {
  ply: number;
  move_san: string;
  turn_color: 'white' | 'black';
  dynamic: 'SOLO_HOST' | 'SOLO_ANALYST' | 'BANTER' | 'SILENCE';
  priority: number;
  turns: DialogueTurn[];
  is_interrupt: boolean;
}

export interface BroadcastFrame {
  event_type: BroadcastEventType;
  game_id: string;
  round_id?: string | null;
  ply?: number | null;
  fen?: string | null;
  turn?: 'white' | 'black' | null;
  metadata?: GameMetadata | null;
  move?: ParsedMoveEvent | null;
  evaluation?: MoveEvaluation | null;
  commentary?: CommentaryExchange | null;
  visual_cues?: VisualCue | null;
  termination_reason?: string | null;
  error?: string | null;
  timestamp: number;
}

export interface BroadcastPlayerSummary {
  name?: string;
  username?: string;
  title?: string;
  rating?: number;
  federation?: string;
}

export interface BroadcastGameSummary {
  id: string; // Game ID to launch studio
  board?: number;
  white: BroadcastPlayerSummary;
  black: BroadcastPlayerSummary;
  fen?: string;
  status?: string; // 'started' | 'mate' | 'draw' | 'resign' | 'outoftime' | etc.
  winner?: 'white' | 'black' | null;
  lastMove?: string;
  round?: number | string;
}