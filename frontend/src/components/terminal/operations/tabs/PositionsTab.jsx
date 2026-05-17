/**
 * Positions Tab - Live position tracking with cognitive context
 * ============================================================
 * 
 * Shows active positions with:
 * - Entry/risk/target context
 * - Health status
 * - Binding to chart zones
 */

import React from 'react';
import { useBinding } from '../../binding/BindingProvider';
import { makePositionId, makeEntryZoneId, makeRiskZoneId, makeTargetZoneId } from '../../binding/bindingUtils';
import TabTable from '../shared/TabTable';
import StatusPill from '../shared/StatusPill';
import EmptyState from '../shared/EmptyState';

export default function PositionsTab({ positions = [], symbol, timeframe }) {
  const { setHovered, clearHovered, setSelected, hovered, selected } = useBinding();

  if (!positions || positions.length === 0) {
    return <EmptyState title="No open positions" />;
  }

  const columns = [
    {
      key: 'symbol',
      label: 'Symbol',
      render: (row) => (
        <span className="font-semibold text-white">{row.symbol}</span>
      ),
    },
    {
      key: 'side',
      label: 'Side',
      render: (row) => (
        <span className={`font-bold ${row.side === 'LONG' ? 'text-green-400' : 'text-red-400'}`}>
          {row.side}
        </span>
      ),
    },
    {
      key: 'size',
      label: 'Size',
      render: (row) => (
        <span className="tabular-nums text-white">{row.size}</span>
      ),
    },
    {
      key: 'entry',
      label: 'Entry',
      render: (row) => (
        <span className="tabular-nums text-gray-300">
          ${row.entry_price?.toLocaleString()}
        </span>
      ),
    },
    {
      key: 'mark',
      label: 'Mark',
      render: (row) => (
        <span className="tabular-nums text-white">
          ${row.mark_price?.toLocaleString()}
        </span>
      ),
    },
    {
      key: 'pnl',
      label: 'PnL',
      render: (row) => {
        const pnl = row.unrealized_pnl || 0;
        const pnlPct = row.pnl_pct || 0;
        return (
          <div className={`tabular-nums font-semibold ${pnl >= 0 ? 'text-green-400' : 'text-red-400'}`}>
            <div>{pnl >= 0 ? '+' : ''}{pnl.toLocaleString()}</div>
            <div className="text-xs opacity-75">{pnlPct >= 0 ? '+' : ''}{pnlPct.toFixed(2)}%</div>
          </div>
        );
      },
    },
    {
      key: 'rr',
      label: 'R:R',
      render: (row) => (
        <span className="tabular-nums text-white font-medium">{row.rr || '—'}</span>
      ),
    },
    {
      key: 'health',
      label: 'Health',
      render: (row) => <StatusPill value={row.health || 'GOOD'} />,
    },
    {
      key: 'context',
      label: 'Context',
      render: (row) => (
        <div className="text-xs text-gray-400">
          <div>{row.entry_mode || '—'}</div>
          <div>{row.execution_mode || '—'}</div>
        </div>
      ),
    },
  ];

  const rows = positions.map((pos) => {
    const posId = makePositionId(pos.position_id || pos.id);
    const entryZone = makeEntryZoneId(pos.symbol, timeframe);
    const riskZone = makeRiskZoneId(pos.symbol, timeframe);
    const targetZone = makeTargetZoneId(pos.symbol, timeframe);

    // Binding logic: active = selected ?? hovered
    const active = selected ?? hovered;
    const isActive = active?.id === posId;

    return {
      ...pos,
      id: posId,
      className: isActive ? 'bg-blue-600/20 ring-2 ring-blue-500/50' : '',
      onMouseEnter: () =>
        setHovered({
          id: posId,
          type: 'position',
          relatedIds: [entryZone, riskZone, targetZone],
        }),
      onMouseLeave: clearHovered,
      onClick: () =>
        setSelected({
          id: posId,
          type: 'position',
          relatedIds: [entryZone, riskZone, targetZone],
        }),
    };
  });

  return (
    <div>
      <TabTable columns={columns} rows={rows} />
    </div>
  );
}
