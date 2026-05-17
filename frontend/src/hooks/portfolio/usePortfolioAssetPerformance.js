import { useState, useEffect } from 'react';

export const usePortfolioAssetPerformance = (symbol, interval = 3000) => {
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!symbol) {
      setData([]);
      setLoading(false);
      return;
    }

    const fetchPerformance = async () => {
      try {
        const response = await fetch(`${process.env.REACT_APP_BACKEND_URL}/api/portfolio/asset-performance?symbol=${symbol}`);
        if (!response.ok) throw new Error(`Failed to fetch performance: ${response.status}`);
        const result = await response.json();
        setData(result || []);
        setLoading(false);
      } catch (err) {
        console.error(`[usePortfolioAssetPerformance] Error for ${symbol}:`, err);
        setLoading(false);
      }
    };

    fetchPerformance();
    const intervalId = setInterval(fetchPerformance, interval);
    return () => clearInterval(intervalId);
  }, [symbol, interval]);

  return { data, loading };
};
