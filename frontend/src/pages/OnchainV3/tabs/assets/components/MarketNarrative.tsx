import React from 'react';
import { IntelligenceBlock } from '../../../../../components/intelligence';
import type { Narrative, TokenScore, RotationPattern, DestinationHeat } from '../hooks/useTokenIntelligence';

function fmtUsd(n: number): string {
  const abs = Math.abs(n);
  if (abs >= 1e9) return `$${(abs / 1e9).toFixed(1)}B`;
  if (abs >= 1e6) return `$${(abs / 1e6).toFixed(1)}M`;
  if (abs >= 1e3) return `$${(abs / 1e3).toFixed(1)}K`;
  return `$${abs.toFixed(0)}`;
}

interface MarketNarrativeProps {
  narrative: Narrative | null;
  scores: TokenScore[];
  patterns: RotationPattern[];
  heat: DestinationHeat[];
  loading: boolean;
}

function buildNarrativeLines(
  narrative: Narrative | null,
  scores: TokenScore[],
  patterns: RotationPattern[],
  heat: DestinationHeat[]
): string[] {
  if (!narrative) return [];
  const lines: string[] = [];

  const topToken = scores.length > 0 ? [...scores].sort((a, b) => b.alpha_score - a.alpha_score)[0] : null;
  const rotations = patterns.filter(p => p.pattern_type === 'rotation' && p.from_token && p.to_token);

  // Main narrative sentence
  if (rotations.length > 0) {
    const r = rotations[0];
    lines.push(`Smart money rotating capital from ${r.from_token} to ${r.to_token}.`);
  } else if (narrative.summary) {
    lines.push(narrative.summary);
  }

  // Wallet activity
  if (topToken && topToken.wallet_count > 0) {
    const totalInflow = heat.filter(h => h.net_flow_usd > 0).reduce((s, h) => s + h.net_flow_usd, 0);
    lines.push(`${topToken.wallet_count} wallets accumulated ${fmtUsd(totalInflow)} in ${topToken.token} with average lead time of ${topToken.avg_timing.toFixed(1)}h.`);
  }

  // Signal interpretation
  const avgTiming = scores.length > 0 ? scores.reduce((s, t) => s + t.avg_timing, 0) / scores.length : 0;
  if (avgTiming >= 8) {
    lines.push('Strong early timing signals suggest expansion phase ahead.');
  } else if (avgTiming >= 5) {
    lines.push('Favorable timing patterns indicate potential price movement.');
  }

  // Accumulation/distribution count
  const bullish = scores.filter(s => s.signal === 'strong_bullish' || s.signal === 'bullish').length;
  const bearish = scores.filter(s => s.signal === 'strong_bearish' || s.signal === 'bearish').length;
  if (bullish > bearish && bullish >= 2) {
    lines.push(`${bullish} of ${scores.length} tokens showing bullish signals.`);
  } else if (bearish > bullish && bearish >= 2) {
    lines.push(`${bearish} of ${scores.length} tokens showing bearish signals.`);
  }

  return lines;
}

export function MarketNarrative({ narrative, scores, patterns, heat, loading }: MarketNarrativeProps) {
  if (loading && !narrative) return null;
  if (!narrative) return null;

  const lines = buildNarrativeLines(narrative, scores, patterns, heat);
  if (lines.length === 0) return null;

  return (
    <IntelligenceBlock dark testId="market-narrative">
      <div className="text-[9px] font-bold text-gray-500 uppercase tracking-[0.2em] mb-3">Market Narrative</div>
      <div className="space-y-2">
        {lines.map((line, i) => (
          <p key={i} className={`${i === 0 ? 'text-base font-semibold text-white' : 'text-sm text-gray-400'} leading-relaxed`}
            data-testid={`narrative-line-${i}`}>
            {line}
          </p>
        ))}
      </div>
    </IntelligenceBlock>
  );
}
