/**
 * Strategy Live Signals Hook (WS-3 Hybrid)
 * 
 * Sprint WS-3: Hybrid architecture
 * - Primary: WebSocket (strategy.signals channel)
 * - Fallback: HTTP polling (3s interval)
 * - Reconnect-safe: lastWsData persistence
 * 
 * Architecture pattern:
 *   data = wsData ?? lastWsData ?? polledData
 */

import { useEffect, useState, useRef, useCallback } from "react";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const POLLING_INTERVAL = 3000; // 3 seconds

// WS-3 CRITICAL: WS endpoint is /ws (NOT /api/ws)
// Production-grade URL construction
const WS_BASE = BACKEND_URL
  ? BACKEND_URL
      .replace(/^http/, 'ws')
      .replace(/\/api\/?$/, '')
  : null;
const WS_URL = WS_BASE ? `${WS_BASE}/ws` : null;

export function useStrategyLiveSignals() {
  // State layers
  const [wsData, setWsData] = useState([]);
  const [lastWsData, setLastWsData] = useState([]);
  const [polledData, setPolledData] = useState([]);
  
  const [isConnected, setIsConnected] = useState(false);
  const [error, setError] = useState(null);
  
  // Refs
  const wsRef = useRef(null);
  const reconnectTimeoutRef = useRef(null);
  const reconnectAttempts = useRef(0);
  const pollingIntervalRef = useRef(null);
  
  // Polling fallback
  const fetchSignals = useCallback(async () => {
    try {
      const res = await fetch(`${BACKEND_URL}/api/strategy/signals/live`);
      if (!res.ok) throw new Error(`signals/live failed: ${res.status}`);
      const json = await res.json();
      setPolledData(Array.isArray(json) ? json : []);
      setError(null);
    } catch (e) {
      console.error('[useStrategyLiveSignals] Polling error:', e);
      setError(e.message);
    }
  }, []);
  
  // WebSocket connection
  const connectWs = useCallback(() => {
    if (!WS_URL) return;
    if (wsRef.current?.readyState === WebSocket.OPEN) return;
    
    try {
      console.log('[useStrategyLiveSignals] WS connecting...');
      const ws = new WebSocket(WS_URL);
      wsRef.current = ws;
      
      ws.onopen = () => {
        console.log('[useStrategyLiveSignals] WS connected');
        setIsConnected(true);
        setError(null);
        reconnectAttempts.current = 0;
        
        // Subscribe to strategy.signals
        ws.send(JSON.stringify({
          type: 'subscribe',
          channels: ['strategy.signals']
        }));
      };
      
      ws.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data);
          
          // WS-3: Only process snapshot messages
          if (msg.type === 'snapshot' && msg.channel === 'strategy.signals') {
            const snapshot = msg.data;
            
            // NEVER overwrite with null
            if (!snapshot || !Array.isArray(snapshot)) {
              console.warn('[useStrategyLiveSignals] Received invalid snapshot, ignoring');
              return;
            }
            
            setWsData(snapshot);
          }
        } catch (err) {
          console.error('[useStrategyLiveSignals] WS message parse error:', err);
        }
      };
      
      ws.onerror = (err) => {
        console.error('[useStrategyLiveSignals] WS error:', err);
        setError('WebSocket error');
      };
      
      ws.onclose = () => {
        console.log('[useStrategyLiveSignals] WS disconnected');
        setIsConnected(false);
        wsRef.current = null;
        
        // Auto-reconnect (max 5 attempts)
        if (reconnectAttempts.current < 5) {
          reconnectAttempts.current++;
          console.log(`[useStrategyLiveSignals] Reconnecting... (attempt ${reconnectAttempts.current})`);
          
          reconnectTimeoutRef.current = setTimeout(() => {
            connectWs();
          }, 3000);
        }
      };
    } catch (err) {
      console.error('[useStrategyLiveSignals] WS connection error:', err);
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
          channels: ['strategy.signals']
        }));
      }
      wsRef.current.close();
      wsRef.current = null;
    }
    
    setIsConnected(false);
  }, []);
  
  // WS-3 Critical: lastWsData persistence
  useEffect(() => {
    if (wsData && wsData.length > 0) {
      setLastWsData(wsData);
    }
  }, [wsData]);
  
  // Initialize: WS + Polling
  useEffect(() => {
    // Start WebSocket
    connectWs();
    
    // Start polling (always active as fallback)
    fetchSignals();
    pollingIntervalRef.current = setInterval(fetchSignals, POLLING_INTERVAL);
    
    // Cleanup
    return () => {
      disconnectWs();
      if (pollingIntervalRef.current) {
        clearInterval(pollingIntervalRef.current);
        pollingIntervalRef.current = null;
      }
    };
  }, [connectWs, disconnectWs, fetchSignals]);
  
  // WS-3 Architecture: wsData ?? lastWsData ?? polledData
  const data = (wsData && wsData.length > 0) ? wsData : 
               (lastWsData && lastWsData.length > 0) ? lastWsData : 
               polledData;
  
  return { 
    data, 
    error,
    isConnected
  };
}
