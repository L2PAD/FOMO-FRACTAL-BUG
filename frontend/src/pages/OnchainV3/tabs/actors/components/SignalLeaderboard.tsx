import React, { useMemo, useState } from 'react';
import { Trophy, ChevronDown, ChevronRight, ExternalLink, Copy, Check } from 'lucide-react';
import { Tooltip, TooltipTrigger, TooltipContent } from '../../../../../components/ui/tooltip';
import { addressUrl } from '../../../utils/explorer';
import type { AlphaSignal } from '../types/smartMoney';

const SIGNAL_TYPE_CONFIG: Record<string, { label: string; color: string; dotColor: string }> = {
  accumulation: { label: 'Accumulation', color: 'text-emerald-600', dotColor: 'bg-emerald-500' },
  distribution: { label: 'Distribution', color: 'text-red-600', dotColor: 'bg-red-500' },
  rotation: { label: 'Rotation', color: 'text-blue-600', dotColor: 'bg-blue-500' },
  momentum: { label: 'Momentum', color: 'text-purple-600', dotColor: 'bg-purple-500' },
  weakening: { label: 'Weakening', color: 'text-amber-600', dotColor: 'bg-amber-500' },
  cluster_activity: { label: 'Cluster', color: 'text-cyan-600', dotColor: 'bg-cyan-500' },
  exit: { label: 'Exit', color: 'text-amber-600', dotColor: 'bg-amber-500' },
};

export function ConvictionLeaderboard({ signals, loading, onNavigateToWallet, chainId }: {
  signals: AlphaSignal[];
  loading: boolean;
  onNavigateToWallet?: (address: string, src: string, params?: Record<string, string>) => void;
  chainId?: number;
}) {
  const top = useMemo(() =>
    [...signals].sort((a, b) => b.conviction - a.conviction).slice(0, 5),
    [signals]
  );

  if (loading && top.length === 0) return null;
  if (top.length === 0) return null;

  return (
    <div className="rounded-2xl bg-white overflow-hidden" data-testid="conviction-leaderboard">
      <div className="px-6 py-4 flex items-center gap-3">
        <Trophy className="w-5 h-5 text-amber-500" />
        <div>
          <h3 className="font-bold text-gray-900">Top Smart Money Signals</h3>
          <p className="text-xs text-gray-400">Ranked by conviction strength</p>
        </div>
      </div>

      <div className="px-6 pb-5 space-y-0">
        {top.map((sig, i) => (
          <LeaderboardRow
            key={sig.signal_id}
            sig={sig}
            index={i}
            onNavigateToWallet={onNavigateToWallet}
            chainId={chainId}
          />
        ))}
      </div>
    </div>
  );
}

function LeaderboardRow({ sig, index, onNavigateToWallet, chainId }: {
  sig: AlphaSignal;
  index: number;
  onNavigateToWallet?: (address: string, src: string, params?: Record<string, string>) => void;
  chainId?: number;
}) {
  const [expanded, setExpanded] = useState(false);
  const [copiedIdx, setCopiedIdx] = useState<number | null>(null);
  const cfg = SIGNAL_TYPE_CONFIG[sig.signal_type] || SIGNAL_TYPE_CONFIG.accumulation;
  const convictionColor = sig.conviction >= 60 ? 'text-emerald-600' : sig.conviction >= 50 ? 'text-amber-600' : 'text-gray-500';
  const barColor = sig.conviction >= 60 ? 'bg-emerald-500' : sig.conviction >= 50 ? 'bg-amber-500' : 'bg-gray-400';
  const isRotation = sig.signal_type === 'rotation';
  const rankColors = ['text-amber-500', 'text-gray-400', 'text-amber-700', 'text-gray-400', 'text-gray-400'];
  const hasWallets = sig.wallet_addresses && sig.wallet_addresses.length > 0;

  return (
    <div className="py-3" data-testid={`leaderboard-${index + 1}`}>
      <div className="flex items-center gap-4">
        <span className={`text-lg font-black tabular-nums w-6 ${rankColors[index] || 'text-gray-400'}`}>
          {index + 1}
        </span>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-0.5">
            {isRotation ? (
              <span className="text-sm font-bold text-gray-900">{sig.from_token} -> {sig.to_token}</span>
            ) : (
              <span className="text-sm font-bold text-gray-900">{sig.token}</span>
            )}
            <span className={`text-[10px] font-bold uppercase ${cfg.color}`}>{cfg.label}</span>
          </div>
          <div className="flex items-center gap-2 text-[10px] text-gray-400">
            <span>{sig.capital_fmt}</span>
            <span>&#183;</span>
            {hasWallets ? (
              <button
                onClick={() => setExpanded(!expanded)}
                className="text-violet-500 hover:text-violet-400 font-semibold flex items-center gap-0.5 transition-colors"
                data-testid={`leaderboard-expand-${index}`}
              >
                {expanded ? <ChevronDown className="w-3 h-3" /> : <ChevronRight className="w-3 h-3" />}
                {sig.wallet_count} wallets
              </button>
            ) : (
              <span>{sig.wallet_count} wallets</span>
            )}
          </div>
        </div>
        <div className="flex items-center gap-2">
          <div className="w-16 h-1.5 bg-gray-100 rounded-full overflow-hidden">
            <div className={`h-full rounded-full ${barColor}`} style={{ width: `${sig.conviction}%` }} />
          </div>
          <span className={`text-sm font-bold tabular-nums w-10 text-right ${convictionColor}`}>
            {sig.conviction}%
          </span>
        </div>
      </div>

      {expanded && hasWallets && (
        <div className="ml-10 mt-2 space-y-1 pl-3 border-l-2 border-violet-500/20">
          {sig.wallet_addresses!.map((addr, i) => (
            <div key={addr} className="flex items-center gap-2 group/w py-0.5" data-testid={`leaderboard-wallet-${index}-${i}`}>
              <span className="text-[9px] text-gray-500 tabular-nums w-4">{i + 1}.</span>
              <button
                onClick={() => onNavigateToWallet?.(addr, 'leaderboard')}
                className="text-[10px] text-violet-400 hover:text-violet-300 font-mono transition-colors"
                data-testid={`leaderboard-wallet-link-${index}-${i}`}
              >
                {addr.slice(0, 8)}...{addr.slice(-6)}
              </button>
              {chainId && (
                <a href={addressUrl(addr, chainId)} target="_blank" rel="noopener noreferrer"
                  className="opacity-0 group-hover/w:opacity-100 transition-opacity">
                  <ExternalLink className="w-3 h-3 text-gray-500 hover:text-blue-400" />
                </a>
              )}
              <button
                onClick={() => {
                  navigator.clipboard.writeText(addr);
                  setCopiedIdx(i);
                  setTimeout(() => setCopiedIdx(null), 1500);
                }}
                className="opacity-0 group-hover/w:opacity-100 transition-opacity"
              >
                {copiedIdx === i
                  ? <Check className="w-3 h-3 text-emerald-400" />
                  : <Copy className="w-3 h-3 text-gray-500 hover:text-gray-300" />}
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
