import { useState, useEffect, useCallback } from 'react';

const API = process.env.REACT_APP_BACKEND_URL;

export function useMiniAppCore(asset = 'BTC') {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchCore = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API}/api/miniapp/core?asset=${asset}`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const json = await res.json();
      setData(json);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, [asset]);

  useEffect(() => {
    fetchCore();
    const interval = setInterval(fetchCore, 60000);
    return () => clearInterval(interval);
  }, [fetchCore]);

  return { data, loading, error, refetch: fetchCore };
}
