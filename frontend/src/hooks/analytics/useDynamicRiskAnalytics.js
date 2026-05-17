/**
 * Dynamic Risk Analytics Hook
 * Phase 4: Operational Analytics Layer
 * Phase A.3 Step 1: routed through taAnalytics (canonical /api/ta/*).
 *
 * Simple fetch on mount. NO polling, NO WebSocket, NO global state.
 */
import { useState, useEffect } from 'react';
import { taAnalytics } from '../../modules/ta/services';

export function useDynamicRiskAnalytics() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const refresh = async () => {
    try {
      setLoading(true);
      const json = await taAnalytics.getDynamicRiskSummary();
      setData(json);
      setError(null);
    } catch (err) {
      console.error('[useDynamicRiskAnalytics] Error:', err);
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return { data, loading, error, refresh };
}
