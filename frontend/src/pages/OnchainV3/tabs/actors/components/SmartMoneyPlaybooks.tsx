import React, { useState } from 'react';
import { TrendingUp, TrendingDown, ArrowRight, AlertCircle, Users, Target, ExternalLink, ChevronDown, ChevronRight, Copy, Check } from 'lucide-react';
import { addressUrl } from '../../../utils/explorer';
import type { Playbook } from '../types/smartMoney';

const PLAYBOOK_SIGNAL_CONFIG: Record<string, { icon: React.ReactNode; color: string; dotColor: string }> = {
  accumulation: { icon: <TrendingUp className="w-4 h-4" />, color: 'text-emerald-600', dotColor: 'bg-emerald-500' },
  distribution: { icon: <TrendingDown className="w-4 h-4" />, color: 'text-red-600', dotColor: 'bg-red-500' },
  rotation: { icon: <ArrowRight className="w-4 h-4" />, color: 'text-blue-600', dotColor: 'bg-blue-500' },
  momentum: { icon: <TrendingUp className="w-4 h-4" />, color: 'text-purple-600', dotColor: 'bg-purple-500' },
  cluster_activity: { icon: <Users className="w-4 h-4" />, color: 'text-cyan-600', dotColor: 'bg-cyan-500' },
  weakening: { icon: <TrendingDown className="w-4 h-4" />, color: 'text-amber-600', dotColor: 'bg-amber-500' },
  exit: { icon: <AlertCircle className="w-4 h-4" />, color: 'text-amber-600', dotColor: 'bg-amber-500' },
};

const STRATEGY_LABELS: Record<string, string> = {
  early_accumulator: 'Early Accumulator',
  momentum_trader: 'Momentum Trader',
  rotation_trader: 'Rotation Trader',
  distribution_wallet: 'Distribution',
  active_trader: 'Active Trader',
  liquidity_provider: 'LP Provider',
};

const STRATEGY_DESCRIPTIONS: Record<string, string> = {
  accumulation: 'Accumulating before momentum phase. Smart money entering early positions.',
  distribution: 'Distributing holdings. Smart money reducing exposure on strength.',
  rotation: 'Rotating capital between assets. Sector rotation in progress.',
  momentum: 'Riding momentum with size. Trend-following entry detected.',
  cluster_activity: 'Coordinated cluster activity. Multiple wallets acting in sync.',
  exit: 'Risk-off mode. Moving capital to safety.',
  weakening: 'Weakening conviction. Position reduction detected.',
};

export function PlaybooksBlock({ playbooks, loading, onNavigateToWallet, chainId }: {
  playbooks: Playbook[];
  loading: boolean;
  onNavigateToWallet?: (address: string, src: string, params?: Record<string, string>) => void;
  chainId?: number;
}) {
  if (loading && playbooks.length === 0) {
    return (
      <div className="rounded-2xl bg-white p-6 text-center" data-testid="playbooks-block">
        <div className="animate-spin w-6 h-6 border-2 border-gray-900 border-t-transparent rounded-full mx-auto" />
        <p className="text-gray-400 mt-3 text-sm">Detecting playbooks...</p>
      </div>
    );
  }
  if (playbooks.length === 0) return null;

  return (
    <div className="rounded-2xl bg-white overflow-hidden" data-testid="playbooks-block">
      <div className="px-6 py-4 flex items-center gap-3">
        <Target className="w-5 h-5 text-indigo-500" />
        <div>
          <h3 className="font-bold text-gray-900">Smart Money Playbooks</h3>
          <p className="text-xs text-gray-400">Clusters of wallets executing coordinated strategies</p>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-0">
        {playbooks.map((pb, i) => (
          <PlaybookCard key={pb.playbook_id} pb={pb} index={i}
            onNavigateToWallet={onNavigateToWallet} chainId={chainId} />
        ))}
      </div>
    </div>
  );
}


function PlaybookCard({ pb, index, onNavigateToWallet, chainId }: {
  pb: Playbook;
  index: number;
  onNavigateToWallet?: (address: string, src: string, params?: Record<string, string>) => void;
  chainId?: number;
}) {
  const [expanded, setExpanded] = useState(false);
  const [copiedIdx, setCopiedIdx] = useState<number | null>(null);
  const cfg = PLAYBOOK_SIGNAL_CONFIG[pb.signal_type] || PLAYBOOK_SIGNAL_CONFIG.accumulation;
  const convictionColor = pb.conviction >= 60 ? 'text-emerald-600' : pb.conviction >= 50 ? 'text-amber-600' : 'text-gray-500';
  const convictionBar = pb.conviction >= 60 ? 'bg-emerald-500' : pb.conviction >= 50 ? 'bg-amber-500' : 'bg-gray-400';
  const isRotation = pb.signal_type === 'rotation';
  const stratDesc = STRATEGY_DESCRIPTIONS[pb.signal_type] || '';
  const hasWalletAddresses = pb.wallet_addresses && pb.wallet_addresses.length > 0;

  return (
    <div className="px-6 py-5 hover:bg-gray-50 transition-colors" data-testid={`playbook-card-${index + 1}`}>
      <div className="flex items-center gap-2 mb-1">
        <span className={cfg.color}>{cfg.icon}</span>
        <span className={`text-xs font-bold uppercase tracking-wider ${cfg.color}`}>{pb.label}</span>
      </div>

      {isRotation ? (
        <div className="flex items-center gap-1.5 mb-2">
          <span className="text-lg font-bold text-gray-900">{pb.from_token}</span>
          <ArrowRight className="w-4 h-4 text-gray-400" />
          <span className="text-lg font-bold text-gray-900">{pb.to_token}</span>
        </div>
      ) : (
        <div className="text-lg font-bold text-gray-900 mb-2">{pb.token}</div>
      )}

      {stratDesc && (
        <p className="text-[11px] text-gray-500 mb-3 leading-relaxed italic">{stratDesc}</p>
      )}

      <div className="flex items-center gap-4 mb-3">
        <div>
          <div className="text-[10px] text-gray-400">Conviction</div>
          <div className="flex items-center gap-1.5">
            <div className="w-12 h-1.5 bg-gray-100 rounded-full overflow-hidden">
              <div className={`h-full rounded-full ${convictionBar}`} style={{ width: `${pb.conviction}%` }} />
            </div>
            <span className={`text-xs font-bold ${convictionColor}`}>{pb.conviction}%</span>
          </div>
        </div>
        <div>
          <div className="text-[10px] text-gray-400">Capital</div>
          <div className="text-xs font-bold text-gray-700">{pb.capital_fmt}</div>
        </div>
        <div>
          <div className="text-[10px] text-gray-400">Wallets</div>
          {hasWalletAddresses ? (
            <button
              onClick={() => setExpanded(!expanded)}
              className="text-xs font-bold text-violet-500 hover:text-violet-400 flex items-center gap-0.5 transition-colors"
              data-testid={`playbook-expand-${index}`}
            >
              {expanded ? <ChevronDown className="w-3 h-3" /> : <ChevronRight className="w-3 h-3" />}
              {pb.wallet_count}
            </button>
          ) : (
            <div className="text-xs font-bold text-gray-700">{pb.wallet_count}</div>
          )}
        </div>
      </div>

      {pb.drivers.length > 0 && (
        <div className="mb-3">
          <div className="text-[9px] font-bold text-gray-400 uppercase tracking-wider mb-1">Why playbook</div>
          <div className="space-y-0.5">
            {pb.drivers.slice(0, 3).map((d, di) => (
              <div key={di} className="text-[10px] text-gray-500 flex items-center gap-1.5">
                <span className={`w-1 h-1 rounded-full ${cfg.dotColor}`} />
                {d}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Wallet addresses section */}
      {expanded && hasWalletAddresses && (
        <div className="mb-3">
          <div className="text-[9px] font-bold text-gray-400 uppercase tracking-wider mb-1.5">Wallets in cluster</div>
          <div className="space-y-0.5 pl-2 border-l-2 border-violet-500/20">
            {pb.wallet_addresses!.map((addr, wi) => (
              <div key={addr} className="flex items-center gap-2 group/w py-0.5" data-testid={`playbook-wallet-${index}-${wi}`}>
                <span className="text-[9px] text-gray-500 tabular-nums w-4">{wi + 1}.</span>
                <button
                  onClick={() => onNavigateToWallet?.(addr, 'playbook', { cluster: pb.signal_type, token: pb.token })}
                  className="text-[10px] text-violet-400 hover:text-violet-300 font-mono transition-colors"
                >
                  {addr.slice(0, 8)}...{addr.slice(-6)}
                </button>
                {chainId && (
                  <a href={addressUrl(addr, chainId)} target="_blank" rel="noopener noreferrer"
                    className="no-underline opacity-0 group-hover/w:opacity-100 transition-opacity">
                    <ExternalLink className="w-3 h-3 text-gray-500 hover:text-blue-400" />
                  </a>
                )}
                <button
                  onClick={() => {
                    navigator.clipboard.writeText(addr);
                    setCopiedIdx(wi);
                    setTimeout(() => setCopiedIdx(null), 1500);
                  }}
                  className="opacity-0 group-hover/w:opacity-100 transition-opacity"
                >
                  {copiedIdx === wi
                    ? <Check className="w-3 h-3 text-emerald-400" />
                    : <Copy className="w-3 h-3 text-gray-500 hover:text-gray-300" />}
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Legacy wallets display (from wallets array) — shown only if no wallet_addresses and not expanded */}
      {!expanded && pb.wallets.length > 0 && (
        <div>
          <div className="text-[9px] font-bold text-gray-400 uppercase tracking-wider mb-1.5">Wallets in cluster</div>
          <div className="space-y-1">
            {pb.wallets.slice(0, 3).map((w: any, wi: number) => (
              <div key={wi}
                className={`flex items-center justify-between ${onNavigateToWallet && w.address ? 'cursor-pointer hover:text-gray-900' : ''}`}
                onClick={() => w.address && onNavigateToWallet?.(w.address, 'playbook', { cluster: pb.signal_type, token: pb.token })}>
                <span className="text-[11px] text-violet-400 font-mono truncate max-w-[160px]">
                  {w.address ? `${w.address.slice(0, 8)}...${w.address.slice(-6)}` : w.name?.replace(/_/g, ' ')}
                </span>
                <div className="flex items-center gap-1">
                  <span className="text-[10px] text-gray-400">{STRATEGY_LABELS[w.strategy] || w.strategy} {w.confidence}%</span>
                  {w.address && onNavigateToWallet && <ArrowRight className="w-3 h-3 text-gray-300" />}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
