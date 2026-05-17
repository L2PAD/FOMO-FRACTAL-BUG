/**
 * OnchainChainContext — Phase G0.7
 * =================================
 * 
 * Single source of truth for active chain in OnchainV3.
 * Currently locked to Ethereum (chainId=1), selector disabled.
 * When G1.4 enables the selector, this context drives the switch.
 */

import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';

const API_BASE = process.env.REACT_APP_BACKEND_URL || '';

export interface ChainInfo {
  chainId: number;
  key: string;
  name: string;
  enabled: boolean;
  isDefault?: boolean;
  nativeCurrency?: string;
}

interface ChainContextType {
  chainId: number;
  setChainId: (id: number) => void;
  chains: ChainInfo[];
  selectorEnabled: boolean;
  loading: boolean;
}

const ChainContext = createContext<ChainContextType>({
  chainId: 1,
  setChainId: () => {},
  chains: [],
  selectorEnabled: false,
  loading: false,
});

export function useOnchainChain() {
  return useContext(ChainContext);
}

// Feature flag — set to true when G1.4 is ready
const SELECTOR_ENABLED = true;

export function OnchainChainProvider({ children }: { children: React.ReactNode }) {
  const [chainId, setChainIdState] = useState<number>(1);
  const [chains, setChains] = useState<ChainInfo[]>([]);
  const [loading, setLoading] = useState(true);

  // Load chains from API
  useEffect(() => {
    let mounted = true;
    (async () => {
      try {
        const res = await fetch(`${API_BASE}/api/system/chains`);
        if (!res.ok) throw new Error('chains fetch failed');
        const data = await res.json();
        if (mounted && data.ok && Array.isArray(data.chains)) {
          setChains(data.chains);
        }
      } catch (e) {
        // Fallback to ETH only
        if (mounted) {
          setChains([{ chainId: 1, key: 'eth', name: 'Ethereum', enabled: true, isDefault: true }]);
        }
      } finally {
        if (mounted) setLoading(false);
      }
    })();
    return () => { mounted = false; };
  }, []);

  // Read ?chain= from URL on mount
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const urlChain = params.get('chain');
    if (urlChain) {
      const parsed = parseInt(urlChain, 10);
      // Only apply if selector enabled AND chain is valid
      if (SELECTOR_ENABLED && !isNaN(parsed) && parsed > 0) {
        setChainIdState(parsed);
      }
      // If selector disabled, ignore and force ETH
    }
  }, []);

  const setChainId = useCallback((id: number) => {
    if (!SELECTOR_ENABLED) return; // Blocked while disabled
    setChainIdState(id);
    // Update URL param
    const params = new URLSearchParams(window.location.search);
    params.set('chain', String(id));
    window.history.replaceState({}, '', `${window.location.pathname}?${params.toString()}`);
  }, []);

  return (
    <ChainContext.Provider value={{
      chainId,
      setChainId,
      chains,
      selectorEnabled: SELECTOR_ENABLED,
      loading,
    }}>
      {children}
    </ChainContext.Provider>
  );
}
