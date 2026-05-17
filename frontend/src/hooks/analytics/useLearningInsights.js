/**
 * Sprint 6.4: Learning Insights Hook
 *
 * Fetches pattern extraction insights (NO ML).
 *
 * Phase A.3 Step 2 migration — routed through taLearning (canonical /api/ta/*).
 * Backend alias maps /api/ta/learning/insights → /api/learning/insights with
 * a byte-identical response shape.
 */
import { useState, useEffect } from 'react';
import { taLearning } from '../../modules/ta/services';

export function useLearningInsights() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    let mounted = true;

    async function fetchInsights() {
      try {
        const result = await taLearning.getInsights();
        if (mounted) {
          setData(result);
          setError(null);
        }
      } catch (err) {
        if (mounted) {
          console.error('[useLearningInsights] Failed:', err);
          setError(err.message);
        }
      } finally {
        if (mounted) {
          setLoading(false);
        }
      }
    }

    fetchInsights();

    // Refresh every 15 seconds (less frequent than analytics)
    const interval = setInterval(fetchInsights, 15000);

    return () => {
      mounted = false;
      clearInterval(interval);
    };
  }, []);

  return { data, loading, error };
}
