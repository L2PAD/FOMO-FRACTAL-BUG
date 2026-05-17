/**
 * useDecisionAnalytics — Phase A.3 Step 1 migration.
 *
 * Now goes through the canonical TA module client. URL is
 *   /api/ta/analytics/decisions/summary
 * which the backend alias maps to the legacy
 *   /api/analytics/decisions/summary
 * for byte-identical responses.
 */
import { useState, useEffect } from 'react';
import { taAnalytics } from '../../modules/ta/services';

export function useDecisionAnalytics() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const json = await taAnalytics.decisions.getSummary();
        if (!cancelled && json && json.ok) setData(json);
      } catch (err) {
        if (!cancelled) console.error('[DecisionAnalytics] fetch failed:', err);
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    load();
    const iv = setInterval(load, 10000);
    return () => { cancelled = true; clearInterval(iv); };
  }, []);

  return { data, loading };
}
