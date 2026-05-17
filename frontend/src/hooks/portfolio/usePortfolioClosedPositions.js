/**
 * Portfolio Closed Positions Hook
 * 
 * Fetches closed positions from backend.
 * Polls every 10 seconds (slower - historical data).
 */

import { useState, useEffect } from 'react';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;

export function usePortfolioClosedPositions() {
  const [positions, setPositions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchPositions = async () => {
    try {
      const response = await fetch(`${BACKEND_URL}/api/portfolio/closed-positions`);
      
      if (!response.ok) {
        throw new Error(`Failed to fetch closed positions: ${response.status}`);
      }
      
      const data = await response.json();
      setPositions(data);
      setError(null);
    } catch (err) {
      console.error('[usePortfolioClosedPositions] Error:', err);
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchPositions();
    
    // Refresh every 10 seconds
    const interval = setInterval(fetchPositions, 10000);
    
    return () => clearInterval(interval);
  }, []);

  return {
    positions,
    loading,
    error,
    refetch: fetchPositions
  };
}
