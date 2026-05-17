import React from 'react';
import { IntelligenceBlock } from '../../../../../components/intelligence';
import type { TokenScore, RotationPattern, Narrative } from '../hooks/useTokenIntelligence';

const PHASE_CONFIG: Record<string, { label: string; color: string }> = {
  accumulation: { label: 'Early Accumulation', color: 'text-emerald-600' },
  distribution: { label: 'Distribution', color: 'text-red-600' },
  rotation: { label: 'Capital Rotation', color: 'text-blue-600' },
  momentum: { label: 'Momentum', color: 'text-purple-600' },
  neutral: { label: 'Neutral', color: 'text-gray-500' },
};

export function TokenRegime({ scores, patterns, narrative, loading }: {
  scores: TokenScore[];
  patterns: RotationPattern[];
  narrative: Narrative | null;
  loading: boolean;
}) {
  if (loading && scores.length === 0) {
    return (
      <IntelligenceBlock testId="token-regime">
        <div className="py-8 text-center">
          <div className="animate-spin w-5 h-5 border-2 border-gray-400 border-t-transparent rounded-full mx-auto" />
        </div>
      </IntelligenceBlock>
    );
  }

  // Dominant phase
  const patternCounts: Record<string, number> = {};
  patterns.forEach(p => { patternCounts[p.pattern_type] = (patternCounts[p.pattern_type] || 0) + 1; });
  const dominantPhase = Object.entries(patternCounts).sort((a, b) => b[1] - a[1])[0]?.[0] || 'neutral';

  // Momentum: average alpha score
  const avgScore = scores.length > 0 ? scores.reduce((s, t) => s + t.alpha_score, 0) / scores.length : 0;
  const momentum = avgScore >= 65 ? 'Strong' : avgScore >= 45 ? 'Moderate' : 'Weak';
  const momColor = avgScore >= 65 ? 'text-emerald-600' : avgScore >= 45 ? 'text-amber-600' : 'text-gray-500';

  // Bias
  const bias = narrative?.bias || 'neutral';
  const biasConfig: Record<string, { label: string; color: string }> = {
    bullish: { label: 'Bullish', color: 'text-emerald-600' },
    bearish: { label: 'Bearish', color: 'text-red-600' },
    neutral: { label: 'Neutral', color: 'text-gray-500' },
  };
  const bc = biasConfig[bias] || biasConfig.neutral;

  // Volatility heuristic: if scores vary widely → high volatility
  const maxScore = Math.max(...scores.map(s => s.alpha_score), 0);
  const minScore = Math.min(...scores.map(s => s.alpha_score), 100);
  const spread = maxScore - minScore;
  const volatility = spread >= 30 ? 'High' : spread >= 15 ? 'Moderate' : 'Low';
  const volColor = volatility === 'Low' ? 'text-emerald-600' : volatility === 'Moderate' ? 'text-amber-600' : 'text-red-600';

  // Breakout probability: composite heuristic
  const bullishTokens = scores.filter(s => s.signal === 'strong_bullish' || s.signal === 'bullish').length;
  const totalTokens = scores.length || 1;
  const confidence = narrative?.confidence || 50;
  const avgTiming = scores.length > 0 ? scores.reduce((s, t) => s + t.avg_timing, 0) / scores.length : 0;
  const breakoutPct = Math.min(95, Math.round(
    (bullishTokens / totalTokens) * 30 +
    (confidence / 100) * 25 +
    (avgScore / 100) * 25 +
    Math.min(20, (avgTiming / 15) * 20)
  ));
  const breakoutColor = breakoutPct >= 60 ? 'text-emerald-600' : breakoutPct >= 40 ? 'text-amber-600' : 'text-gray-500';
  const breakoutBar = breakoutPct >= 60 ? 'bg-emerald-500' : breakoutPct >= 40 ? 'bg-amber-500' : 'bg-gray-400';

  const phase = PHASE_CONFIG[dominantPhase] || PHASE_CONFIG.neutral;

  return (
    <IntelligenceBlock testId="token-regime">
      <h3 className="text-xs font-bold text-gray-400 uppercase tracking-[0.15em] mb-4">Market Regime</h3>

      <div className="space-y-3">
        <div className="grid grid-cols-2 gap-3">
          <div>
            <div className="text-[9px] font-bold text-gray-400 uppercase tracking-wider mb-0.5">Phase</div>
            <div className={`text-sm font-black ${phase.color}`} data-testid="regime-phase">{phase.label}</div>
          </div>
          <div>
            <div className="text-[9px] font-bold text-gray-400 uppercase tracking-wider mb-0.5">Volatility</div>
            <div className={`text-sm font-black ${volColor}`} data-testid="regime-volatility">{volatility}</div>
          </div>
          <div>
            <div className="text-[9px] font-bold text-gray-400 uppercase tracking-wider mb-0.5">Smart Bias</div>
            <div className={`text-sm font-black ${bc.color}`} data-testid="regime-bias">{bc.label}</div>
          </div>
          <div>
            <div className="text-[9px] font-bold text-gray-400 uppercase tracking-wider mb-0.5">Momentum</div>
            <div className={`text-sm font-black ${momColor}`} data-testid="regime-momentum">{momentum}</div>
          </div>
        </div>

        {/* Breakout probability */}
        <div className="pt-3 border-t border-gray-100">
          <div className="flex items-center justify-between mb-1">
            <span className="text-[9px] font-bold text-gray-400 uppercase tracking-wider">Breakout Probability</span>
            <span className={`text-lg font-black tabular-nums ${breakoutColor}`} data-testid="regime-breakout">{breakoutPct}%</span>
          </div>
          <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
            <div className={`h-full rounded-full ${breakoutBar} transition-all duration-700`} style={{ width: `${breakoutPct}%` }} />
          </div>
          <div className="mt-2 grid grid-cols-4 gap-1">
            {[
              { l: 'Flow', v: bullishTokens > totalTokens / 2 },
              { l: 'Clusters', v: avgScore >= 60 },
              { l: 'Regime', v: dominantPhase === 'accumulation' || dominantPhase === 'rotation' },
              { l: 'Liquidity', v: confidence >= 60 },
            ].map(d => (
              <div key={d.l} className="text-center">
                <div className={`text-[9px] font-bold ${d.v ? 'text-emerald-500' : 'text-gray-400'}`}>
                  {d.v ? '+++' : '+'}
                </div>
                <div className="text-[8px] text-gray-400">{d.l}</div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </IntelligenceBlock>
  );
}
