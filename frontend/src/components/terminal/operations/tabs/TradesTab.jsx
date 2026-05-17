/**
 * Trades Tab - Closed trade forensics with outcome context
 * =======================================================
 * 
 * Shows closed trades with:
 * - Win/Loss/BE outcome
 * - Entry/Exit reasons
 * - Binding to historical zones
 */

import React from 'react';
import { useBinding } from '../../binding/BindingProvider';
import { makeTradeId, makeEntryZoneId, makeRiskZoneId, makeTargetZoneId } from '../../binding/bindingUtils';
import TabTable from '../shared/TabTable';
import StatusPill from '../shared/StatusPill';
import EmptyState from '../shared/EmptyState';

export default function TradesTab({ trades = [], symbol, timeframe }) {
  const { setHovered, clearHovered, setSelected, hovered, selected } = useBinding();

  if (!trades || trades.length === 0) {
    return <EmptyState title="No closed trades" />;
  }

  const columns = [
    {
      key: 'trade_id',
      label: 'Trade ID',
      render: (row) => (
        <span className="font-mono text-xs text-gray-400">
          {row.trade_id?.slice(0, 8)}...
        </span>
      ),
    },
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
      key: 'entry_exit',
      label: 'Entry / Exit',
      render: (row) => (
        <div className="tabular-nums text-sm">
          <div className="text-gray-300">${row.entry_price?.toLocaleString()}</div>
          <div className="text-white">${row.exit_price?.toLocaleString()}</div>
        </div>
      ),
    },
    {
      key: 'pnl',
      label: 'PnL',
      render: (row) => {
        const pnl = row.pnl || 0;
        const pnlPct = row.pnl_pct || 0;
        return (
          <div className={`tabular-nums font-semibold ${pnl >= 0 ? 'text-green-400' : 'text-red-400'}`}>
            <div>{pnl >= 0 ? '+' : ''}{pnl.toFixed(0)}</div>
            <div className="text-xs opacity-75">{pnlPct >= 0 ? '+' : ''}{pnlPct.toFixed(2)}%</div>
          </div>
        );
      },
    },
    {
      key: 'rr',
      label: 'R:R',
      render: (row) => (
        <span className="tabular-nums text-white font-medium">{row.rr_actual || row.rr || '—'}</span>
      ),
    },
    {
      key: 'result',
      label: 'Result',
      render: (row) => <StatusPill value={row.result} />,
    },
    {
      key: 'duration',
      label: 'Duration',
      render: (row) => {
        const duration = row.duration_minutes || row.duration;
        if (!duration) return <span className="text-gray-500">—</span>;
        
        if (duration >= 1440) {
          return <span className="text-gray-300 text-xs">{(duration / 1440).toFixed(1)}d</span>;
        } else if (duration >= 60) {
          return <span className="text-gray-300 text-xs">{(duration / 60).toFixed(1)}h</span>;
        } else {
          return <span className="text-gray-300 text-xs">{duration}m</span>;
        }
      },
    },
    {
      key: 'context',
      label: 'Context',
      render: (row) => (
        <div className="text-xs text-gray-400">
          <div>{row.entry_mode || '—'}</div>
          <div>{row.exit_reason || '—'}</div>
        </div>
      ),
    },
  ];

  const rows = trades.map((trade) => {
    const tradeId = makeTradeId(trade.trade_id || trade.id);
    const entryZone = makeEntryZoneId(trade.symbol, timeframe);
    const riskZone = makeRiskZoneId(trade.symbol, timeframe);
    const targetZone = makeTargetZoneId(trade.symbol, timeframe);

    // Binding logic: active = selected ?? hovered
    const active = selected ?? hovered;
    const isActive = active?.id === tradeId;

    return {
      ...trade,
      id: tradeId,
      className: isActive ? 'bg-blue-600/20 ring-2 ring-blue-500/50' : '',
      onMouseEnter: () =>
        setHovered({
          id: tradeId,
          type: 'trade',
          relatedIds: [entryZone, riskZone, targetZone],
        }),
      onMouseLeave: clearHovered,
      onClick: () =>
        setSelected({
          id: tradeId,
          type: 'trade',
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
