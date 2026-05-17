import { useState, useEffect } from 'react';

export const usePortfolioNarrative = (interval = 3000) => {
  const [narrative, setNarrative] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchNarrative = async () => {
      try {
        const response = await fetch(`${process.env.REACT_APP_BACKEND_URL}/api/portfolio/narrative`);
        if (!response.ok) throw new Error(`Failed to fetch narrative: ${response.status}`);
        const result = await response.json();
        setNarrative(result);
        setLoading(false);
      } catch (err) {
        console.error('[usePortfolioNarrative] Error:', err);
        setLoading(false);
      }
    };

    fetchNarrative();
    const intervalId = setInterval(fetchNarrative, interval);
    return () => clearInterval(intervalId);
  }, [interval]);

  return { narrative, loading };
};
