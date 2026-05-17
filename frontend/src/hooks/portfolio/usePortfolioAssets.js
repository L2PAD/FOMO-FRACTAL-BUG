/**
 * Portfolio Assets Hook
 * 
 * Fetches asset breakdown from backend.
 * Polls every 8 seconds.
 */

import { useState, useEffect } from 'react';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;

export function usePortfolioAssets() {
  const [assets, setAssets] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchAssets = async () => {
    try {
      const response = await fetch(`${BACKEND_URL}/api/portfolio/assets`);
      
      if (!response.ok) {
        throw new Error(`Failed to fetch assets: ${response.status}`);
      }
      
      const data = await response.json();
      setAssets(data);
      setError(null);
    } catch (err) {
      console.error('[usePortfolioAssets] Error:', err);
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAssets();
    
    // Refresh every 8 seconds
    const interval = setInterval(fetchAssets, 8000);
    
    return () => clearInterval(interval);
  }, []);

  return {
    assets,
    loading,
    error,
    refetch: fetchAssets
  };
}
