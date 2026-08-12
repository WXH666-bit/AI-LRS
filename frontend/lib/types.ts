// 与后端契约对应的类型定义

export interface GameEvent {
  seq: number;
  type: string;
  actor_seat: number | null;
  day: number;
  night: number;
  phase: string;
  payload: Record<string, any>;
}

export interface AIStreamUpdate {
  stream_id: string;
  actor_seat: number;
  window_kind: string | null;
  text: string;
  status: "chunk" | "retry" | "complete" | "fallback";
}

export interface PlayerInfo {
  seat: number;
  name: string;
  controller_type: "human" | "ai" | "trustee" | "empty";
  user_id: number | null;
  alive: boolean;
  ready: boolean;
  is_host: boolean;
  role: string | null;
  persona_name?: string | null;
  model_config_id?: number | null;
}

export interface MeInfo {
  seat: number;
  controller_type: string;
  role: string | null;
  alive: boolean;
  is_host: boolean;
}

export interface RoleSetupItem {
  role: string;
  label: string;
  count: number;
}

export interface GameInfo {
  game_id: number;
  board_size: number;
  role_setup: RoleSetupItem[];
  status: "lobby" | "running" | "paused" | "ended";
  phase: string;
  phase_label: string;
  window_kind: string | null;
  window_label: string;
  night: number;
  day: number;
  sheriff_seat: number | null;
  winner: string | null;
  end_reason: string | null;
  speed: number;
  acting_seats: number[];
  deadline: number;
  election_stage: string | null;
  night_step: string | null;
  is_all_ai: boolean;
}

export interface LegalAction {
  type: string;
  label: string;
  action?: string;
  skill?: string;
}

export interface LegalTarget {
  seat: number;
  label: string;
  kind?: string;
}

export interface GameView {
  game: GameInfo;
  players: PlayerInfo[];
  me: MeInfo | null;
  legal_actions: LegalAction[];
  legal_targets: LegalTarget[];
  private: Record<string, any>;
  roles_revealed?: Record<number, string> | null;
}

export interface GameSummary {
  game: {
    id: number;
    board_size: number;
    status: string;
    phase: string;
    winner: string | null;
    end_reason: string | null;
    created_at: string | null;
    ended_at: string | null;
    is_host: boolean;
  } | null;
  players: PlayerInfo[];
  me: {
    seat: number;
    controller_type: string;
    ready: boolean;
    is_host: boolean;
    role?: string | null;
  } | null;
}

export interface ModelConfig {
  id: number;
  display_name: string;
  protocol: "openai_compatible" | "anthropic_messages";
  base_url: string;
  model_name: string;
  temperature: number;
  max_output_tokens: number;
  timeout_seconds: number;
  enabled: boolean;
  is_default_fallback: boolean;
  has_api_key: boolean;
}

export interface Persona {
  id: number;
  name: string;
  speaking_style: string;
  risk_preference: string;
  reasoning_style: string;
  aggression: number;
  description: string;
}
