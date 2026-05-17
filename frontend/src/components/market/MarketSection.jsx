/**
 * P2 — Market Section
 * Renders a titled block with MarketRow list.
 */
import React from 'react';
import MarketRow from './MarketRow';

const SECTION_ICONS = {
  action:    { emoji: '', color: '#16a34a' },
  early:     { emoji: '', color: '#d97706' },
  shift:     { emoji: '', color: '#6366f1' },
  risk:      { emoji: '', color: '#dc2626' },
};

export default function MarketSection({ title, description, rows, variant = 'normal', sectionType = 'action', onRowClick }) {
  if (!rows?.length) return null;

  const sInfo = SECTION_ICONS[sectionType] || SECTION_ICONS.action;

  return (
    <div data-testid={`market-section-${sectionType}`}>
      {/* Header */}
      <div className="mb-3">
        <div className="flex items-center gap-2">
          <span className="text-[17px] font-bold tracking-tight" style={{ color: '#0f172a' }}>{title}</span>
          <span className="text-[12px] font-semibold tabular-nums px-1.5 py-0.5 rounded" style={{ background: 'rgba(15,23,42,0.04)', color: '#64748b' }}>
            {rows.length}
          </span>
        </div>
        <div className="text-[12px] mt-0.5" style={{ color: '#94a3b8' }}>{description}</div>
      </div>

      {/* Rows */}
      <div>
        {rows.map((row) => (
          <MarketRow key={row.symbol} row={row} variant={variant} onClick={onRowClick} />
        ))}
      </div>
    </div>
  );
}
