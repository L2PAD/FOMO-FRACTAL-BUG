/**
 * P2 — Market Pulse
 * Aggregate market context: bias, counts, averages.
 * Minimal. No borders. Clean typography.
 */
import React from 'react';

const BIAS_STYLE = {
  BULLISH:  { color: '#16a34a', label: 'Bullish' },
  BEARISH:  { color: '#dc2626', label: 'Bearish' },
  MIXED:    { color: '#d97706', label: 'Mixed' },
  QUIET:    { color: '#94a3b8', label: 'Quiet' },
  NO_DATA:  { color: '#94a3b8', label: 'No Data' },
};

export default function MarketPulse({ pulse }) {
  if (!pulse) return null;

  const biasInfo = BIAS_STYLE[pulse.bias] || BIAS_STYLE.NO_DATA;

  return (
    <div data-testid="market-pulse" className="flex items-start justify-between pb-8" style={{ borderBottom: '1px solid rgba(15,23,42,0.06)' }}>
      {/* Left: Bias */}
      <div>
        <div className="text-[11px] uppercase tracking-wide" style={{ color: '#94a3b8', letterSpacing: '1px' }}>Market Bias</div>
        <div className="text-[28px] font-bold mt-0.5" style={{ color: biasInfo.color, letterSpacing: '-0.5px' }}>
          {biasInfo.label}
        </div>
        <div className="text-[12px] mt-1" style={{ color: '#b0b8c4' }}>
          {pulse.counts.total} scanned &middot; {pulse.counts.ok} active &middot; {pulse.dominantHorizon} dominant
        </div>
      </div>

      {/* Right: Stats grid */}
      <div className="flex gap-8">
        <PulseStat label="BUY" value={pulse.counts.buy} color="#16a34a" />
        <PulseStat label="SELL" value={pulse.counts.sell} color="#dc2626" />
        <PulseStat label="WATCH" value={pulse.counts.watch} color="#d97706" />
        <PulseStat label="Avg Conv" value={pulse.avg.conv} color="#0f172a" />
        <PulseStat label="Divergence" value={pulse.avg.div.toFixed(2)} color="#6366f1" />
      </div>
    </div>
  );
}

function PulseStat({ label, value, color }) {
  return (
    <div className="text-center">
      <div className="text-[11px] uppercase" style={{ color: '#94a3b8', letterSpacing: '0.5px' }}>{label}</div>
      <div className="text-[20px] font-bold tabular-nums mt-0.5" style={{ color }}>{value}</div>
    </div>
  );
}
