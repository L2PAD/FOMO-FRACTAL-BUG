/**
 * Portfolio Active Positions Hook
 * 
 * Fetches active positions from backend.
 * Polls every 8 seconds.
 */

import { useState, useEffect } from 'react';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;

export function usePortfolioActivePositions() {
  const [positions, setPositions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchPositions = async () => {
    try {
      const response = await fetch(`${BACKEND_URL}/api/portfolio/active-positions`);
      
      if (!response.ok) {
        throw new Error(`Failed to fetch active positions: ${response.status}`);
      }
      
      const data = await response.json();
      setPositions(data);
      setError(null);
    } catch (err) {
      console.error('[usePortfolioActivePositions] Error:', err);
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchPositions();
    
    // Refresh every 8 seconds
    const interval = setInterval(fetchPositions, 8000);
    
    return () => clearInterval(interval);
  }, []);

  return {
    positions,
    loading,
    error,
    refetch: fetchPositions
  };
}
