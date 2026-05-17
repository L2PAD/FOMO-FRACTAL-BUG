import React, { useState } from 'react';
import { TrendingUp, TrendingDown, ArrowRight, AlertCircle, Activity, ChevronDown, ChevronRight, ExternalLink, Copy, Check } from 'lucide-react';
import { fmtUsd } from '../helpers';
import { addressUrl } from '../../../utils/explorer';
import type { PatternEvent } from '../types/smartMoney';

const patternConfig: Record<string, { icon: React.ReactNode; label: string; color: string }> = {
  accumulation: { icon: <TrendingUp className="w-5 h-5" />, label: 'Accumulation', color: 'text-emerald-600' },
  distribution: { icon: <TrendingDown className="w-5 h-5" />, label: 'Distribution', color: 'text-red-600' },
  rotation: { icon: <ArrowRight className="w-5 h-5" />, label: 'Rotation', color: 'text-blue-600' },
  exit: { icon: <AlertCircle className="w-5 h-5" />, label: 'Exit', color: 'text-amber-600' },
};

export function SmartMoneyPatternsBlock({ patterns, loading, onOpenWallet, chainId }: {
  patterns: PatternEvent[];
  loading: boolean;
  onOpenWallet?: (addr: string) => void;
  chainId?: number;
}) {
  if (loading && patterns.length === 0) {
    return (
      <div className="rounded-2xl bg-white p-6 text-center" data-testid="patterns-block">
        <div className="animate-spin w-6 h-6 border-2 border-gray-900 border-t-transparent rounded-full mx-auto" />
        <p className="text-gray-400 mt-3 text-sm">Detecting patterns...</p>
      </div>
    );
  }
  if (patterns.length === 0) return null;

  return (
    <div className="rounded-2xl bg-white overflow-hidden" data-testid="patterns-block">
      <div className="px-6 py-4 flex items-center gap-3">
        <div className="w-9 h-9 flex items-center justify-center">
          <Activity className="w-5 h-5 text-blue-400" />
        </div>
        <div>
          <h3 className="font-bold text-gray-900">Smart Money Market Phases</h3>
          <p className="text-xs text-gray-400">Detected market phases from smart money behavior</p>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4 p-6">
        {patterns.map((p, i) => (
          <PatternCard key={`${p.pattern_type}-${p.token}-${i}`} pattern={p} index={i} onOpenWallet={onOpenWallet} chainId={chainId} />
        ))}
      </div>
    </div>
  );
}

function PatternCard({ pattern: p, index: i, onOpenWallet, chainId }: {
  pattern: PatternEvent;
  index: number;
  onOpenWallet?: (addr: string) => void;
  chainId?: number;
}) {
  const [expanded, setExpanded] = useState(false);
  const [copiedIdx, setCopiedIdx] = useState<number | null>(null);
  const cfg = patternConfig[p.pattern_type] || patternConfig.accumulation;
  const isPositive = p.net_flow_usd > 0;
  const confColor = p.confidence >= 70 ? 'bg-emerald-500' : p.confidence >= 50 ? 'bg-amber-500' : 'bg-gray-400';
  const isRotation = p.pattern_type === 'rotation';
  const hasWallets = p.wallet_addresses && p.wallet_addresses.length > 0;

  return (
    <div className="p-4 transition-colors" data-testid={`pattern-card-${i + 1}`}>
      <div className="flex items-center gap-2 mb-3">
        <span className={cfg.color}>{cfg.icon}</span>
        <span className={`text-xs font-bold uppercase tracking-wider ${cfg.color}`}>{cfg.label} detected</span>
      </div>

      {isRotation ? (
        <div className="flex items-center gap-2 mb-2">
          <span className="text-lg font-bold text-gray-900">{p.from_token}</span>
          <ArrowRight className="w-4 h-4 text-gray-400" />
          <span className="text-lg font-bold text-gray-900">{p.to_token}</span>
        </div>
      ) : (
        <div className="text-lg font-bold text-gray-900 mb-2">{p.token}</div>
      )}

      <div className="flex items-center gap-4 mb-3">
        <div>
          <div className="text-[10px] text-gray-400">Net flow</div>
          <div className={`text-sm font-bold ${isPositive ? 'text-emerald-600' : 'text-red-600'}`}>
            {isPositive ? '+' : ''}{fmtUsd(p.net_flow_usd)}
          </div>
        </div>
        <div>
          <div className="text-[10px] text-gray-400">Confidence</div>
          <div className="flex items-center gap-1.5">
            <div className="w-12 h-1.5 bg-white/60 rounded-full overflow-hidden">
              <div className={`h-full rounded-full ${confColor}`} style={{ width: `${p.confidence}%` }} />
            </div>
            <span className="text-xs font-bold text-gray-700">{p.confidence}%</span>
          </div>
        </div>
        <div>
          <div className="text-[10px] text-gray-400">Wallets</div>
          {hasWallets ? (
            <button
              onClick={() => setExpanded(!expanded)}
              className="text-xs font-bold text-violet-500 hover:text-violet-400 flex items-center gap-0.5 transition-colors"
              data-testid={`pattern-expand-wallets-${i}`}
            >
              {expanded ? <ChevronDown className="w-3 h-3" /> : <ChevronRight className="w-3 h-3" />}
              {p.wallet_count}
            </button>
          ) : (
            <div className="text-xs font-bold text-gray-700">{p.wallet_count}</div>
          )}
        </div>
      </div>

      {p.drivers.length > 0 && (
        <div className="space-y-0.5">
          {p.drivers.slice(0, 3).map((d, di) => (
            <div key={di} className="text-[11px] text-gray-600 flex items-center gap-1.5">
              <span className={`w-1 h-1 rounded-full ${cfg.color.replace('text-', 'bg-')}`} />
              {d}
            </div>
          ))}
        </div>
      )}

      {expanded && hasWallets && (
        <div className="mt-2 space-y-1 pl-3 border-l-2 border-violet-500/20">
          {p.wallet_addresses!.map((addr, wi) => (
            <div key={addr} className="flex items-center gap-2 group/w py-0.5" data-testid={`pattern-wallet-${i}-${wi}`}>
              <span className="text-[9px] text-gray-500 tabular-nums w-4">{wi + 1}.</span>
              <button
                onClick={() => onOpenWallet?.(addr)}
                className="text-[10px] text-violet-400 hover:text-violet-300 font-mono transition-colors"
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
      )}

      <div className="mt-3 flex gap-2">
        {!isRotation && p.token !== 'STABLECOINS' && (
          <button onClick={() => { globalThis.window.location.href = `/intelligence/onchain-v3?tab=assets&token=${p.token}`; }}
            className="text-[11px] font-semibold text-gray-500 hover:text-gray-900 transition-colors"
            data-testid={`pattern-view-token-${i + 1}`}>View Token</button>
        )}
        {isRotation && (
          <>
            <button onClick={() => { globalThis.window.location.href = `/intelligence/onchain-v3?tab=assets&token=${p.from_token}`; }}
              className="text-[11px] font-semibold text-gray-500 hover:text-gray-900 transition-colors">
              {p.from_token}
            </button>
            <button onClick={() => { globalThis.window.location.href = `/intelligence/onchain-v3?tab=assets&token=${p.to_token}`; }}
              className="text-[11px] font-semibold text-gray-500 hover:text-gray-900 transition-colors">
              {p.to_token}
            </button>
          </>
        )}
      </div>
    </div>
  );
}
