import React from 'react';
import { ArrowRight } from 'lucide-react';
import { IntelligenceBlock } from '../../../../../components/intelligence';
import type { DestinationHeat, RotationPattern } from '../hooks/useTokenIntelligence';

function fmtUsd(n: number): string {
  const abs = Math.abs(n);
  if (abs >= 1e9) return `$${(abs / 1e9).toFixed(1)}B`;
  if (abs >= 1e6) return `$${(abs / 1e6).toFixed(1)}M`;
  if (abs >= 1e3) return `$${(abs / 1e3).toFixed(1)}K`;
  return `$${abs.toFixed(0)}`;
}

interface FlowMapProps {
  heat: DestinationHeat[];
  patterns: RotationPattern[];
  loading: boolean;
  onSelectToken?: (token: string) => void;
}

export function TokenFlowHeat({ heat, patterns, loading, onSelectToken }: FlowMapProps) {
  if (loading && heat.length === 0) {
    return (
      <IntelligenceBlock testId="token-flow-heat">
        <div className="py-8 text-center">
          <div className="animate-spin w-5 h-5 border-2 border-gray-400 border-t-transparent rounded-full mx-auto" />
        </div>
      </IntelligenceBlock>
    );
  }

  if (heat.length === 0) return null;

  const maxFlow = Math.max(...heat.map(h => Math.abs(h.net_flow_usd)));
  const totalInflow = heat.filter(h => h.net_flow_usd > 0).reduce((s, h) => s + h.net_flow_usd, 0);
  const totalOutflow = heat.filter(h => h.net_flow_usd < 0).reduce((s, h) => s + Math.abs(h.net_flow_usd), 0);
  const totalAbsFlow = totalInflow + totalOutflow;

  const rotations = patterns.filter(p => p.pattern_type === 'rotation' && p.from_token && p.to_token);

  return (
    <IntelligenceBlock testId="token-flow-heat">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-xs font-bold text-gray-400 uppercase tracking-[0.15em]">Token Capital Flow</h3>
        <div className="flex items-center gap-4 text-[10px]">
          <span className="text-emerald-600 font-bold">Inflow +{fmtUsd(totalInflow)}</span>
          <span className="text-red-600 font-bold">Outflow -{fmtUsd(totalOutflow)}</span>
        </div>
      </div>

      {/* Rotation arrows */}
      {rotations.length > 0 && (
        <div className="mb-4 pb-3 border-b border-gray-100">
          <div className="text-[9px] font-bold text-gray-400 uppercase tracking-wider mb-2">Capital Rotation</div>
          <div className="flex flex-wrap gap-3">
            {rotations.slice(0, 3).map((r, i) => (
              <div key={i} className="flex items-center gap-1.5 bg-gray-50 rounded-lg px-3 py-1.5" data-testid={`flow-rotation-${i}`}>
                <span className="text-xs font-bold text-red-500">{r.from_token}</span>
                <ArrowRight className="w-3 h-3 text-gray-400" />
                <span className="text-xs font-bold text-emerald-600">{r.to_token}</span>
                <span className="text-[10px] text-gray-400 ml-1 tabular-nums">{fmtUsd(r.net_flow_usd)}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Flow bars */}
      <div className="space-y-2.5">
        {heat.slice(0, 8).map((h, i) => {
          const isPos = h.net_flow_usd > 0;
          const barWidth = Math.max(8, (Math.abs(h.net_flow_usd) / maxFlow) * 100);
          const pctShare = totalAbsFlow > 0 ? (Math.abs(h.net_flow_usd) / totalAbsFlow) * 100 : 0;

          return (
            <div key={h.token} data-testid={`flow-heat-${i}`}
              className={onSelectToken ? 'cursor-pointer hover:bg-gray-50 rounded-lg px-2 py-1 -mx-2 transition-colors' : ''}
              onClick={() => onSelectToken?.(h.token)}>
              <div className="flex items-center justify-between mb-1">
                <div className="flex items-center gap-2.5">
                  <span className="text-sm font-black text-gray-900">{h.token}</span>
                  <span className="text-[10px] font-bold text-gray-400 tabular-nums" data-testid={`flow-share-${i}`}>
                    {pctShare.toFixed(1)}%
                  </span>
                </div>
                <span className={`text-sm font-black tabular-nums ${isPos ? 'text-emerald-600' : 'text-red-600'}`}>
                  {isPos ? '+' : '-'}{fmtUsd(h.net_flow_usd)}
                </span>
              </div>
              <div className="h-2.5 bg-gray-100 rounded-full overflow-hidden">
                <div
                  className={`h-full rounded-full transition-all duration-700 ${isPos ? 'bg-emerald-400' : 'bg-red-400'}`}
                  style={{ width: `${barWidth}%` }}
                />
              </div>
            </div>
          );
        })}
      </div>
    </IntelligenceBlock>
  );
}
