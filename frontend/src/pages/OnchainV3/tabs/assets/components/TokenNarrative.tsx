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

const BIAS_CONFIG: Record<string, { label: string; color: string; bg: string }> = {
  bullish: { label: 'BULLISH', color: 'text-emerald-400', bg: 'bg-emerald-500/10' },
  bearish: { label: 'BEARISH', color: 'text-red-400', bg: 'bg-red-500/10' },
  neutral: { label: 'NEUTRAL', color: 'text-gray-400', bg: 'bg-gray-500/10' },
};

const SIGNAL_LABEL: Record<string, string> = {
  strong_bullish: 'STRONG ACCUMULATION',
  bullish: 'ACCUMULATION',
  neutral: 'NEUTRAL',
  bearish: 'DISTRIBUTION',
  strong_bearish: 'STRONG DISTRIBUTION',
};

interface TradingBannerProps {
  narrative: Narrative | null;
  scores: TokenScore[];
  patterns: RotationPattern[];
  heat: DestinationHeat[];
  loading: boolean;
}

export function TradingDecisionBanner({ narrative, scores, patterns, heat, loading }: TradingBannerProps) {
  if (loading && !narrative) {
    return (
      <IntelligenceBlock dark testId="trading-decision-banner">
        <div className="flex items-center justify-center py-10">
          <div className="animate-spin w-5 h-5 border-2 border-emerald-400 border-t-transparent rounded-full" />
          <span className="ml-3 text-sm text-gray-500">Analyzing market signals...</span>
        </div>
      </IntelligenceBlock>
    );
  }
  if (!narrative) return null;

  const topToken = scores.length > 0 ? [...scores].sort((a, b) => b.alpha_score - a.alpha_score)[0] : null;
  const bias = BIAS_CONFIG[narrative.bias] || BIAS_CONFIG.neutral;
  const signalLabel = topToken ? (SIGNAL_LABEL[topToken.signal] || topToken.signal.toUpperCase()) : 'N/A';

  // Compute aggregate metrics
  const totalInflow = heat.filter(h => h.net_flow_usd > 0).reduce((s, h) => s + h.net_flow_usd, 0);
  const totalOutflow = heat.filter(h => h.net_flow_usd < 0).reduce((s, h) => s + Math.abs(h.net_flow_usd), 0);
  const netFlow = totalInflow - totalOutflow;
  const totalWallets = scores.reduce((s, t) => s + t.wallet_count, 0);
  const avgTiming = scores.length > 0 ? scores.reduce((s, t) => s + t.avg_timing, 0) / scores.length : 0;

  // Signal strength from top token
  const signalStrength = topToken?.alpha_score || 0;

  // Confidence tier
  const confTier = narrative.confidence >= 70 ? 'HIGH' : narrative.confidence >= 50 ? 'MODERATE' : 'LOW';
  const confColor = narrative.confidence >= 70 ? 'text-emerald-400' : narrative.confidence >= 50 ? 'text-amber-400' : 'text-gray-400';

  // Market phase from patterns
  const hasAccum = patterns.some(p => p.pattern_type === 'accumulation');
  const hasDistrib = patterns.some(p => p.pattern_type === 'distribution');
  const hasRotation = patterns.some(p => p.pattern_type === 'rotation');
  let phase = 'Mixed';
  if (hasAccum && !hasDistrib) phase = 'Early Accumulation';
  else if (hasAccum && hasRotation) phase = 'Rotation + Accumulation';
  else if (hasDistrib && !hasAccum) phase = 'Distribution';
  else if (hasRotation) phase = 'Capital Rotation';

  // Pressure
  const buyTokens = scores.filter(s => s.net_flow_usd > 0).length;
  const sellTokens = scores.filter(s => s.net_flow_usd < 0).length;
  let pressure = 'NEUTRAL';
  let pressureColor = 'text-gray-400';
  if (buyTokens > sellTokens * 2) { pressure = 'BUY DOMINANT'; pressureColor = 'text-emerald-400'; }
  else if (sellTokens > buyTokens * 2) { pressure = 'SELL DOMINANT'; pressureColor = 'text-red-400'; }
  else if (buyTokens > sellTokens) { pressure = 'BUY LEANING'; pressureColor = 'text-emerald-400'; }
  else if (sellTokens > buyTokens) { pressure = 'SELL LEANING'; pressureColor = 'text-red-400'; }

  return (
    <IntelligenceBlock dark testId="trading-decision-banner">
      <div className="flex flex-col lg:flex-row lg:items-start lg:justify-between gap-6">
        {/* Left: Main signal */}
        <div className="flex-1">
          <div className="text-[10px] font-bold text-gray-500 uppercase tracking-[0.2em] mb-2">Smart Money Bias</div>
          <div className="flex items-center gap-3 mb-4">
            {topToken && (
              <span className="text-2xl font-black text-white" data-testid="banner-token">{topToken.token}</span>
            )}
            <span className="text-lg font-black tracking-wide" style={{ color: bias.color.includes('emerald') ? '#34d399' : bias.color.includes('red') ? '#f87171' : '#9ca3af' }}
              data-testid="banner-signal-label">
              {signalLabel}
            </span>
          </div>

          {/* Key metrics grid */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
            <div>
              <div className="text-[9px] font-bold text-gray-500 uppercase tracking-wider mb-0.5">Net Flow</div>
              <div className={`text-lg font-black tabular-nums ${netFlow >= 0 ? 'text-emerald-400' : 'text-red-400'}`} data-testid="banner-net-flow">
                {netFlow >= 0 ? '+' : '-'}{fmtUsd(netFlow)}
              </div>
            </div>
            <div>
              <div className="text-[9px] font-bold text-gray-500 uppercase tracking-wider mb-0.5">Signal Strength</div>
              <div className={`text-lg font-black tabular-nums ${signalStrength >= 70 ? 'text-emerald-400' : signalStrength >= 50 ? 'text-amber-400' : 'text-gray-400'}`}
                data-testid="banner-signal-strength">
                {signalStrength}%
              </div>
            </div>
            <div>
              <div className="text-[9px] font-bold text-gray-500 uppercase tracking-wider mb-0.5">Lead Time</div>
              <div className="text-lg font-black tabular-nums text-white" data-testid="banner-lead-time">+{avgTiming.toFixed(1)}h</div>
            </div>
            <div>
              <div className="text-[9px] font-bold text-gray-500 uppercase tracking-wider mb-0.5">Wallets</div>
              <div className="text-lg font-black tabular-nums text-white" data-testid="banner-wallets">{totalWallets}</div>
            </div>
          </div>

          {/* Confidence bar */}
          <div className="mt-4 flex items-center gap-3">
            <div className="text-[9px] font-bold text-gray-500 uppercase tracking-wider">Confidence</div>
            <div className="flex-1 h-1.5 bg-gray-800 rounded-full overflow-hidden max-w-48">
              <div className={`h-full rounded-full transition-all duration-700 ${
                narrative.confidence >= 70 ? 'bg-emerald-400' : narrative.confidence >= 50 ? 'bg-amber-400' : 'bg-gray-600'
              }`} style={{ width: `${narrative.confidence}%` }} />
            </div>
            <span className={`text-xs font-black ${confColor}`} data-testid="banner-confidence">{confTier}</span>
          </div>
        </div>

        {/* Right: Market context */}
        <div className="lg:w-64 lg:border-l lg:border-gray-800 lg:pl-6 space-y-3">
          <div>
            <div className="text-[9px] font-bold text-gray-500 uppercase tracking-wider mb-0.5">Market Phase</div>
            <div className="text-sm font-bold text-white" data-testid="banner-phase">{phase}</div>
          </div>
          <div>
            <div className="text-[9px] font-bold text-gray-500 uppercase tracking-wider mb-0.5">Pressure</div>
            <div className={`text-sm font-bold ${pressureColor}`} data-testid="banner-pressure">{pressure}</div>
          </div>
          <div>
            <div className="text-[9px] font-bold text-gray-500 uppercase tracking-wider mb-0.5">Bias</div>
            <div className={`text-sm font-bold ${bias.color}`} data-testid="banner-bias">{bias.label} {narrative.confidence}%</div>
          </div>
          {scores.length > 0 && (
            <div>
              <div className="text-[9px] font-bold text-gray-500 uppercase tracking-wider mb-0.5">Active Tokens</div>
              <div className="text-sm font-bold text-white">{scores.length}</div>
            </div>
          )}
        </div>
      </div>
    </IntelligenceBlock>
  );
}
