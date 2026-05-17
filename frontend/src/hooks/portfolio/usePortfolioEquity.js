/**
 * Portfolio Equity Hook
 * 
 * Fetches equity curve snapshots from backend.
 * Transforms to chart format.
 * Polls every 5 seconds.
 */

import { useState, useEffect } from 'react';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;

export function usePortfolioEquity() {
  const [snapshots, setSnapshots] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchEquity = async () => {
    try {
      const response = await fetch(`${BACKEND_URL}/api/portfolio/equity`);
      
      if (!response.ok) {
        throw new Error(`Failed to fetch equity curve: ${response.status}`);
      }
      
      const data = await response.json();
      
      // Transform to chart format: [{ time: timestamp, value: equity }]
      const chartData = data.map(point => ({
        time: point.timestamp,
        value: point.equity
      }));
      
      setSnapshots(chartData);
      setError(null);
    } catch (err) {
      console.error('[usePortfolioEquity] Error:', err);
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchEquity();
    
    // Refresh every 5 seconds
    const interval = setInterval(fetchEquity, 5000);
    
    return () => clearInterval(interval);
  }, []);

  return {
    snapshots,
    loading,
    error,
    refetch: fetchEquity
  };
}
