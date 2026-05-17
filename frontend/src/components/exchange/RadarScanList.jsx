/**
 * Radar Scan List V5 — Clean Design
 * 
 * Changes from V4:
 * - Merged Direction + Verdict into single column (no duplication)
 * - Removed all bordered badges — plain colored text only
 * - Added breathing room: taller rows, wider column gaps
 * - Simplified Tier/Horizon/Integrity to pure text
 */
import React from 'react';
import { Info, ChevronRight } from 'lucide-react';

const VERDICT_COLORS = {
  buy: '#16a34a',
  sell: '#dc2626',
  watch: '#d97706',
  neutral: '#64748b',
  data_gap: '#a1a1aa',
};

const RISK_COLORS = { low: '#16a34a', medium: '#d97706', high: '#dc2626', unknown: '#a1a1aa' };

const DIR_ARROWS = { long: '\u2191', short: '\u2193', neutral: '\u2013' };

const TIER_COLORS = {
  'A+': '#15803d',
  'A':  '#059669',
  'B':  '#b45309',
  'C':  '#64748b',
  'noise': '#94a3b8',
};

const HORIZON_LABELS = {
  short: { label: '0\u20132d', color: '#dc2626' },
  mid:   { label: '3\u20137d', color: '#d97706' },
  swing: { label: '1\u20134w', color: '#7c3aed' },
};

const INTEGRITY_COLORS = {
  'ok':       '#15803d',
  'degraded': '#b45309',
  'invalid':  '#dc2626',
};

const INTEGRITY_LABELS = {
  'ok':       'OK',
  'degraded': 'DEG',
  'invalid':  'INV',
};

const GRID = '100px 36px 100px 140px 56px 36px 1fr 64px 28px';

function getHorizonConviction(row, horizon) {
  if (horizon === 'auto' || !row.horizons) return row.conviction;
  const h = row.horizons[horizon];
  return h?.conviction ?? row.conviction;
}

function getHorizonDirection(row, horizon) {
  if (horizon === 'auto' || !row.horizons) return row.direction;
  const h = row.horizons[horizon];
  return h?.direction ?? h?.dir ?? row.direction;
}

function getPrimaryHorizon(row) {
  return row.horizons?.primary || null;
}

function ScanHeader() {
  return (
    <div
      className="grid items-center px-5"
      style={{
        gridTemplateColumns: GRID,
        columnGap: '16px',
        paddingBottom: '10px',
        marginBottom: '2px',
        borderBottom: '1px solid rgba(15,23,42,0.06)',
      }}
    >
      {['Asset', 'Tier', 'Signal', 'Conviction', 'Horizon', '', 'Setup', 'Risk', ''].map((label, i) => (
        <span
          key={i}
          className="text-[11px] font-semibold uppercase"
          style={{ color: '#94a3b8', letterSpacing: '0.6px' }}
        >
          {label}
        </span>
      ))}
    </div>
  );
}

function ScanRow({ row, mode, onRowClick, horizon }) {
  const isGap = row.verdict === 'data_gap';
  const conviction = getHorizonConviction(row, horizon);
  const direction = getHorizonDirection(row, horizon);
  const vc = VERDICT_COLORS[row.verdict] || '#64748b';
  const tierColor = isGap ? '#cbd5e1' : (TIER_COLORS[row.convictionTier] || '#94a3b8');
  const primary = horizon === 'auto' ? getPrimaryHorizon(row) : horizon;
  const hLabel = primary ? HORIZON_LABELS[primary] : null;
  const intColor = row.integrity ? (INTEGRITY_COLORS[row.integrity.status] || '#94a3b8') : '#cbd5e1';
  const intLabel = row.integrity ? (INTEGRITY_LABELS[row.integrity.status] || '\u2013') : '\u2013';
  const venueLabel = mode === 'futures' ? 'perp' : mode === 'alpha' ? 'alpha' : 'spot';

  return (
    <div
      data-testid={`radar-row-${row.symbol}`}
      onClick={() => onRowClick(row)}
      className="grid items-center px-5 rounded-md cursor-pointer transition-colors duration-100"
      style={{
        gridTemplateColumns: GRID,
        columnGap: '16px',
        height: '58px',
        opacity: isGap ? 0.5 : 1,
      }}
      onMouseEnter={e => { e.currentTarget.style.background = 'rgba(15,23,42,0.02)'; }}
      onMouseLeave={e => { e.currentTarget.style.background = 'transparent'; }}
    >
      {/* Asset */}
      <div className="flex flex-col min-w-0">
        <div className="flex items-center gap-1.5">
          <span className="text-[15px] font-semibold tracking-tight" style={{ color: isGap ? '#94a3b8' : '#0f172a' }}>
            {row.symbol.replace('USDT', '')}
          </span>
          {row.venueCount >= 2 && (
            <span
              data-testid={`venue-badge-${row.symbol}`}
              className="text-[9px] font-bold px-1 py-px rounded"
              style={{ background: 'rgba(99,102,241,0.10)', color: '#6366f1', letterSpacing: '0.5px' }}
            >
              {row.venueCount}V
            </span>
          )}
          {row.divergenceScore >= 0.25 && row.venueCount >= 2 && (
            <span
              data-testid={`div-badge-${row.symbol}`}
              className="text-[9px] font-bold px-1 py-px rounded"
              style={{
                background: row.divergenceLabel === 'HIGH' ? 'rgba(220,38,38,0.08)' : 'rgba(217,119,6,0.08)',
                color: row.divergenceLabel === 'HIGH' ? '#dc2626' : '#b45309',
                letterSpacing: '0.5px',
              }}
              title={`Venue Divergence: ${row.divergenceLabel}\n${(row.divergenceReasons || []).join(', ')}\nShort-horizon boost`}
            >
              DIV
            </span>
          )}
        </div>
      </div>

      {/* Tier — plain text, no border */}
      <span
        data-testid="tier-badge"
        className="text-[12px] font-bold"
        style={{ color: tierColor }}
      >
        {isGap ? '\u2013' : (row.convictionTier || '\u2013')}
      </span>

      {/* Signal — merged direction + verdict, no duplication */}
      <div className="flex items-center gap-1.5">
        <span className="text-[13px]" style={{ color: vc }}>
          {isGap ? '' : DIR_ARROWS[direction]}
        </span>
        <span
          className="text-[13px] font-semibold uppercase"
          style={{ color: vc, letterSpacing: '0.3px' }}
        >
          {isGap ? 'NO DATA' : row.verdict}
        </span>
      </div>

      {/* Conviction — bar + number */}
      <div className="flex items-center gap-3">
        {isGap ? (
          <span className="text-[12px]" style={{ color: '#a1a1aa' }}>N/A</span>
        ) : (
          <>
            <div className="flex-1 h-[5px] rounded-full overflow-hidden" style={{ background: 'rgba(15,23,42,0.05)' }}>
              <div
                className="h-full rounded-full transition-all duration-300"
                style={{ width: `${conviction}%`, backgroundColor: vc }}
              />
            </div>
            <span className="text-[15px] font-bold tabular-nums" style={{ color: '#0f172a', minWidth: '24px', textAlign: 'right' }}>
              {conviction}
            </span>
          </>
        )}
      </div>

      {/* Horizon — plain text, no border */}
      <span
        data-testid="horizon-tag"
        className="text-[12px] font-semibold"
        style={{ color: (isGap || !hLabel) ? '#cbd5e1' : hLabel.color }}
      >
        {isGap ? '\u2013' : (hLabel ? hLabel.label : '\u2013')}
      </span>

      {/* Integrity — plain text, no border */}
      <span
        data-testid="integrity-badge"
        className="text-[11px] font-bold"
        style={{ color: isGap ? '#cbd5e1' : intColor }}
        title={row.integrity?.reasons?.length ? row.integrity.reasons.join(', ') : ''}
      >
        {isGap ? '\u2013' : intLabel}
      </span>

      {/* Setup — human-readable, extract key insight only */}
      <span className="text-[13px] truncate pr-2 min-w-0 leading-snug" style={{ color: isGap ? '#a1a1aa' : '#64748b' }}>
        {isGap ? 'Insufficient market data' : (() => {
          const raw = row.explain?.oneLiner || row.whyNow || '\u2014';
          // Extract readable part after last pipe separator, strip "Risk X"
          const parts = raw.split('|').map(s => s.trim());
          const insight = parts.length >= 3
            ? parts.slice(2).join(', ').replace(/\s*Risk\s+\w+/i, '').replace(/,\s*$/, '').trim()
            : raw;
          return insight || parts[parts.length - 1] || raw;
        })()}
      </span>

      {/* Risk */}
      <div className="flex items-center gap-1.5">
        <span className="w-[5px] h-[5px] rounded-full flex-shrink-0" style={{ background: RISK_COLORS[row.riskLevel] || '#a1a1aa' }} />
        <span className="text-[12px] font-medium capitalize" style={{ color: RISK_COLORS[row.riskLevel] || '#a1a1aa' }}>
          {isGap ? '?' : row.riskLevel}
        </span>
      </div>

      {/* Detail */}
      <button
        data-testid={`radar-info-${row.symbol}`}
        onClick={(e) => { e.stopPropagation(); onRowClick(row); }}
        className="p-1.5 rounded-md transition-all"
        style={{ color: '#0f172a', opacity: 0.5 }}
        onMouseEnter={e => { e.currentTarget.style.opacity = '1'; e.currentTarget.style.background = 'rgba(15,23,42,0.05)'; }}
        onMouseLeave={e => { e.currentTarget.style.opacity = '0.5'; e.currentTarget.style.background = 'transparent'; }}
      >
        <ChevronRight className="w-4 h-4" strokeWidth={2} />
      </button>
    </div>
  );
}

export default function RadarScanList({ rows, mode, onRowClick, horizon = 'auto' }) {
  if (!rows.length) {
    return (
      <div className="text-center py-16 text-[14px]" style={{ color: '#94a3b8', minHeight: '200px' }} data-testid="radar-empty">
        No signals match current filters
      </div>
    );
  }

  return (
    <div data-testid="radar-scan-list" className="mt-3 px-4" style={{ maxWidth: '1200px', minHeight: '200px' }}>
      <ScanHeader />
      <div className="flex flex-col gap-px">
        {rows.map(row => (
          <ScanRow key={row.symbol} row={row} mode={mode} onRowClick={onRowClick} horizon={horizon} />
        ))}
      </div>
    </div>
  );
}
