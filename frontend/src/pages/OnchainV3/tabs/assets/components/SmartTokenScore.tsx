import React, { useState } from 'react';
import { ExternalLink, ChevronDown, ChevronRight } from 'lucide-react';
import { IntelligenceBlock } from '../../../../../components/intelligence';
import type { TokenScore as TScore } from '../hooks/useTokenIntelligence';

const shortAddr = (a: string) => a ? `${a.slice(0, 6)}...${a.slice(-4)}` : '';

function fmtUsd(n: number): string {
  const abs = Math.abs(n);
  if (abs >= 1e9) return `$${(abs / 1e9).toFixed(1)}B`;
  if (abs >= 1e6) return `$${(abs / 1e6).toFixed(1)}M`;
  if (abs >= 1e3) return `$${(abs / 1e3).toFixed(1)}K`;
  return `$${abs.toFixed(0)}`;
}

const DRIVER_LABELS = [
  { key: 'flow', label: 'Smart Flow', max: 20 },
  { key: 'wallet', label: 'Wallet Quality', max: 25 },
  { key: 'timing', label: 'Timing Edge', max: 20 },
  { key: 'cluster', label: 'Cluster Activity', max: 20 },
  { key: 'pattern', label: 'Pattern Signal', max: 15 },
];

export function SmartTokenScore({ scores, loading, onSelectToken }: { scores: TScore[]; loading: boolean; onSelectToken?: (token: string) => void }) {
  const [showWallets, setShowWallets] = useState(false);
  if (loading && scores.length === 0) {
    return (
      <IntelligenceBlock dark testId="smart-token-score">
        <div className="py-8 text-center">
          <div className="animate-spin w-5 h-5 border-2 border-emerald-400 border-t-transparent rounded-full mx-auto" />
        </div>
      </IntelligenceBlock>
    );
  }

  const sorted = [...scores].sort((a, b) => b.alpha_score - a.alpha_score);
  const top = sorted[0];
  if (!top) return null;

  const scoreColor = top.alpha_score >= 70 ? 'text-emerald-400' : top.alpha_score >= 50 ? 'text-amber-400' : 'text-red-400';
  const components = (top as any).components || {};

  return (
    <IntelligenceBlock dark testId="smart-token-score">
      <h3 className="text-xs font-bold text-gray-400 uppercase tracking-[0.15em] mb-3">Smart Token Score</h3>

      <div className="flex items-start justify-between mb-3">
        <div>
          <div className={`text-lg font-black text-white ${onSelectToken ? 'cursor-pointer hover:text-emerald-400 transition-colors' : ''}`}
            onClick={() => onSelectToken?.(top.token)} data-testid="score-token-name">{top.token}</div>
          <div className={`text-[10px] font-bold uppercase ${
            top.pattern === 'accumulation' ? 'text-emerald-400' :
            top.pattern === 'distribution' ? 'text-red-400' : 'text-gray-400'
          }`}>{top.pattern}</div>
        </div>
        <div className="text-right">
          <div className={`text-4xl font-black tabular-nums ${scoreColor}`} data-testid="score-alpha">{top.alpha_score}</div>
          <div className="text-[9px] text-gray-500">/ 100</div>
        </div>
      </div>

      {/* Driver breakdown bars */}
      <div className="space-y-2 pt-2 border-t border-gray-800">
        <div className="text-[9px] font-bold text-gray-500 uppercase tracking-wider pt-2 mb-1">Drivers</div>
        {DRIVER_LABELS.map(({ key, label, max }) => {
          const val = Math.abs(components[key] || 0);
          const pct = Math.min(100, (val / max) * 100);
          const isNeg = (components[key] || 0) < 0;
          const barCol = isNeg ? 'bg-red-400' : pct >= 70 ? 'bg-emerald-400' : pct >= 40 ? 'bg-amber-400' : 'bg-gray-600';
          // Map to user-friendly score (0-100 scale)
          const displayScore = Math.round(pct);
          return (
            <div key={key}>
              <div className="flex items-center justify-between mb-0.5">
                <span className="text-[10px] text-gray-500">{label}</span>
                <span className="text-[10px] text-gray-400 tabular-nums font-bold">{displayScore}</span>
              </div>
              <div className="h-1 bg-gray-800 rounded-full overflow-hidden">
                <div className={`h-full rounded-full ${barCol} transition-all duration-700`} style={{ width: `${pct}%` }} />
              </div>
            </div>
          );
        })}
      </div>

      {/* Wallet Addresses */}
      {top.wallet_addresses && top.wallet_addresses.length > 0 && (
        <div className="pt-2 border-t border-gray-800 mt-2">
          <button onClick={() => setShowWallets(!showWallets)}
            className="text-[10px] text-violet-400 hover:text-violet-300 font-semibold flex items-center gap-0.5 transition-colors"
            data-testid="score-wallets-expand">
            {showWallets ? <ChevronDown className="w-3 h-3" /> : <ChevronRight className="w-3 h-3" />}
            {top.wallet_count} active wallets
          </button>
          {showWallets && (
            <div className="mt-1 space-y-0.5 pl-2 border-l-2 border-violet-500/20">
              {top.wallet_addresses.map((addr, i) => (
                <div key={addr} className="flex items-center gap-2 py-0.5 group/tw" data-testid={`score-wallet-${i}`}>
                  <span className="text-[9px] text-gray-600 tabular-nums w-3">{i + 1}.</span>
                  <a href={`https://etherscan.io/address/${addr}`} target="_blank" rel="noopener noreferrer"
                    className="text-[10px] text-violet-400 font-mono hover:underline">
                    {shortAddr(addr)}
                  </a>
                  <a href={`https://etherscan.io/address/${addr}`} target="_blank" rel="noopener noreferrer"
                    className="opacity-0 group-hover/tw:opacity-100 transition-opacity">
                    <ExternalLink className="w-2.5 h-2.5 text-gray-500 hover:text-blue-400" />
                  </a>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </IntelligenceBlock>
  );
}
