/**
 * useTokenIntelligence — Data hook for Token Intelligence page
 * ==============================================================
 * REFACTORED: Single API call to /api/onchain/smart-money/intelligence-context
 * Replaces 6 parallel calls (narrative, brain, feed, patterns, map, top-actors)
 */

import { useState, useEffect, useCallback } from 'react';

const API = process.env.REACT_APP_BACKEND_URL || '';

export interface TokenScore {
  token: string;
  alpha_score: number;
  signal: string;
  pattern: string;
  net_flow_usd: number;
  buy_flow_usd: number;
  sell_flow_usd: number;
  wallet_count: number;
  avg_timing: number;
  drivers: string[];
  wallet_addresses?: string[];
  components: {
    wallet: number;
    timing: number;
    flow: number;
    cluster: number;
    pattern: number;
  };
}

export interface TokenSignal {
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

export interface RotationPattern {
  pattern_type: string;
  token: string;
  from_token?: string;
  to_token?: string;
  net_flow_usd: number;
  confidence: number;
  wallet_count: number;
  drivers: string[];
}

export interface CapitalRoute {
  route_type: string;
  source_entity: string;
  protocol: string;
  token: string;
  from_token?: string;
  to_token?: string;
  volume_usd: number;
  impact_score: number;
}

export interface SmartActor {
  wallet: string;
  name: string;
  smart_score: number;
  net_flow_usd: number;
  net_flow_fmt: string;
  trades: number;
  tokens: string[];
  last_activity: string;
}

export interface Narrative {
  narrative_type: string;
  bias: string;
  confidence: number;
  summary: string;
  drivers: string[];
  key_token: string;
  net_flow_usd: number;
}

export interface DestinationHeat {
  token: string;
  net_flow_usd: number;
}

interface TokenIntelligenceData {
  narrative: Narrative | null;
  tokenScores: TokenScore[];
  signals: TokenSignal[];
  patterns: RotationPattern[];
  routes: CapitalRoute[];
  actors: SmartActor[];
  destinationHeat: DestinationHeat[];
  loading: boolean;
  error: string | null;
}

type WindowKey = '24h' | '7d' | '30d';

export function useTokenIntelligence(chainId: number, window: WindowKey): TokenIntelligenceData & { refresh: () => void } {
  const [data, setData] = useState<TokenIntelligenceData>({
    narrative: null,
    tokenScores: [],
    signals: [],
    patterns: [],
    routes: [],
    actors: [],
    destinationHeat: [],
    loading: true,
    error: null,
  });

  const load = useCallback(async () => {
    setData(prev => ({ ...prev, loading: true, error: null }));
    try {
      const res = await fetch(`${API}/api/onchain/smart-money/intelligence-context?chainId=${chainId}&window=${window}`);
      const json = await res.json();

      if (!json.ok) throw new Error(json.error || 'Failed to load');

      setData({
        narrative: json.narrative || null,
        tokenScores: json.token_scores || [],
        signals: json.signals || [],
        patterns: json.patterns || [],
        routes: json.routes || [],
        actors: json.actors || [],
        destinationHeat: json.destination_heat || [],
        loading: false,
        error: null,
      });
    } catch (e: any) {
      setData(prev => ({ ...prev, loading: false, error: e?.message || 'Failed to load data' }));
    }
  }, [chainId, window]);

  useEffect(() => { load(); }, [load]);

  return { ...data, refresh: load };
}
