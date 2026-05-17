/**
 * Radar Top Setups Strip V5 — Clean Design
 * No bordered badges. Plain colored text. More breathing room.
 */
import React, { useRef } from 'react';
import { ChevronLeft, ChevronRight } from 'lucide-react';

const VERDICT_COLORS = {
  buy: '#16a34a',
  sell: '#dc2626',
  watch: '#d97706',
  neutral: '#64748b',
};

const DIR_ARROWS = { long: '\u2191', short: '\u2193', neutral: '\u2013' };

const TIER_COLORS = {
  'A+': '#15803d',
  'A':  '#059669',
  'B':  '#b45309',
  'C':  '#64748b',
};

const HORIZON_LABELS = {
  short: { label: '0\u20132d', color: '#dc2626' },
  mid:   { label: '3\u20137d', color: '#d97706' },
  swing: { label: '1\u20134w', color: '#7c3aed' },
};

export default function RadarTopSetups({ rows, onRowClick, horizon = 'auto' }) {
  const scrollRef = useRef(null);

  const top = [...rows]
    .filter(r => r.verdict !== 'data_gap')
    .sort((a, b) => {
      if (horizon !== 'auto' && a.horizons && b.horizons) {
        return (b.horizons[horizon]?.conviction ?? b.conviction) - (a.horizons[horizon]?.conviction ?? a.conviction);
      }
      return b.conviction - a.conviction;
    })
    .slice(0, 8);

  if (!top.length) return <div style={{ height: 0 }} />;

  const scroll = (dir) => {
    if (!scrollRef.current) return;
    scrollRef.current.scrollBy({ left: dir * 220, behavior: 'smooth' });
  };

  return (
    <div
      data-testid="radar-top-setups"
      className="relative mt-3 px-4 pb-4"
      style={{
        borderBottom: '1px solid rgba(15,23,42,0.05)',
        borderTop: '1px solid rgba(15,23,42,0.04)',
        background: 'rgba(15,23,42,0.018)',
        minHeight: '110px',
      }}
    >
      <button
        onClick={() => scroll(-1)}
        className="absolute left-1 top-1/2 -translate-y-1/2 z-10 w-6 h-6 rounded-full flex items-center justify-center opacity-0 hover:opacity-100 transition-opacity"
        style={{ background: 'rgba(255,255,255,0.95)', boxShadow: '0 1px 4px rgba(0,0,0,0.08)' }}
        data-testid="top-setups-scroll-left"
      >
        <ChevronLeft className="w-3.5 h-3.5" style={{ color: '#475569' }} />
      </button>
      <button
        onClick={() => scroll(1)}
        className="absolute right-1 top-1/2 -translate-y-1/2 z-10 w-6 h-6 rounded-full flex items-center justify-center opacity-0 hover:opacity-100 transition-opacity"
        style={{ background: 'rgba(255,255,255,0.95)', boxShadow: '0 1px 4px rgba(0,0,0,0.08)' }}
        data-testid="top-setups-scroll-right"
      >
        <ChevronRight className="w-3.5 h-3.5" style={{ color: '#475569' }} />
      </button>

      <div
        ref={scrollRef}
        className="flex gap-2 overflow-x-auto"
        style={{ scrollbarWidth: 'none', msOverflowStyle: 'none' }}
      >
        {top.map(row => {
          const vc = VERDICT_COLORS[row.verdict] || '#64748b';
          const conviction = horizon !== 'auto' && row.horizons?.[horizon]
            ? (row.horizons[horizon].conviction ?? row.conviction)
            : row.conviction;
          const primary = horizon === 'auto' ? row.horizons?.primary : horizon;
          const hLabel = HORIZON_LABELS[primary];
          const tier = row.convictionTier;
          const tierColor = tier ? TIER_COLORS[tier] : null;

          return (
            <div
              key={row.symbol}
              data-testid={`top-setup-${row.symbol}`}
              onClick={() => onRowClick(row)}
              className="flex-shrink-0 py-3.5 px-5 rounded-lg cursor-pointer transition-colors duration-150"
              style={{ width: '200px', borderRight: '1px solid rgba(15,23,42,0.04)' }}
              onMouseEnter={e => { e.currentTarget.style.background = 'rgba(15,23,42,0.05)'; }}
              onMouseLeave={e => { e.currentTarget.style.background = 'transparent'; }}
            >
              {/* Row 1: Symbol + Arrow + Conviction */}
              <div className="flex items-center justify-between mb-1">
                <div className="flex items-center gap-1.5">
                  <span className="text-[16px] font-semibold tracking-tight" style={{ color: '#0f172a' }}>
                    {row.symbol.replace('USDT', '')}
                  </span>
                  <span className="text-[13px]" style={{ color: vc }}>
                    {DIR_ARROWS[row.direction]}
                  </span>
                </div>
                <span className="text-[16px] font-bold tabular-nums" style={{ color: vc }}>
                  {conviction}
                </span>
              </div>

              {/* Row 2: Verdict + Tier + Horizon — all plain text, no borders */}
              <div className="flex items-center gap-2 mb-1.5">
                <span className="text-[12px] font-semibold uppercase" style={{ color: vc, letterSpacing: '0.4px' }}>
                  {row.verdict}
                </span>
                {tierColor && (
                  <span className="text-[11px] font-bold" style={{ color: tierColor }}>
                    {tier}
                  </span>
                )}
                {hLabel && (
                  <span className="text-[11px] font-semibold" style={{ color: hLabel.color }}>
                    {hLabel.label}
                  </span>
                )}
              </div>

              {/* Row 3: Setup reason */}
              <p className="text-[12px] truncate leading-snug" style={{ color: '#94a3b8' }}>
                {row.whyNow || 'No active catalyst'}
              </p>
            </div>
          );
        })}
      </div>
    </div>
  );
}
