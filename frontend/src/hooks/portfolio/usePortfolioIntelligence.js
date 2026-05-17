/**
 * Portfolio Intelligence Hook
 * 
 * Fetches system intelligence metrics.
 * Polls every 5 seconds.
 */

import { useState, useEffect } from 'react';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;

export function usePortfolioIntelligence() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchData = async () => {
    try {
      const response = await fetch(`${BACKEND_URL}/api/portfolio/intelligence`);
      
      if (!response.ok) {
        throw new Error(`Failed to fetch intelligence: ${response.status}`);
      }
      
      const json = await response.json();
      setData(json);
      setError(null);
    } catch (err) {
      console.error('[usePortfolioIntelligence] Error:', err);
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
    
    // Refresh every 5 seconds
    const interval = setInterval(fetchData, 5000);
    
    return () => clearInterval(interval);
  }, []);

  return {
    data,
    loading,
    error,
    refetch: fetchData
  };
}
