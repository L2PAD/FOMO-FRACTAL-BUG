import React from 'react';
import { IntelligenceBlock } from '../../../../../components/intelligence';
import type { TokenScore, RotationPattern } from '../hooks/useTokenIntelligence';

function fmtUsd(n: number): string {
  const abs = Math.abs(n);
  if (abs >= 1e9) return `$${(abs / 1e9).toFixed(1)}B`;
  if (abs >= 1e6) return `$${(abs / 1e6).toFixed(1)}M`;
  if (abs >= 1e3) return `$${(abs / 1e3).toFixed(1)}K`;
  return `$${abs.toFixed(0)}`;
}

export function MarketPressure({ scores, loading }: { scores: TokenScore[]; loading: boolean }) {
  if (loading && scores.length === 0) {
    return (
      <IntelligenceBlock dark testId="market-pressure">
        <div className="py-8 text-center">
          <div className="animate-spin w-5 h-5 border-2 border-emerald-400 border-t-transparent rounded-full mx-auto" />
        </div>
      </IntelligenceBlock>
    );
  }

  const totalBuy = scores.reduce((s, t) => s + Math.max(0, t.net_flow_usd), 0);
  const totalSell = scores.reduce((s, t) => s + Math.abs(Math.min(0, t.net_flow_usd)), 0);
  const netFlow = totalBuy - totalSell;
  const total = totalBuy + totalSell || 1;
  const buyPct = Math.round((totalBuy / total) * 100);
  const sellPct = 100 - buyPct;
  const isBullish = buyPct > 50;

  return (
    <IntelligenceBlock dark testId="market-pressure">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-xs font-bold text-gray-400 uppercase tracking-wider">Market Pressure</h3>
        <span className={`text-xs font-bold ${isBullish ? 'text-emerald-400' : 'text-red-400'}`}>
          {isBullish ? 'BUY DOMINANT' : 'SELL DOMINANT'}
        </span>
      </div>

      <div className="mb-4">
        <div className="flex justify-between text-[10px] text-gray-500 mb-1.5">
          <span>Buying Pressure</span>
          <span>Selling Pressure</span>
        </div>
        <div className="h-3 rounded-full bg-gray-800 overflow-hidden flex">
          <div className="h-full bg-emerald-400 rounded-l-full transition-all duration-700" style={{ width: `${buyPct}%` }} />
          <div className="h-full bg-red-400 rounded-r-full transition-all duration-700" style={{ width: `${sellPct}%` }} />
        </div>
        <div className="flex justify-between text-xs font-bold mt-1.5">
          <span className="text-emerald-400">{buyPct}%</span>
          <span className="text-red-400">{sellPct}%</span>
        </div>
      </div>

      <div className="space-y-2.5 pt-2">
        <div className="flex items-center justify-between">
          <span className="text-[11px] text-gray-500">Smart Money Buying</span>
          <span className="text-sm font-bold text-emerald-400 tabular-nums">+{fmtUsd(totalBuy)}</span>
        </div>
        <div className="flex items-center justify-between">
          <span className="text-[11px] text-gray-500">Smart Money Selling</span>
          <span className="text-sm font-bold text-red-400 tabular-nums">-{fmtUsd(totalSell)}</span>
        </div>
        <div className="flex items-center justify-between pt-1">
          <span className="text-[11px] text-gray-500">Net Flow</span>
          <span className={`text-sm font-bold tabular-nums ${netFlow >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
            {netFlow >= 0 ? '+' : ''}{fmtUsd(netFlow)}
          </span>
        </div>
      </div>
    </IntelligenceBlock>
  );
}
