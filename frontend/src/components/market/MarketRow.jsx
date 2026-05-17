/**
 * P2 — Market Row (Compact)
 * Reuses Radar visual language. Click → ExplainDrawer.
 */
import React from 'react';

const VERDICT_COLORS = {
  buy: '#16a34a', sell: '#dc2626', watch: '#d97706', neutral: '#64748b', data_gap: '#cbd5e1',
};
const DIR_ARROWS = { long: '\u2191', short: '\u2193', neutral: '\u2013' };
const TIER_COLORS = { 'A+': '#15803d', 'A': '#059669', 'B': '#b45309', 'C': '#64748b' };
const HORIZON_LABELS = {
  short: { label: '0\u20132d', color: '#dc2626' },
  mid:   { label: '3\u20137d', color: '#d97706' },
  swing: { label: '1\u20134w', color: '#7c3aed' },
};
const RISK_COLORS = { high: '#dc2626', medium: '#d97706', low: '#16a34a', unknown: '#94a3b8' };

export default function MarketRow({ row, variant = 'normal', onClick }) {
  const vc = VERDICT_COLORS[row.verdict] || '#64748b';
  const tier = row.convictionTier;
  const tierColor = tier ? TIER_COLORS[tier] : null;
  const primary = row.horizons?.primary || 'mid';
  const hLabel = HORIZON_LABELS[primary];
  const riskVal = typeof row.risk === 'string' ? row.risk : (row.risk?.value ?? 'unknown');
  const riskColor = RISK_COLORS[riskVal] || '#94a3b8';
  const oneLiner = row.explain?.oneLiner || '';

  return (
    <div
      data-testid={`market-row-${row.symbol}`}
      onClick={() => onClick?.(row)}
      className="flex items-center justify-between py-3 px-3 rounded-lg cursor-pointer transition-colors duration-100"
      style={{ borderBottom: '1px solid rgba(15,23,42,0.04)' }}
      onMouseEnter={e => { e.currentTarget.style.background = 'rgba(15,23,42,0.025)'; }}
      onMouseLeave={e => { e.currentTarget.style.background = 'transparent'; }}
    >
      {/* Left block */}
      <div className="flex items-center gap-4 min-w-0 flex-1">
        {/* Symbol + badges */}
        <div className="flex items-center gap-2 shrink-0" style={{ minWidth: '90px' }}>
          <span className="text-[15px] font-semibold tracking-tight" style={{ color: '#0f172a' }}>
            {row.symbol.replace('USDT', '')}
          </span>
          <span className="text-[12px]" style={{ color: vc }}>
            {DIR_ARROWS[row.direction] || '\u2013'}
          </span>
          {(row.venueCount ?? 1) >= 2 && (
            <span className="text-[9px] font-bold px-1 py-px rounded" style={{ background: 'rgba(99,102,241,0.10)', color: '#6366f1' }}>
              {row.venueCount}V
            </span>
          )}
          {row.divergenceScore >= 0.25 && (row.venueCount ?? 1) >= 2 && (
            <span className="text-[9px] font-bold px-1 py-px rounded" style={{
              background: row.divergenceLabel === 'HIGH' ? 'rgba(220,38,38,0.08)' : 'rgba(217,119,6,0.08)',
              color: row.divergenceLabel === 'HIGH' ? '#dc2626' : '#b45309',
            }}>
              DIV
            </span>
          )}
        </div>

        {/* Verdict */}
        <span className="text-[11px] font-bold uppercase shrink-0" style={{ color: vc, letterSpacing: '0.4px' }}>
          {row.verdict}
        </span>

        {/* One-liner */}
        <span className="text-[12px] truncate" style={{ color: '#94a3b8' }}>
          {oneLiner}
        </span>
      </div>

      {/* Right block: Tier + Horizon + Conv + Risk */}
      <div className="flex items-center gap-5 shrink-0 ml-4">
        {tierColor && (
          <span data-testid={`market-tier-${row.symbol}`} className="text-[11px] font-bold" style={{ color: tierColor }}>
            {tier}
          </span>
        )}
        {hLabel && (
          <span className="text-[11px] font-semibold" style={{ color: hLabel.color }}>
            {hLabel.label}
          </span>
        )}
        <span className="text-[15px] font-bold tabular-nums" style={{ color: vc, minWidth: '28px', textAlign: 'right' }}>
          {row.conviction}
        </span>
        {variant === 'risk' && (
          <span className="text-[10px] font-semibold uppercase" style={{ color: riskColor }}>
            {riskVal}
          </span>
        )}
      </div>
    </div>
  );
}
