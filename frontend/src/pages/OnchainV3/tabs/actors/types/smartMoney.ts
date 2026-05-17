export type WindowKey = '24h' | '7d' | '30d';
export type RadarSortKey = 'confidence' | 'net_flow' | 'recency' | 'impact';
export type FeedFilter = 'all' | 'accumulation' | 'distribution' | 'rotation' | 'momentum';
export type ConvictionTier = 'all' | 'high' | 'medium' | 'low';

export interface ActorItem {
  entityId: string;
  entityName: string | null;
  entityType: string;
  tags: string[];
  attributionSource: string | null;
  attributionConfidence: number | null;
  netUsd: number;
  dexUsd: number;
  cexUsd: number;
  bridgeUsd: number;
  trades: number;
  pricedShare: number;
}

export interface ActorsResponse {
  ok: boolean;
  direction: string;
  window: string;
  items: ActorItem[];
}

export interface RadarEvent {
  event_type: 'early_accumulation' | 'early_distribution' | 'smart_wallet_detected' | 'cluster_activity';
  signal_class: 'wallet' | 'market' | 'cluster';
  wallet: string;
  entity: string;
  entity_type: string;
  token: string;
  net_flow_usd: number;
  confidence: number;
  timing_score: number;
  impact_score: number;
  signal_severity: 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';
  last_activity: string;
  reason: string[];
  trades: number;
  cluster_wallets?: number | null;
  wallet_addresses?: string[];
}

export interface BrainSignal {
  token: string;
  alpha_score: number;
  signal: 'strong_bullish' | 'bullish' | 'neutral' | 'bearish' | 'strong_bearish';
  pattern: string | null;
  net_flow_usd: number;
  buy_flow_usd: number;
  sell_flow_usd: number;
  wallet_count: number;
  avg_timing: number;
  avg_edge: number;
  drivers: string[];
  components: { wallet: number; timing: number; flow: number; cluster: number; pattern: number };
  wallet_addresses?: string[];
}

export interface PatternEvent {
  pattern_type: 'accumulation' | 'distribution' | 'rotation' | 'exit';
  token: string;
  from_token?: string;
  to_token?: string;
  net_flow_usd: number;
  confidence: number;
  wallet_count: number;
  buy_ratio: number;
  avg_timing: number;
  drivers: string[];
  wallet_addresses?: string[];
}

export interface MapRoute {
  route_type: string;
  source_entity: string;
  source_type: string;
  source_wallet: string;
  protocol: string;
  token: string;
  from_token?: string;
  to_token?: string;
  volume_usd: number;
  net_flow_usd: number;
  impact_score: number;
  confidence: number;
  wallet_addresses?: string[];
}

export interface MapData {
  routes: MapRoute[];
  destination_heat: Array<{ token: string; net_flow_usd: number }>;
  source_heat: Array<{ name: string; type: string; total_flow_usd: number }>;
  flow_summary: Record<string, number>;
}

export interface NarrativeData {
  narrative_type: string;
  bias: 'bullish' | 'bearish' | 'neutral';
  confidence: number;
  summary: string;
  drivers: string[];
  key_token: string | null;
  net_flow_usd: number;
}

export interface SmartActor {
  wallet: string;
  name: string;
  smart_score: number;
  activity_score: number;
  net_flow_usd: number;
  net_flow_fmt: string;
  trades: number;
  token_count: number;
  tokens: string[];
  edge_score: number;
  timing_score: number;
  last_activity: string;
  wallet_addresses?: string[];
}

export interface AlphaSignal {
  signal_id: string;
  token: string;
  signal_type: string;
  conviction: number;
  drivers: string[];
  wallet_count: number;
  capital_usd: number;
  capital_fmt: string;
  brain_score: number;
  pattern_confidence: number;
  from_token?: string;
  to_token?: string;
  wallet_addresses?: string[];
}

export interface Playbook {
  playbook_id: string;
  label: string;
  token: string;
  signal_type: string;
  conviction: number;
  capital_usd: number;
  capital_fmt: string;
  wallet_count: number;
  drivers: string[];
  wallets: Array<{ name: string; strategy: string; confidence: number; address?: string }>;
  from_token?: string;
  to_token?: string;
  wallet_addresses?: string[];
}
