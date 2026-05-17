import { useState, useEffect } from 'react';

export const usePortfolioDecision = (interval = 3000) => {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchDecision = async () => {
      try {
        const response = await fetch(`${process.env.REACT_APP_BACKEND_URL}/api/portfolio/decision`);
        if (!response.ok) throw new Error(`Failed to fetch decision: ${response.status}`);
        const result = await response.json();
        setData(result);
        setLoading(false);
      } catch (err) {
        console.error('[usePortfolioDecision] Error:', err);
        setLoading(false);
      }
    };

    fetchDecision();
    const intervalId = setInterval(fetchDecision, interval);
    return () => clearInterval(intervalId);
  }, [interval]);

  return { data, loading };
};
