/**
 * useTokenProfile — Data hook for Token Profile page
 * ====================================================
 * Fetches from single context endpoint: /api/onchain/smart-money/token/:symbol/context
 */

import { useState, useEffect, useCallback } from 'react';

const API = process.env.REACT_APP_BACKEND_URL || '';

export interface ScoreComponents {
  wallet: number;
  timing: number;
  flow: number;
  cluster: number;
  pattern: number;
}

export interface TokenScoreDetail {
  token: string;
  alpha_score: number;
  signal: string;
  pattern: string | null;
  net_flow_usd: number;
  buy_flow_usd: number;
  sell_flow_usd: number;
  wallet_count: number;
  avg_timing: number;
  avg_edge: number;
  drivers: string[];
  components: ScoreComponents;
}

export interface TokenPattern {
  pattern_type: string;
  token: string;
  from_token?: string;
  to_token?: string;
  net_flow_usd: number;
  confidence: number;
  wallet_count: number;
  drivers: string[];
}

export interface TokenSignalDetail {
  signal_id: string;
  token: string;
  signal_type: string;
  conviction: number;
  drivers: string[];
  wallet_count: number;
  capital_usd: number;
  capital_fmt: string;
  brain_score: number;
}

export interface TokenRoute {
  route_type: string;
  source_entity: string;
  protocol: string;
  token: string;
  volume_usd: number;
  impact_score: number;
}

export interface TokenActor {
  wallet: string;
  name: string;
  smart_score: number;
  net_flow_usd: number;
  net_flow_fmt: string;
  trades: number;
  tokens: string[];
  last_activity: string;
}

export interface RelatedToken {
  token: string;
  alpha_score: number;
  signal: string;
  net_flow_usd: number;
}

export interface TokenFlow {
  net_flow_usd: number;
  share_pct: number;
}

export interface Narrative {
  narrative_type: string;
  bias: string;
  confidence: number;
  summary: string;
  drivers: string[];
}

export interface TokenProfileData {
  symbol: string;
  score: TokenScoreDetail | null;
  rank: number | null;
  totalTokens: number;
  patterns: TokenPattern[];
  signals: TokenSignalDetail[];
  routes: TokenRoute[];
  flow: TokenFlow;
  actors: TokenActor[];
  relatedTokens: RelatedToken[];
  narrative: Narrative | null;
  loading: boolean;
  error: string | null;
}

type WindowKey = '24h' | '7d' | '30d';

export function useTokenProfile(symbol: string, chainId: number, window: WindowKey): TokenProfileData & { refresh: () => void } {
  const [data, setData] = useState<TokenProfileData>({
    symbol,
    score: null,
    rank: null,
    totalTokens: 0,
    patterns: [],
    signals: [],
    routes: [],
    flow: { net_flow_usd: 0, share_pct: 0 },
    actors: [],
    relatedTokens: [],
    narrative: null,
    loading: true,
    error: null,
  });

  const load = useCallback(async () => {
    if (!symbol) return;
    setData(prev => ({ ...prev, loading: true, error: null }));
    try {
      const res = await fetch(`${API}/api/onchain/smart-money/token/${encodeURIComponent(symbol)}/context?chainId=${chainId}&window=${window}`);
      const json = await res.json();
      if (!json.ok) throw new Error(json.error || 'Failed to load token data');

      setData({
        symbol: json.symbol || symbol,
        score: json.score || null,
        rank: json.rank || null,
        totalTokens: json.total_tokens || 0,
        patterns: json.patterns || [],
        signals: json.signals || [],
        routes: json.routes || [],
        flow: json.flow || { net_flow_usd: 0, share_pct: 0 },
        actors: json.actors || [],
        relatedTokens: json.related_tokens || [],
        narrative: json.narrative || null,
        loading: false,
        error: null,
      });
    } catch (e: any) {
      setData(prev => ({ ...prev, loading: false, error: e?.message || 'Failed to load' }));
    }
  }, [symbol, chainId, window]);

  useEffect(() => { load(); }, [load]);

  return { ...data, refresh: load };
}
