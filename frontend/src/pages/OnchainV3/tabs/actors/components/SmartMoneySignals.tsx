import React, { useState } from 'react';
import { TrendingUp, TrendingDown, ArrowRight, RefreshCw, Zap, ChevronDown, ChevronRight, ExternalLink, Copy, Check } from 'lucide-react';
import { Tooltip, TooltipTrigger, TooltipContent } from '../../../../../components/ui/tooltip';
import type { AlphaSignal, FeedFilter, ConvictionTier } from '../types/smartMoney';

function WalletExpandList({ wallets, onNavigateToWallet }: { wallets: string[]; onNavigateToWallet?: (addr: string, src: string) => void }) {
  const [copiedIdx, setCopiedIdx] = useState<number | null>(null);
  if (!wallets?.length) return null;
  return (
    <div className="mt-2 pt-2 border-t border-gray-700/50">
      <div className="text-[9px] font-bold text-gray-500 uppercase tracking-wider mb-1.5">Wallets</div>
      <div className="space-y-1">
        {wallets.map((addr, i) => (
          <div key={addr} className="flex items-center gap-2 group" data-testid={`signal-wallet-${i}`}>
            <span className="text-[9px] text-gray-600 tabular-nums w-4">{i + 1}.</span>
            <button onClick={() => onNavigateToWallet?.(addr, 'smart_money')}
              className="text-[10px] text-violet-400 hover:text-violet-300 font-mono transition-colors truncate"
              data-testid={`signal-wallet-link-${i}`}>
              {addr.slice(0, 8)}...{addr.slice(-6)}
            </button>
            <a href={`https://etherscan.io/address/${addr}`} target="_blank" rel="noopener noreferrer"
              className="opacity-0 group-hover:opacity-100 transition-opacity">
              <ExternalLink className="w-3 h-3 text-gray-600 hover:text-gray-400" />
            </a>
            <button onClick={() => { navigator.clipboard.writeText(addr); setCopiedIdx(i); setTimeout(() => setCopiedIdx(null), 1500); }}
              className="opacity-0 group-hover:opacity-100 transition-opacity">
              {copiedIdx === i ? <Check className="w-3 h-3 text-emerald-400" /> : <Copy className="w-3 h-3 text-gray-600 hover:text-gray-400" />}
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}

const SIGNAL_TYPE_CONFIG: Record<string, { label: string; color: string; dotColor: string }> = {
  accumulation: { label: 'Accumulation', color: 'text-emerald-600', dotColor: 'bg-emerald-500' },
  distribution: { label: 'Distribution', color: 'text-red-600', dotColor: 'bg-red-500' },
  rotation: { label: 'Rotation', color: 'text-blue-600', dotColor: 'bg-blue-500' },
  momentum: { label: 'Momentum', color: 'text-purple-600', dotColor: 'bg-purple-500' },
  weakening: { label: 'Weakening', color: 'text-amber-600', dotColor: 'bg-amber-500' },
  cluster_activity: { label: 'Cluster', color: 'text-cyan-600', dotColor: 'bg-cyan-500' },
  exit: { label: 'Exit', color: 'text-amber-600', dotColor: 'bg-amber-500' },
};

const FEED_FILTERS: Array<{ key: FeedFilter; label: string }> = [
  { key: 'all', label: 'All' },
  { key: 'accumulation', label: 'Accumulation' },
  { key: 'distribution', label: 'Distribution' },
  { key: 'rotation', label: 'Rotation' },
  { key: 'momentum', label: 'Momentum' },
];

const TIER_FILTERS: Array<{ key: ConvictionTier; label: string; color: string }> = [
  { key: 'high', label: 'HIGH', color: 'text-emerald-400' },
  { key: 'medium', label: 'MED', color: 'text-amber-400' },
  { key: 'low', label: 'LOW', color: 'text-gray-400' },
  { key: 'all', label: 'ALL', color: 'text-gray-300' },
];

export function TradeInsightBlock({ insight }: {
  insight: { title: string; body: string; action: string; signal: 'bullish' | 'bearish' | 'neutral' };
}) {
  const cfg = {
    bullish: { accent: 'text-emerald-700', icon: 'text-emerald-600' },
    bearish: { accent: 'text-red-700', icon: 'text-red-600' },
    neutral: { accent: 'text-amber-700', icon: 'text-amber-600' },
  }[insight.signal];

  return (
    <div className="p-6" data-testid="trade-insight-block">
      <div className="flex items-start gap-4">
        <div className="w-10 h-10 flex items-center justify-center">
          <Zap className={`w-5 h-5 ${cfg.icon}`} />
        </div>
        <div className="flex-1">
          <h3 className={`font-bold text-base ${cfg.accent}`} data-testid="insight-title">{insight.title}</h3>
          <p className="text-sm text-gray-700 mt-2 leading-relaxed">{insight.body}</p>
          <div className="mt-3 pt-3">
            <div className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1">Suggested action</div>
            <p className={`text-sm font-medium ${cfg.accent}`} data-testid="insight-action">{insight.action}</p>
          </div>
        </div>
      </div>
    </div>
  );
}

export function AlphaFeedBlock({ signals, loading, filter, onFilterChange, tier, onTierChange, onRefresh, onNavigateToWallet }: {
  signals: AlphaSignal[];
  loading: boolean;
  filter: FeedFilter;
  onFilterChange: (f: FeedFilter) => void;
  tier: ConvictionTier;
  onTierChange: (t: ConvictionTier) => void;
  onRefresh: () => void;
  onNavigateToWallet?: (address: string, src: string, params?: Record<string, string>) => void;
}) {
  if (loading && signals.length === 0) {
    return (
      <div className="rounded-2xl bg-gray-900 intelligence-dark p-8 text-center" data-testid="alpha-feed-block">
        <div className="animate-spin w-6 h-6 border-2 border-emerald-400 border-t-transparent rounded-full mx-auto" />
        <p className="text-gray-500 mt-3 text-sm">Scanning for alpha signals...</p>
      </div>
    );
  }

  return (
    <div className="rounded-2xl bg-gray-900 intelligence-dark overflow-hidden" data-testid="alpha-feed-block">
      <div className="px-6 py-4">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-3">
            <Zap className="w-5 h-5 text-amber-400" />
            <div>
              <h3 className="font-bold text-white">Smart Money Signals</h3>
              <p className="text-xs text-gray-500">High-conviction alpha feed</p>
            </div>
          </div>
          <button onClick={onRefresh} disabled={loading}
            className="p-2 text-gray-500 hover:text-gray-300 transition-colors disabled:opacity-50"
            data-testid="feed-refresh-btn">
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
          </button>
        </div>

        <div className="flex items-center justify-between">
          <div className="flex gap-1" data-testid="feed-tier-controls">
            {TIER_FILTERS.map(({ key, label, color }) => (
              <button key={key} onClick={() => onTierChange(key)}
                className={`px-3 py-1.5 text-xs font-bold tracking-wider transition-all ${
                  tier === key ? `${color} underline underline-offset-4` : 'text-gray-600 hover:text-gray-400'
                }`} data-testid={`feed-tier-${key}`}>
                {label}
              </button>
            ))}
          </div>
          <div className="flex gap-1" data-testid="feed-filter-controls">
            {FEED_FILTERS.map(({ key, label }) => (
              <button key={key} onClick={() => onFilterChange(key)}
                className={`px-2.5 py-1.5 text-[10px] font-semibold transition-all ${
                  filter === key ? 'text-white' : 'text-gray-600 hover:text-gray-400'
                }`} data-testid={`feed-filter-${key}`}>
                {label}
              </button>
            ))}
          </div>
        </div>
      </div>

      {signals.length === 0 ? (
        <div className="px-6 pb-6 text-center">
          <p className="text-gray-500 text-sm">No signals match current filters</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-0">
          {signals.slice(0, 9).map((sig, i) => {
            const cfg = SIGNAL_TYPE_CONFIG[sig.signal_type] || SIGNAL_TYPE_CONFIG.accumulation;
            const convictionColor = sig.conviction >= 60 ? 'text-emerald-400' : sig.conviction >= 50 ? 'text-amber-400' : 'text-gray-400';
            const convictionBar = sig.conviction >= 60 ? 'bg-emerald-400' : sig.conviction >= 50 ? 'bg-amber-400' : 'bg-gray-500';
            const tierLabel = sig.conviction >= 60 ? 'HIGH' : sig.conviction >= 50 ? 'MED' : 'LOW';
            const tierColor = sig.conviction >= 60 ? 'text-emerald-400' : sig.conviction >= 50 ? 'text-amber-400' : 'text-gray-500';
            const isRotation = sig.signal_type === 'rotation';
            const hasWallets = sig.wallet_addresses && sig.wallet_addresses.length > 0;

            return (
              <SignalCard key={sig.signal_id} sig={sig} index={i} cfg={cfg}
                convictionColor={convictionColor} convictionBar={convictionBar}
                tierLabel={tierLabel} tierColor={tierColor} isRotation={isRotation}
                hasWallets={hasWallets} onNavigateToWallet={onNavigateToWallet} />
            );
          })}
        </div>
      )}
    </div>
  );
}

function SignalCard({ sig, index, cfg, convictionColor, convictionBar, tierLabel, tierColor, isRotation, hasWallets, onNavigateToWallet }: any) {
  const [expanded, setExpanded] = useState(false);
  return (
    <div className="px-6 py-4 hover:bg-gray-800/40 transition-colors" data-testid={`feed-signal-${index + 1}`}>
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <span className={`w-1.5 h-1.5 rounded-full ${cfg.dotColor}`} />
          <span className={`text-[10px] font-bold uppercase tracking-wider ${cfg.color}`}>{cfg.label}</span>
          <span className={`text-[9px] font-bold ${tierColor}`}>{tierLabel}</span>
        </div>
        <span className={`text-lg font-bold tabular-nums ${convictionColor}`}
          data-testid={`feed-conviction-${index + 1}`}>{sig.conviction}%</span>
      </div>

      {isRotation ? (
        <div className="flex items-center gap-1.5 mb-2">
          <span className="text-base font-bold text-white">{sig.from_token}</span>
          <ArrowRight className="w-3.5 h-3.5 text-gray-500" />
          <span className="text-base font-bold text-white">{sig.to_token}</span>
        </div>
      ) : (
        <div className="text-base font-bold text-white mb-2">{sig.token}</div>
      )}

      <div className="h-1 bg-gray-700 rounded-full overflow-hidden mb-3">
        <div className={`h-full rounded-full ${convictionBar} transition-all duration-700`}
          style={{ width: `${sig.conviction}%` }} />
      </div>

      <div className="flex items-center gap-4 text-[10px] mb-3">
        <span className="text-gray-400">{sig.capital_fmt} capital</span>
        {hasWallets ? (
          <button onClick={() => setExpanded(!expanded)}
            className="text-violet-400 hover:text-violet-300 transition-colors flex items-center gap-1"
            data-testid={`signal-expand-wallets-${index}`}>
            {expanded ? <ChevronDown className="w-3 h-3" /> : <ChevronRight className="w-3 h-3" />}
            {sig.wallet_count} wallets
          </button>
        ) : (
          <span className="text-gray-400">{sig.wallet_count} wallets</span>
        )}
      </div>

      {sig.drivers.length > 0 && (
        <div className="mt-2">
          <div className="text-[9px] font-bold text-gray-500 uppercase tracking-wider mb-1.5">Why signal</div>
          <div className="space-y-1">
            {sig.drivers.map((d: string, di: number) => (
              <div key={di} className="text-[10px] text-gray-400 flex items-center gap-1.5">
                <span className={`w-1 h-1 rounded-full ${cfg.dotColor}`} />
                {d}
              </div>
            ))}
          </div>
        </div>
      )}

      {expanded && hasWallets && (
        <WalletExpandList wallets={sig.wallet_addresses} onNavigateToWallet={onNavigateToWallet} />
      )}
    </div>
  );
}
