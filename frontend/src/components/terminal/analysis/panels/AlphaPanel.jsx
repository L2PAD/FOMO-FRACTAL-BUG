/**
 * Alpha Panel - Alpha Factory edge status
 * Question: Есть ли edge?
 */

import React from 'react';
import { GridRow } from '../shared/GridRow';

export default function AlphaPanel({ data }) {
  if (!data) {
    return (
      <div className="text-center text-sm text-gray-500 py-8">
        No alpha data available
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <h3 className="text-sm font-semibold uppercase tracking-wider text-gray-400">
        Alpha Factory
      </h3>
      <div className="space-y-3">
        <GridRow label="Symbol Verdict" value={data.symbol_verdict} />
        <GridRow label="Entry Mode Verdict" value={data.entry_mode_verdict} />
        <GridRow label="Profit Factor" value={data.profit_factor ?? '—'} />
        <GridRow
          label="Win Rate"
          value={
            data.win_rate != null
              ? `${Math.round(data.win_rate * 100)}%`
              : '—'
          }
        />
        <GridRow label="Expectancy" value={data.expectancy ?? '—'} />
        <GridRow label="Pending Actions" value={data.pending_actions ?? 0} />
      </div>
    </div>
  );
}
