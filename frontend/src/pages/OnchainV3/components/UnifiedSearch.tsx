/**
 * Unified Search Router — Phase E4
 * ===================================
 * One search for the entire hub. Routes inputs to:
 *   - 0x... (42 chars) wallet → Wallets tab
 *   - 0x... (shorter) token address → Assets deep dive
 *   - Symbol (LINK, UNI) → Assets deep dive
 *   - Entity label (binance) → CEX Flow / Actors
 */

import React, { useState, useCallback, useRef, useEffect } from 'react';
import { Search, Loader2, Wallet, Coins, Building2, X } from 'lucide-react';
import { useOnchainChain } from '../context/OnchainChainContext';

const API_BASE = process.env.REACT_APP_BACKEND_URL || '';

interface SearchResult {
  type: 'wallet' | 'token' | 'exchange';
  label: string;
  sublabel?: string;
  value: string; // address or symbol
  tab: string;
  params: Record<string, string>;
}

interface Props {
  onNavigate: (tab: string, params?: Record<string, string>) => void;
}

export function UnifiedSearch({ onNavigate }: Props) {
  const { chainId } = useOnchainChain();
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<SearchResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const timer = useRef<any>(null);

  // Close dropdown on outside click
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  const search = useCallback(async (q: string) => {
    if (q.length < 2) { setResults([]); setOpen(false); return; }
    setLoading(true);

    const items: SearchResult[] = [];

    // 1. If looks like wallet address (0x... 42 chars)
    if (q.startsWith('0x') && q.length >= 40) {
      items.push({
        type: 'wallet',
        label: `${q.slice(0, 8)}...${q.slice(-4)}`,
        sublabel: 'Wallet Deep Profile',
        value: q,
        tab: 'wallets',
        params: { address: q },
      });
    }

    // 2. If looks like token address (0x... shorter)
    if (q.startsWith('0x') && q.length >= 10 && q.length < 42) {
      items.push({
        type: 'token',
        label: q.slice(0, 10) + '...',
        sublabel: 'Token lookup',
        value: q,
        tab: 'assets',
        params: { token: q },
      });
    }

    // 3. Token suggest (D1)
    if (!q.startsWith('0x') || q.length < 10) {
      try {
        const r = await fetch(`${API_BASE}/api/v10/onchain-v2/market/tokens/suggest?chainId=${chainId}&q=${encodeURIComponent(q)}&limit=5`);
        const data = await r.json();
        if (data.ok && data.items) {
          for (const t of data.items) {
            items.push({
              type: 'token',
              label: t.symbol,
              sublabel: t.name,
              value: t.address,
              tab: 'assets',
              params: { token: t.address },
            });
          }
        }
      } catch {}

      // 4. Check for exchange-like names (simple hardcoded for now)
      const exchangeKeywords: Record<string, string> = {
        binance: 'binance', coinbase: 'coinbase', kraken: 'kraken',
        okx: 'okx', bybit: 'bybit', bitfinex: 'bitfinex',
        kucoin: 'kucoin', huobi: 'huobi', gemini: 'gemini',
        'crypto.com': 'crypto.com', gate: 'gate.io',
      };
      const lower = q.toLowerCase();
      for (const [key, exName] of Object.entries(exchangeKeywords)) {
        if (key.includes(lower) || lower.includes(key)) {
          items.push({
            type: 'exchange',
            label: exName.charAt(0).toUpperCase() + exName.slice(1),
            sublabel: 'CEX Exchange',
            value: exName,
            tab: 'cex-flow',
            params: { exchange: exName },
          });
          break;
        }
      }
    }

    setResults(items);
    setOpen(items.length > 0);
    setLoading(false);
  }, []);

  const handleInput = (val: string) => {
    setQuery(val);
    if (timer.current) clearTimeout(timer.current);
    timer.current = setTimeout(() => search(val), 200);
  };

  const selectResult = (r: SearchResult) => {
    setOpen(false);
    setQuery('');
    onNavigate(r.tab, r.params);
  };

  const ICONS: Record<string, React.ElementType> = {
    wallet: Wallet,
    token: Coins,
    exchange: Building2,
  };

  return (
    <div ref={ref} className="relative" data-testid="unified-search">
      <div className="relative">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
        <input
          type="text"
          value={query}
          onChange={e => handleInput(e.target.value)}
          onFocus={() => results.length > 0 && setOpen(true)}
          placeholder="Search: token, wallet, exchange..."
          className="w-64 pl-9 pr-8 py-2 bg-gray-50 rounded-xl text-sm focus:outline-none"
          data-testid="unified-search-input"
        />
        {query && (
          <button onClick={() => { setQuery(''); setResults([]); setOpen(false); }} className="absolute right-2.5 top-1/2 -translate-y-1/2">
            <X className="w-3.5 h-3.5 text-gray-400 hover:text-gray-600" />
          </button>
        )}
        {loading && <Loader2 className="absolute right-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 animate-spin text-gray-400" />}
      </div>

      {open && results.length > 0 && (
        <div className="absolute top-full mt-1 left-0 w-80 bg-white rounded-xl z-50 py-1 max-h-72 overflow-y-auto" data-testid="unified-search-dropdown">
          {results.map((r, i) => {
            const Icon = ICONS[r.type] || Search;
            return (
              <button
                key={`${r.type}-${r.value}-${i}`}
                onClick={() => selectResult(r)}
                className="flex items-center gap-3 w-full px-3 py-2 hover:bg-gray-50 transition-colors text-left"
                data-testid={`search-result-${i}`}
              >
                <div className={`w-7 h-7 rounded-lg flex items-center justify-center flex-shrink-0 ${
                  r.type === 'wallet' ? 'bg-purple-50' :
                  r.type === 'exchange' ? 'bg-amber-50' :
                  'bg-blue-50'
                }`}>
                  <Icon className={`w-3.5 h-3.5 ${
                    r.type === 'wallet' ? 'text-purple-500' :
                    r.type === 'exchange' ? 'text-amber-500' :
                    'text-blue-500'
                  }`} />
                </div>
                <div className="min-w-0">
                  <p className="text-sm font-medium text-gray-800 truncate">{r.label}</p>
                  {r.sublabel && <p className="text-[11px] text-gray-400 truncate">{r.sublabel}</p>}
                </div>
                <span className="ml-auto text-[10px] text-gray-300 flex-shrink-0 uppercase">{r.type}</span>
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}

export default UnifiedSearch;
