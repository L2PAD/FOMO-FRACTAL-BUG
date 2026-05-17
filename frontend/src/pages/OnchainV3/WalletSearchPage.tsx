import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { ArrowRight, TrendingUp } from 'lucide-react';

const API_BASE = process.env.REACT_APP_BACKEND_URL || '';

export default function WalletSearchPage({ onOpenWallet }: { onOpenWallet?: (addr: string) => void }) {
  const navigate = useNavigate();
  const [query, setQuery] = useState('');
  const [topWallets, setTopWallets] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch(`${API_BASE}/api/onchain/smart-money/context?chainId=1&window=24h`)
      .then(r => r.json())
      .then(j => {
        if (j.ok && j.actors) {
          setTopWallets(j.actors.slice(0, 8));
        }
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  const openWallet = (addr: string) => {
    if (onOpenWallet) onOpenWallet(addr);
    else navigate(`/wallet/${encodeURIComponent(addr)}`);
  };

  const handleSearch = () => {
    const q = query.trim();
    if (!q) return;
    openWallet(q);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') handleSearch();
  };

  return (
    <div className="min-h-[60vh]" data-testid="wallet-search-page">
      <div className="max-w-3xl mx-auto px-6 pt-16 pb-16">

        <div className="text-center mb-12">
          <h1 className="text-4xl font-bold text-gray-900 mb-3" data-testid="wallet-search-title">
            Wallet Intelligence
          </h1>
          <p className="text-base text-gray-400">Search any wallet address to analyze behavior, strategy, and signals</p>
        </div>

        {/* Search */}
        <div className="relative mb-16" data-testid="wallet-search-input-wrapper">
          <input
            type="text"
            value={query}
            onChange={e => setQuery(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="0x..."
            className="w-full px-5 py-4 rounded-2xl bg-white text-gray-900 text-base placeholder:text-gray-300 focus:outline-none focus:ring-2 focus:ring-gray-200 transition-all"
            data-testid="wallet-search-input"
          />
          {query.trim() && (
            <button
              onClick={handleSearch}
              className="absolute right-3 top-1/2 -translate-y-1/2 p-2 rounded-xl bg-gray-900 text-white hover:bg-gray-800 transition-colors"
              data-testid="wallet-search-submit">
              <ArrowRight className="w-4 h-4" />
            </button>
          )}
        </div>

        {/* Top Smart Wallets */}
        <div className="mb-12">
          <div className="flex items-center gap-2 mb-4">
            <TrendingUp className="w-4 h-4 text-gray-400" />
            <h3 className="text-sm font-bold text-gray-400 uppercase tracking-wider">Top Smart Wallets</h3>
          </div>

          {loading ? (
            <div className="text-center py-8">
              <div className="animate-spin w-5 h-5 border-2 border-gray-900 border-t-transparent rounded-full mx-auto" />
            </div>
          ) : topWallets.length > 0 ? (
            <div className="space-y-2">
              {topWallets.map((w, i) => (
                <button
                  key={w.wallet}
                  onClick={() => openWallet(w.wallet)}
                  className="w-full flex items-center gap-4 py-3 px-4 rounded-xl bg-white hover:bg-gray-50 transition-colors text-left group"
                  data-testid={`top-wallet-${i + 1}`}>
                  <span className="text-xs text-gray-300 w-5 text-right tabular-nums">{i + 1}</span>
                  <div className="flex-1 min-w-0">
                    <span className="text-sm font-semibold text-gray-900 truncate block">{w.name?.replace(/_/g, ' ')}</span>
                    <span className="text-xs text-gray-400 font-mono">{shortAddr(w.wallet)}</span>
                  </div>
                  <div className="text-right">
                    <div className="text-xs font-bold text-gray-900">Score {w.smart_score}</div>
                    <div className={`text-xs font-semibold tabular-nums ${w.net_flow_usd >= 0 ? 'text-emerald-600' : 'text-red-600'}`}>
                      {w.net_flow_usd >= 0 ? '+' : ''}{w.net_flow_fmt}
                    </div>
                  </div>
                  <ArrowRight className="w-3.5 h-3.5 text-gray-200 group-hover:text-gray-400 transition-colors flex-shrink-0" />
                </button>
              ))}
            </div>
          ) : (
            <p className="text-sm text-gray-300 text-center py-6">No wallet data available</p>
          )}
        </div>
      </div>
    </div>
  );
}

function shortAddr(addr: string): string {
  if (!addr || addr.length < 10) return addr;
  return `${addr.slice(0, 6)}...${addr.slice(-4)}`;
}
