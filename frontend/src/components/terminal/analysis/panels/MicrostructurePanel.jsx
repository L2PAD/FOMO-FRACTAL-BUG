/**
 * Microstructure Panel
 * ====================
 * 
 * Shows execution-level market conditions:
 * - Micro decision
 * - State (favorable/hostile)
 * - Imbalance
 * - Spread
 * - Liquidity
 * - Size/confidence impact
 */

import React from 'react';
import { PanelShell } from '../shared/PanelShell';
import { GridRow } from '../shared/GridRow';
import { TagList } from '../shared/TagList';
import { fmtPct, fmtNum } from '../shared/formatters';

export default function MicrostructurePanel({ data }) {
  if (!data) {
    return (
      <PanelShell title="Microstructure">
        <div className="text-gray-500 text-sm">No microstructure data available</div>
      </PanelShell>
    );
  }

  return (
    <PanelShell title="Microstructure">
      <GridRow label="Decision" value={data.decision || data.state} />
      <GridRow label="State" value={data.state} />
      <GridRow label="Imbalance" value={fmtPct(data.imbalance)} />
      <GridRow 
        label="Spread" 
        value={data.spread != null ? `${fmtNum(data.spread, 1)} bps` : '—'} 
      />
      <GridRow label="Liquidity" value={data.liquidity || '—'} />
      <GridRow 
        label="Size Mod" 
        value={data.weighting_impact?.size_multiplier || data.size_multiplier || '—'} 
      />
      <GridRow 
        label="Exec Style" 
        value={data.weighting_impact?.execution_style || data.execution_style || '—'} 
      />

      <TagList 
        title="Reasons" 
        items={data.reasons} 
        empty="No micro reasons" 
      />
    </PanelShell>
  );
}
