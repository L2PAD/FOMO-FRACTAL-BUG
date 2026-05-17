import React from 'react';
import { IntelligenceBlock } from '../../../../../components/intelligence';
import type { TokenScore, RotationPattern } from '../hooks/useTokenIntelligence';

export function TokenPositioning({ scores, patterns, loading }: {
  scores: TokenScore[];
  patterns: RotationPattern[];
  loading: boolean;
}) {
  if (loading && scores.length === 0) {
    return (
      <IntelligenceBlock testId="token-positioning">
        <div className="py-8 text-center">
          <div className="animate-spin w-5 h-5 border-2 border-gray-400 border-t-transparent rounded-full mx-auto" />
        </div>
      </IntelligenceBlock>
    );
  }

  const accCount = patterns.filter(p => p.pattern_type === 'accumulation').length;
  const distCount = patterns.filter(p => p.pattern_type === 'distribution').length;
  const rotCount = patterns.filter(p => p.pattern_type === 'rotation').length;
  const total = accCount + distCount + rotCount || 1;

  const accPct = Math.round((accCount / total) * 100);
  const distPct = Math.round((distCount / total) * 100);
  const rotPct = Math.round((rotCount / total) * 100);

  // Determine market phase
  const dominant = [
    { type: 'accumulation', pct: accPct },
    { type: 'distribution', pct: distPct },
    { type: 'rotation', pct: rotPct },
  ].sort((a, b) => b.pct - a.pct)[0];

  const phaseLabels: Record<string, { label: string; color: string }> = {
    accumulation: { label: 'Early Accumulation', color: 'text-emerald-600' },
    distribution: { label: 'Distribution Phase', color: 'text-red-600' },
    rotation: { label: 'Active Rotation', color: 'text-blue-600' },
  };
  const phase = phaseLabels[dominant.type] || phaseLabels.accumulation;

  return (
    <IntelligenceBlock testId="token-positioning">
      <h3 className="text-xs font-bold text-gray-400 uppercase tracking-wider mb-4">Smart Money Positioning</h3>

      <div className="space-y-3 mb-5">
        <PositionBar label="Accumulation" pct={accPct} color="bg-emerald-500" textColor="text-emerald-600" />
        <PositionBar label="Distribution" pct={distPct} color="bg-red-500" textColor="text-red-600" />
        <PositionBar label="Rotation" pct={rotPct} color="bg-blue-500" textColor="text-blue-600" />
      </div>

      <div className="pt-3">
        <div className="text-[10px] text-gray-400 mb-1">Market Phase</div>
        <div className={`text-lg font-bold ${phase.color}`} data-testid="positioning-phase">{phase.label}</div>
      </div>
    </IntelligenceBlock>
  );
}

function PositionBar({ label, pct, color, textColor }: { label: string; pct: number; color: string; textColor: string }) {
  return (
    <div>
      <div className="flex items-center justify-between mb-1">
        <span className="text-sm text-gray-700">{label}</span>
        <span className={`text-sm font-bold tabular-nums ${textColor}`}>{pct}%</span>
      </div>
      <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
        <div className={`h-full rounded-full ${color} transition-all duration-700`} style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}
