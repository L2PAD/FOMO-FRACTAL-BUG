/**
 * Portfolio Allocations Hook
 * 
 * Fetches asset allocations from backend.
 * Transforms for donut chart and legend.
 * Polls every 5 seconds.
 */

import { useState, useEffect } from 'react';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;

export function usePortfolioAllocations() {
  const [allocations, setAllocations] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchAllocations = async () => {
    try {
      const response = await fetch(`${BACKEND_URL}/api/portfolio/allocations`);
      
      if (!response.ok) {
        throw new Error(`Failed to fetch allocations: ${response.status}`);
      }
      
      const data = await response.json();
      setAllocations(data);
      setError(null);
    } catch (err) {
      console.error('[usePortfolioAllocations] Error:', err);
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAllocations();
    
    // Refresh every 5 seconds
    const interval = setInterval(fetchAllocations, 5000);
    
    return () => clearInterval(interval);
  }, []);

  return {
    allocations,
    loading,
    error,
    refetch: fetchAllocations
  };
}
