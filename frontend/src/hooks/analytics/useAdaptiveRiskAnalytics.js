/**
 * useAdaptiveRiskAnalytics — Phase A.3 Step 1 migration.
 *
 * Canonical URL: /api/ta/analytics/adaptive-risk/summary
 * Legacy URL  : /api/analytics/adaptive-risk/summary
 * Backend alias keeps response byte-identical.
 */
import { useEffect, useState } from 'react';
import { taAnalytics } from '../../modules/ta/services';

export default function useAdaptiveRiskAnalytics() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchData = async () => {
    try {
      // 5s timeout — previously AbortSignal.timeout(5000). We keep parity.
      const controller = new AbortController();
      const to = setTimeout(() => controller.abort(), 5000);
      const json = await taAnalytics.getAdaptiveRiskSummary({ signal: controller.signal });
      clearTimeout(to);
      setData(json);
      setError(null);
    } catch (err) {
      console.error('[useAdaptiveRiskAnalytics] fetch error:', err);
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return { data, loading, error, refresh: fetchData };
}
