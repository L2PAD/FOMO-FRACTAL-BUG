import { useEffect, useRef, useState, useCallback } from "react";

export function usePolling<T>(fn: () => Promise<T>, pollMs: number) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<Error | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  const alive = useRef(true);

  const run = useCallback(async () => {
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
  }, [fn]);

  useEffect(() => {
    alive.current = true;
    run();

    const t = setInterval(run, pollMs);
    return () => {
      alive.current = false;
      clearInterval(t);
    };
  }, [pollMs, run]);

  return {
    data,
    error,
    isLoading,
    refetch: run,
  };
}
