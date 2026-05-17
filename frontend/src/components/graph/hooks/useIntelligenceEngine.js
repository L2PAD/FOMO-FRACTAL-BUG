import { useState, useCallback } from 'react';

export function useIntelligenceEngine() {
  const [intelligence, setIntelligence] = useState([]);
  const [marketContext, setMarketContext] = useState(null);

  const clearIntelligence = useCallback(() => {
    setIntelligence([]);
    setMarketContext(null);
  }, []);

  return { intelligence, setIntelligence, marketContext, setMarketContext, clearIntelligence };
}
