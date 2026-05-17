/**
 * Orders Tab - Active order tracking with execution context
 * ========================================================
 * 
 * Shows pending/filled orders with:
 * - Fill progress
 * - Status tracking
 * - Binding to chart zones
 */

import React from 'react';
import { useBinding } from '../../binding/BindingProvider';
import { makeOrderId, makeEntryZoneId } from '../../binding/bindingUtils';
import TabTable from '../shared/TabTable';
import StatusPill from '../shared/StatusPill';
import EmptyState from '../shared/EmptyState';

export default function OrdersTab({ orders = [], symbol, timeframe }) {
  const { setHovered, clearHovered, setSelected, hovered, selected } = useBinding();

  if (!orders || orders.length === 0) {
    return <EmptyState title="No active orders" />;
  }

  const columns = [
    {
      key: 'order_id',
      label: 'Order ID',
      render: (row) => (
        <span className="font-mono text-xs text-gray-400">
          {row.order_id?.slice(0, 8)}...
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
        <span className={`font-bold ${row.side === 'BUY' ? 'text-green-400' : 'text-red-400'}`}>
          {row.side}
        </span>
      ),
    },
    {
      key: 'type',
      label: 'Type',
      render: (row) => (
        <span className="text-gray-300 text-xs uppercase">{row.type || 'LIMIT'}</span>
      ),
    },
    {
      key: 'price',
      label: 'Price',
      render: (row) => (
        <span className="tabular-nums text-white">
          ${row.price?.toLocaleString()}
        </span>
      ),
    },
    {
      key: 'size',
      label: 'Size',
      render: (row) => (
        <span className="tabular-nums text-gray-300">{row.size}</span>
      ),
    },
    {
      key: 'filled',
      label: 'Filled',
      render: (row) => {
        const filledPct = (row.filled_pct || 0) * 100;
        return (
          <div>
            <div className="text-white font-medium tabular-nums">{filledPct.toFixed(1)}%</div>
            {filledPct > 0 && filledPct < 100 && (
              <div className="mt-1 h-1 w-12 bg-white/10 rounded-full overflow-hidden">
                <div
                  className="h-full bg-blue-500 transition-all"
                  style={{ width: `${filledPct}%` }}
                />
              </div>
            )}
          </div>
        );
      },
    },
    {
      key: 'status',
      label: 'Status',
      render: (row) => <StatusPill value={row.status} />,
    },
  ];

  const rows = orders.map((order) => {
    const orderId = makeOrderId(order.order_id || order.id);
    const entryZone = makeEntryZoneId(order.symbol, timeframe);

    // Binding logic: active = selected ?? hovered
    const active = selected ?? hovered;
    const isActive = active?.id === orderId;

    return {
      ...order,
      id: orderId,
      className: isActive ? 'bg-blue-600/20 ring-2 ring-blue-500/50' : '',
      onMouseEnter: () =>
        setHovered({
          id: orderId,
          type: 'order',
          relatedIds: [entryZone],
        }),
      onMouseLeave: clearHovered,
      onClick: () =>
        setSelected({
          id: orderId,
          type: 'order',
          relatedIds: [entryZone],
        }),
    };
  });

  return (
    <div>
      <TabTable columns={columns} rows={rows} />
    </div>
  );
}
