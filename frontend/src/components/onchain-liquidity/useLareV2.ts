/**
 * LARE v2 Hook
 * =============
 * 
 * BLOCK 8: Fetch data from new LARE v2.0.0 API
 */

import { useEffect, useState, useCallback } from 'react';

const API_BASE = process.env.REACT_APP_BACKEND_URL || '';

export interface LareV2Gate {
  riskCap: number;
  allowAggressiveRisk: boolean;
  blockNewPositions: boolean;
  reason: string;
}

export interface LareV2Component {
  key: string;
  score: number;
  direction: -1 | 0 | 1;
  strength: number;
  confidence: number;
  drivers: string[];
  flags: string[];
}

export interface LareV2Data {
  version: string;
  window: '24h' | '7d';
  bucketTs: number;
  computedAt: number;
  score: number;
  confidence: number;
  regime: 'RISK_ON_ALTS' | 'MODERATE_RISK_ON' | 'NEUTRAL' | 'MODERATE_RISK_OFF' | 'RISK_OFF';
  gate: LareV2Gate;
  components: LareV2Component[];
  drivers: string[];
  flags: string[];
}

export interface LareV2SeriesPoint {
  t: number;
  score: number;
  confidence: number;
  regime: string;
  riskCap: number;
}

interface UseLareV2State {
  loading: boolean;
  error: string | null;
  latest: LareV2Data | null;
  series: LareV2SeriesPoint[];
}

export function useLareV2(window: '24h' | '7d' = '24h') {
  const [state, setState] = useState<UseLareV2State>({
    loading: true,
    error: null,
    latest: null,
    series: [],
  });

  const refresh = useCallback(async () => {
    setState(s => ({ ...s, loading: true, error: null }));

    try {
      const [latestRes, seriesRes] = await Promise.all([
        fetch(`${API_BASE}/api/v10/onchain-v2/lare-v2/latest?window=${window}`, {
          credentials: 'include',
        }),
        fetch(`${API_BASE}/api/v10/onchain-v2/lare-v2/series?window=${window}&range=30d`, {
          credentials: 'include',
        }),
      ]);

      if (!latestRes.ok) throw new Error(`Latest failed: ${latestRes.status}`);
      if (!seriesRes.ok) throw new Error(`Series failed: ${seriesRes.status}`);

      const latestJson = await latestRes.json();
      const seriesJson = await seriesRes.json();

      setState({
        loading: false,
        error: null,
        latest: latestJson.data || null,
        series: seriesJson.series || [],
      });
    } catch (e: any) {
      setState(s => ({
        ...s,
        loading: false,
        error: e?.message ?? 'Unknown error',
      }));
    }
  }, [window]);

  useEffect(() => {
    refresh();
    const interval = setInterval(refresh, 60000);
    return () => clearInterval(interval);
  }, [refresh]);

  return { ...state, refresh };
}
