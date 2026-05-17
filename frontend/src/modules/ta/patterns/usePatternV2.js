/**
 * usePatternV2 Hook
 * =================
 * 
 * Fetches pattern-v2 API and returns normalized pattern data.
 */

import { useEffect, useState, useCallback } from 'react';
import { adaptPatternV2 } from './patternRenderAdapter';

const API_BASE = process.env.REACT_APP_BACKEND_URL || '';

/**
 * Hook to fetch and normalize pattern-v2 data
 * 
 * @param {string} symbol - Trading pair (e.g., 'BTC', 'ETH')
 * @param {string} timeframe - Timeframe (e.g., '4H', '1D')
 * @returns {Object} { pattern, loading, error, refetch }
 */
export function usePatternV2(symbol, timeframe) {
  const [pattern, setPattern] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  
  const fetchPattern = useCallback(async () => {
    if (!symbol || !timeframe) {
      setPattern(null);
      return;
    }
    
    try {
      setLoading(true);
      setError(null);
      
      const url = `${API_BASE}/api/ta-engine/pattern-v2/${symbol}?timeframe=${timeframe}`;
      console.log('[usePatternV2] Fetching:', url);
      
      const res = await fetch(url);
      if (!res.ok) {
        throw new Error(`Pattern API error: ${res.status}`);
      }
      
      const json = await res.json();
      console.log('[usePatternV2] Response:', json);
      
      const normalized = adaptPatternV2(json);
      console.log('[usePatternV2] Normalized:', normalized);
      
      setPattern(normalized);
      
    } catch (e) {
      console.error('[usePatternV2] Error:', e);
      setError(e.message || 'Failed to load pattern');
      setPattern(null);
    } finally {
      setLoading(false);
    }
  }, [symbol, timeframe]);
  
  useEffect(() => {
    fetchPattern();
  }, [fetchPattern]);
  
  return { 
    pattern, 
    loading, 
    error, 
    refetch: fetchPattern 
  };
}

export default usePatternV2;
