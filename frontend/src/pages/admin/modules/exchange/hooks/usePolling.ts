/**
 * Polling Hook
 * =============
 * 
 * BLOCK E6: Generic polling hook for admin dashboard
 */

import { useEffect, useRef, useState } from 'react';

export function usePolling<T>(fn: () => Promise<T>, pollMs: number) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<Error | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const alive = useRef(true);

  const run = async () => {
    try {
      const x = await fn();
      if (!alive.current) return;
      setData(x);
      setError(null);
    } catch (e: any) {
      if (!alive.current) return;
      setError(e instanceof Error ? e : new Error(String(e)));
    } finally {
      if (!alive.current) return;
      setIsLoading(false);
    }
  };

  useEffect(() => {
    alive.current = true;
    run();
    const t = setInterval(run, pollMs);
    return () => { alive.current = false; clearInterval(t); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pollMs]);

  return { data, error, isLoading, refetch: run };
}
