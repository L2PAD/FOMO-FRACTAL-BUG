/**
 * Alt Flow Hook
 * ==============
 * 
 * BLOCK 3.6: Data fetching for alt flow rankings
 */

import { useEffect, useState, useCallback } from 'react';
import type { AltFlowRow } from './AltFlowTable';

interface AltFlowResponse {
  ok: boolean;
  window: string;
  generatedAt: number;
  topAccumulation: AltFlowRow[];
  topDistribution: AltFlowRow[];
  totalTokens: number;
  error?: string;
}

interface UseAltFlowState {
  loading: boolean;
  error: string | null;
  data: AltFlowResponse | null;
}

const API_BASE = process.env.REACT_APP_BACKEND_URL || '';

export function useAltFlow(window: '24h' | '7d' = '24h') {
  const [state, setState] = useState<UseAltFlowState>({
    loading: true,
    error: null,
    data: null,
  });

  const refresh = useCallback(async (forceRefresh = false) => {
    setState(s => ({ ...s, loading: true, error: null }));

    try {
      const url = forceRefresh
        ? `${API_BASE}/api/v10/onchain-v2/market/altflow?window=${window}&refresh=true`
        : `${API_BASE}/api/v10/onchain-v2/market/altflow?window=${window}`;

      const res = await fetch(url, { credentials: 'include' });
      
      if (!res.ok) {
        throw new Error(`Request failed: ${res.status}`);
      }

      const data = await res.json() as AltFlowResponse;

      if (!data.ok) {
        throw new Error(data.error || 'Unknown error');
      }

      setState({
        loading: false,
        error: null,
        data,
      });
    } catch (e: any) {
      setState(s => ({
        ...s,
        loading: false,
        error: e?.message ?? 'Failed to fetch alt flow',
      }));
    }
  }, [window]);

  useEffect(() => {
    refresh();

    // Auto-refresh every 5 minutes
    const interval = setInterval(() => refresh(), 5 * 60 * 1000);
    return () => clearInterval(interval);
  }, [refresh]);

  return { ...state, refresh };
}
