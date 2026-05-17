/**
 * useDecisionQuality — Phase A.3 Step 1 migration.
 *
 * Canonical URL: /api/ta/analytics/decision-quality
 * Legacy URL  : /api/analytics/decision-quality
 * Backend alias keeps response byte-identical.
 */
import { useState, useEffect } from 'react';
import { taAnalytics } from '../../modules/ta/services';

export function useDecisionQuality() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const json = await taAnalytics.getDecisionQuality();
        if (!cancelled && json && json.ok) setData(json);
      } catch (err) {
        if (!cancelled) console.error('[DecisionQuality] fetch failed:', err);
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    load();
    const iv = setInterval(load, 15000);
    return () => { cancelled = true; clearInterval(iv); };
  }, []);

  return { data, loading };
}
