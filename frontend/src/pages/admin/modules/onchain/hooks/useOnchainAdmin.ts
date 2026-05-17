import { useState, useEffect, useCallback, useRef } from 'react';
import {
  getRuntime,
  getGovState,
  getAuditLog,
  OnchainRuntimeResponse,
  OnchainGovStateResponse,
  OnchainAuditEntry,
} from '../lib/onchainGovernanceApi';

export interface OnchainAdminData {
  runtime: OnchainRuntimeResponse | null;
  govState: OnchainGovStateResponse | null;
  auditLog: OnchainAuditEntry[];
  loading: boolean;
  error: string | null;
  lastRefresh: number;
}

export function useOnchainAdmin(refreshInterval = 15000) {
  const [data, setData] = useState<OnchainAdminData>({
    runtime: null,
    govState: null,
    auditLog: [],
    loading: false, // Start non-blocking - show UI skeleton immediately
    error: null,
    lastRefresh: 0,
  });
  
  const isMounted = useRef(true);

  const fetchData = useCallback(async () => {
    try {
      // Fetch sequentially to avoid browser Promise issues
      let runtime: OnchainRuntimeResponse | null = null;
      let govState: OnchainGovStateResponse | null = null;
      let audit: { entries: OnchainAuditEntry[] } = { entries: [] };
      
      try {
        runtime = await getRuntime();
      } catch {
        // Silent fail
      }
      
      try {
        govState = await getGovState();
      } catch {
        // Silent fail
      }
      
      try {
        audit = await getAuditLog(50);
      } catch {
        // Silent fail
      }
      
      if (!isMounted.current) return;
      
      setData({
        runtime,
        govState,
        auditLog: audit?.entries || [],
        loading: false,
        error: runtime || govState ? null : 'Failed to fetch data',
        lastRefresh: Date.now(),
      });
    } catch (err) {
      if (!isMounted.current) return;
      setData(prev => ({
        ...prev,
        loading: false,
        error: err instanceof Error ? err.message : 'Unknown error',
        lastRefresh: Date.now(),
      }));
    }
  }, []);

  useEffect(() => {
    isMounted.current = true;
    fetchData();
    const interval = setInterval(fetchData, refreshInterval);
    return () => {
      isMounted.current = false;
      clearInterval(interval);
    };
  }, [fetchData, refreshInterval]);

  return { ...data, refetch: fetchData };
}
