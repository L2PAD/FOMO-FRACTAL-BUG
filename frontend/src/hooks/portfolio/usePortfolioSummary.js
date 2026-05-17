/**
 * Portfolio Summary Hook (WS-3 Hybrid)
 * 
 * Sprint WS-3: Hybrid architecture
 * - Primary: WebSocket (portfolio.summary channel)
 * - Fallback: HTTP polling (5s interval)
 * - Reconnect-safe: lastWsData persistence
 * 
 * Architecture pattern:
 *   data = wsData ?? lastWsData ?? polledData
 */

import { useState, useEffect, useRef, useCallback } from 'react';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const POLLING_INTERVAL = 5000; // 5 seconds

// WS-3 CRITICAL: WS endpoint is /ws (NOT /api/ws)
// Production-grade URL construction
const WS_BASE = BACKEND_URL
  ? BACKEND_URL
      .replace(/^http/, 'ws')
      .replace(/\/api\/?$/, '')
  : null;
const WS_URL = WS_BASE ? `${WS_BASE}/ws` : null;

export function usePortfolioSummary() {
  // State layers
  const [wsData, setWsData] = useState(null);
  const [lastWsData, setLastWsData] = useState(null);
  const [polledData, setPolledData] = useState(null);
  
  const [isConnected, setIsConnected] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  
  // Refs
  const wsRef = useRef(null);
  const reconnectTimeoutRef = useRef(null);
  const reconnectAttempts = useRef(0);
  const pollingIntervalRef = useRef(null);
  
  // Polling fallback
  const fetchSummary = useCallback(async () => {
    try {
      // Use Promise.race instead of AbortController to avoid postMessage clone error
      const fetchPromise = fetch(`${BACKEND_URL}/api/portfolio/summary`);
      const timeoutPromise = new Promise((_, reject) =>
        setTimeout(() => reject(new Error('Request timeout (10s)')), 10000)
      );
      
      const response = await Promise.race([fetchPromise, timeoutPromise]);
      
      if (!response.ok) {
        throw new Error(`Failed to fetch portfolio summary: ${response.status}`);
      }
      
      const data = await response.json();
      setPolledData(data);
      setError(null);
    } catch (err) {
      console.error('[usePortfolioSummary] Polling error:', err);
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, []);
  
  // WebSocket connection
  const connectWs = useCallback(() => {
    if (!WS_URL) return;
    if (wsRef.current?.readyState === WebSocket.OPEN) return;
    
    try {
      console.log('[usePortfolioSummary] WS connecting...');
      const ws = new WebSocket(WS_URL);
      wsRef.current = ws;
      
      ws.onopen = () => {
        console.log('[usePortfolioSummary] WS connected');
        setIsConnected(true);
        setError(null);
        reconnectAttempts.current = 0;
        
        // Subscribe to portfolio.summary
        ws.send(JSON.stringify({
          type: 'subscribe',
          channels: ['portfolio.summary']
        }));
      };
      
      ws.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data);
          
          // WS-3: Only process snapshot messages
          if (msg.type === 'snapshot' && msg.channel === 'portfolio.summary') {
            const snapshot = msg.data;
            
            // NEVER overwrite with null
            if (!snapshot || Object.keys(snapshot).length === 0) {
              console.warn('[usePortfolioSummary] Received empty snapshot, ignoring');
              return;
            }
            
            setWsData(snapshot);
            setLoading(false);
          }
        } catch (err) {
          console.error('[usePortfolioSummary] WS message parse error:', err);
        }
      };
      
      ws.onerror = (err) => {
        console.error('[usePortfolioSummary] WS error:', err);
        setError('WebSocket error');
      };
      
      ws.onclose = () => {
        console.log('[usePortfolioSummary] WS disconnected');
        setIsConnected(false);
        wsRef.current = null;
        
        // Auto-reconnect (max 5 attempts)
        if (reconnectAttempts.current < 5) {
          reconnectAttempts.current++;
          console.log(`[usePortfolioSummary] Reconnecting... (attempt ${reconnectAttempts.current})`);
          
          reconnectTimeoutRef.current = setTimeout(() => {
            connectWs();
          }, 3000);
        }
      };
    } catch (err) {
      console.error('[usePortfolioSummary] WS connection error:', err);
      setError(err.message);
    }
  }, []);
  
  // Disconnect WebSocket
  const disconnectWs = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }
    
    if (wsRef.current) {
      // Unsubscribe before closing
      if (wsRef.current.readyState === WebSocket.OPEN) {
        wsRef.current.send(JSON.stringify({
          type: 'unsubscribe',
          channels: ['portfolio.summary']
        }));
      }
      wsRef.current.close();
      wsRef.current = null;
    }
    
    setIsConnected(false);
  }, []);
  
  // WS-3 Critical: lastWsData persistence
  useEffect(() => {
    if (wsData && Object.keys(wsData).length > 0) {
      setLastWsData(wsData);
    }
  }, [wsData]);
  
  // Initialize: WS + Polling
  useEffect(() => {
    // Start WebSocket
    connectWs();
    
    // Start polling (always active as fallback)
    fetchSummary();
    pollingIntervalRef.current = setInterval(fetchSummary, POLLING_INTERVAL);
    
    // Cleanup
    return () => {
      disconnectWs();
      if (pollingIntervalRef.current) {
        clearInterval(pollingIntervalRef.current);
        pollingIntervalRef.current = null;
      }
    };
  }, [connectWs, disconnectWs, fetchSummary]);
  
  // WS-3 Architecture: wsData ?? lastWsData ?? polledData
  const data = wsData ?? lastWsData ?? polledData;
  
  return {
    summary: data,
    loading,
    error,
    isConnected,
    refetch: fetchSummary
  };
}
