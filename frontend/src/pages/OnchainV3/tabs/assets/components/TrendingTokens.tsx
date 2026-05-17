import React from 'react';
import { TrendingUp, TrendingDown } from 'lucide-react';
import { IntelligenceBlock } from '../../../../../components/intelligence';
import type { TokenScore } from '../hooks/useTokenIntelligence';

function fmtUsd(n: number): string {
  const abs = Math.abs(n);
  if (abs >= 1e9) return `$${(abs / 1e9).toFixed(1)}B`;
  if (abs >= 1e6) return `$${(abs / 1e6).toFixed(1)}M`;
  if (abs >= 1e3) return `$${(abs / 1e3).toFixed(1)}K`;
  return `$${abs.toFixed(0)}`;
}

export function TrendingTokens({ scores, loading, onSelectToken }: {
  scores: TokenScore[];
  loading: boolean;
  onSelectToken: (token: string) => void;
}) {
  if (loading && scores.length === 0) {
    return (
      <IntelligenceBlock dark testId="trending-tokens">
        <div className="py-8 text-center">
          <div className="animate-spin w-5 h-5 border-2 border-emerald-400 border-t-transparent rounded-full mx-auto" />
        </div>
      </IntelligenceBlock>
    );
  }

  const sorted = [...scores].sort((a, b) => b.alpha_score - a.alpha_score);

  return (
    <IntelligenceBlock dark testId="trending-tokens">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-xs font-bold text-gray-400 uppercase tracking-[0.15em]">Trending Tokens</h3>
        <span className="text-[10px] text-gray-500">by Smart Money Flow</span>
      </div>

      {sorted.length === 0 ? (
        <p className="text-sm text-gray-500 text-center py-4">No token data</p>
      ) : (
        <div className="space-y-2.5">
          {sorted.map((t, i) => {
            const scoreColor = t.alpha_score >= 60 ? 'text-emerald-400' : t.alpha_score >= 40 ? 'text-amber-400' : 'text-red-400';
            const barColor = t.alpha_score >= 60 ? 'bg-emerald-400' : t.alpha_score >= 40 ? 'bg-amber-400' : 'bg-red-400';
            const isPositive = t.net_flow_usd >= 0;
            // Momentum: derived from alpha score distance from neutral (50)
            const momentum = t.alpha_score - 50;
            const momentumLabel = momentum > 0 ? `+${momentum}%` : `${momentum}%`;
            const MomentumIcon = momentum >= 0 ? TrendingUp : TrendingDown;

            return (
              <div
                key={t.token}
                onClick={() => onSelectToken(t.token)}
                className="flex items-center gap-3 py-2 cursor-pointer hover:bg-gray-800/40 rounded-lg px-2 -mx-2 transition-colors"
                data-testid={`trending-token-${i}`}
              >
                <span className="text-xs text-gray-500 w-4 text-right tabular-nums">{i + 1}</span>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-0.5">
                    <span className="text-sm font-bold text-white">{t.token}</span>
                    <span className={`text-[10px] font-bold capitalize ${
                      t.pattern === 'accumulation' ? 'text-emerald-400' :
                      t.pattern === 'distribution' ? 'text-red-400' : 'text-gray-400'
                    }`}>{t.pattern}</span>
                  </div>
                  <div className="flex items-center gap-3">
                    <span className={`text-[10px] font-bold tabular-nums ${isPositive ? 'text-emerald-400' : 'text-red-400'}`}>
                      Smart Flow {isPositive ? '+' : ''}{fmtUsd(t.net_flow_usd)}
                    </span>
                    <span className={`flex items-center gap-0.5 text-[10px] font-bold tabular-nums ${momentum >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                      <MomentumIcon className="w-3 h-3" />
                      {momentumLabel}
                    </span>
                  </div>
                </div>
                <div className="flex items-center gap-2 flex-shrink-0">
                  <div className="w-12 h-1.5 bg-gray-700 rounded-full overflow-hidden">
                    <div className={`h-full rounded-full ${barColor}`} style={{ width: `${t.alpha_score}%` }} />
                  </div>
                  <span className={`text-sm font-bold tabular-nums w-8 text-right ${scoreColor}`}>{t.alpha_score}</span>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </IntelligenceBlock>
  );
}
