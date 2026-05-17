import React from 'react';
import { IntelligenceBlock } from '../../../../../components/intelligence';
import type { TokenScore, DestinationHeat } from '../hooks/useTokenIntelligence';

function fmtUsd(n: number): string {
  const abs = Math.abs(n);
  if (abs >= 1e9) return `$${(abs / 1e9).toFixed(1)}B`;
  if (abs >= 1e6) return `$${(abs / 1e6).toFixed(1)}M`;
  if (abs >= 1e3) return `$${(abs / 1e3).toFixed(1)}K`;
  return `$${abs.toFixed(0)}`;
}

export function LiquidityAbsorption({ scores, heat, loading }: {
  scores: TokenScore[];
  heat: DestinationHeat[];
  loading: boolean;
}) {
  if (loading && scores.length === 0) {
    return (
      <IntelligenceBlock testId="liquidity-absorption">
        <div className="py-8 text-center">
          <div className="animate-spin w-5 h-5 border-2 border-gray-400 border-t-transparent rounded-full mx-auto" />
        </div>
      </IntelligenceBlock>
    );
  }

  const totalFlow = heat.reduce((s, h) => s + Math.abs(h.net_flow_usd), 0);
  const smartInflow = heat.filter(h => h.net_flow_usd > 0).reduce((s, h) => s + h.net_flow_usd, 0);
  const positiveTokens = heat.filter(h => h.net_flow_usd > 0).length;
  const totalTokens = heat.length || 1;

  // Top token concentration
  const topConcentration = heat.length > 0 ? Math.abs(heat[0]?.net_flow_usd || 0) / totalFlow * 100 : 0;

  // Pool depth heuristic: based on total flow magnitude
  const poolDepth = totalFlow >= 100_000_000 ? 'HIGH' : totalFlow >= 10_000_000 ? 'MODERATE' : 'LOW';
  const poolColor = poolDepth === 'HIGH' ? 'text-emerald-600' : poolDepth === 'MODERATE' ? 'text-amber-600' : 'text-gray-500';

  // Price impact heuristic: high concentration = higher impact
  const priceImpact = topConcentration >= 80 ? 'HIGH' : topConcentration >= 50 ? 'MODERATE' : 'LOW';
  const impactColor = priceImpact === 'LOW' ? 'text-emerald-600' : priceImpact === 'MODERATE' ? 'text-amber-600' : 'text-red-600';

  // Absorption level
  const absorptionPct = Math.min(95, Math.round(topConcentration + (positiveTokens / totalTokens) * 30));
  const absLevel = absorptionPct >= 70 ? 'HIGH' : absorptionPct >= 45 ? 'MODERATE' : 'LOW';
  const absColor = absorptionPct >= 70 ? 'text-emerald-600' : absorptionPct >= 45 ? 'text-amber-600' : 'text-gray-500';
  const barColor = absorptionPct >= 70 ? 'bg-emerald-500' : absorptionPct >= 45 ? 'bg-amber-500' : 'bg-gray-400';

  return (
    <IntelligenceBlock testId="liquidity-absorption">
      <h3 className="text-xs font-bold text-gray-400 uppercase tracking-[0.15em] mb-4">Liquidity Absorption</h3>

      <div className="space-y-3">
        {/* Key metrics grid */}
        <div className="grid grid-cols-2 gap-3">
          <div>
            <div className="text-[9px] font-bold text-gray-400 uppercase tracking-wider mb-0.5">Smart Inflow</div>
            <div className="text-xl font-black text-emerald-600 tabular-nums">{fmtUsd(smartInflow)}</div>
          </div>
          <div>
            <div className="text-[9px] font-bold text-gray-400 uppercase tracking-wider mb-0.5">Pool Depth</div>
            <div className={`text-xl font-black ${poolColor}`}>{poolDepth}</div>
          </div>
          <div>
            <div className="text-[9px] font-bold text-gray-400 uppercase tracking-wider mb-0.5">Price Impact</div>
            <div className={`text-lg font-black ${impactColor}`}>{priceImpact}</div>
          </div>
          <div>
            <div className="text-[9px] font-bold text-gray-400 uppercase tracking-wider mb-0.5">Concentration</div>
            <div className="text-lg font-black text-gray-700 tabular-nums">{topConcentration.toFixed(0)}%</div>
          </div>
        </div>

        {/* Absorption bar */}
        <div className="pt-2">
          <div className="flex items-center justify-between mb-1">
            <span className="text-[9px] font-bold text-gray-400 uppercase tracking-wider">Absorption Level</span>
            <span className={`text-xs font-black ${absColor}`} data-testid="absorption-level">{absLevel}</span>
          </div>
          <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
            <div className={`h-full rounded-full ${barColor} transition-all duration-700`} style={{ width: `${absorptionPct}%` }} />
          </div>
        </div>
      </div>
    </IntelligenceBlock>
  );
}
