import { useState, useEffect } from 'react';

/**
 * Hook to fetch multi-asset equity curve (Total, BTC, ETH)
 */
export const usePortfolioMultiEquity = (interval = 2000) => {
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchMultiEquity = async () => {
      try {
        const response = await fetch(`${process.env.REACT_APP_BACKEND_URL}/api/portfolio/multi-equity`);
        if (!response.ok) {
          throw new Error(`Failed to fetch multi-equity: ${response.status}`);
        }
        const result = await response.json();
        setData(result);
        setLoading(false);
      } catch (err) {
        console.error('[usePortfolioMultiEquity] Error:', err);
        setError(err.message);
        setLoading(false);
      }
    };

    fetchMultiEquity();

    const intervalId = setInterval(fetchMultiEquity, interval);

    return () => clearInterval(intervalId);
  }, [interval]);

  return { data, loading, error };
};
