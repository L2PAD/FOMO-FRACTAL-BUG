/**
 * Alt Liquidity Hook
 * ===================
 * 
 * PHASE 3: Data fetching hook for Alt Liquidity Signal
 */

import { useEffect, useState, useCallback, useMemo } from 'react';
import type { LiquidityLatest, LiquiditySeries } from './types';

interface AltLiquidityState {
  loading: boolean;
  error: string | null;
  latest: LiquidityLatest | null;
  series: LiquiditySeries | null;
}

const API_BASE = process.env.REACT_APP_BACKEND_URL || '';

export function useAltLiquidity(params?: { window?: '24h' | '7d' | '30d' }) {
  const window = params?.window ?? '30d';

  const [state, setState] = useState<AltLiquidityState>({
    loading: true,
    error: null,
    latest: null,
    series: null,
  });

  const refresh = useCallback(async () => {
    setState(s => ({ ...s, loading: true, error: null }));

    try {
      const [latestRes, seriesRes] = await Promise.all([
        fetch(`${API_BASE}/api/v10/onchain-v2/market/liquidity/latest`, {
          credentials: 'include',
        }),
        fetch(`${API_BASE}/api/v10/onchain-v2/market/liquidity/series?window=${window}`, {
          credentials: 'include',
        }),
      ]);

      if (!latestRes.ok) throw new Error(`Latest failed: ${latestRes.status}`);
      if (!seriesRes.ok) throw new Error(`Series failed: ${seriesRes.status}`);

      const latestJson = await latestRes.json() as LiquidityLatest;
      const seriesJson = await seriesRes.json() as LiquiditySeries;

      setState({
        loading: false,
        error: null,
        latest: latestJson,
        series: seriesJson,
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
    
    // Auto-refresh every 60 seconds
    const interval = setInterval(refresh, 60000);
    return () => clearInterval(interval);
  }, [refresh]);

  const derived = useMemo(() => {
    const latest = state.latest;
    if (!latest) return null;

    const blocked = 
      latest.governance?.guardrailAction === 'BLOCK_OUTPUT' || 
      latest.governance?.guardrailState === 'CRITICAL';
    const downweighted = latest.governance?.guardrailAction === 'DOWNWEIGHT';
    const score = Number.isFinite(latest.score) ? latest.score : 50;

    return { blocked, downweighted, score };
  }, [state.latest]);

  return { ...state, refresh, derived };
}
