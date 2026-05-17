import { useEffect, useState, useCallback } from 'react';
import { mobileApi, HistoryData } from '../services/api/mobile-api';

export function useSignalHistory(asset: string) {
  const [data, setData] = useState<HistoryData | null>(null);
  const [loading, setLoading] = useState(true);

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const res = await mobileApi.getHistory(asset);
      setData(res);
    } catch (e) {
      console.warn('history fetch failed', e);
    } finally {
      setLoading(false);
    }
  }, [asset]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  return { data, loading, refetch: fetchData };
}
