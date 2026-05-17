/**
 * Operations Tabs - Operational Intelligence Layer Container
 * =========================================================
 * 
 * Unified container for:
 * - Live Positions (what system is holding)
 * - Active Orders (what system is executing)
 * - Closed Trades (what system learned)
 */

import React, { useState } from 'react';
import PositionsTab from './tabs/PositionsTab';
import OrdersTab from './tabs/OrdersTab';
import TradesTab from './tabs/TradesTab';

const tabs = [
  { id: 'positions', label: 'Positions' },
  { id: 'orders', label: 'Orders' },
  { id: 'trades', label: 'Trades' },
];

export default function OperationsTabs({ data, symbol = 'BTCUSDT', timeframe = '4H' }) {
  const [active, setActive] = useState('positions');

  if (!data) return null;

  const positions = data.positions || [];
  const orders = data.orders || [];
  const trades = data.trades || [];

  return (
    <div className="rounded-xl border border-white/10 bg-[#0F141A]">
      {/* Tabs */}
      <div className="flex gap-2 border-b border-white/10 p-2">
        {tabs.map((tab) => {
          // Count badges
          let count = 0;
          if (tab.id === 'positions') count = positions.length;
          if (tab.id === 'orders') count = orders.length;
          if (tab.id === 'trades') count = trades.length;

          return (
            <button
              key={tab.id}
              onClick={() => setActive(tab.id)}
              className={`rounded px-3 py-1.5 text-xs font-medium uppercase tracking-wide transition-all flex items-center gap-2 ${
                active === tab.id
                  ? 'bg-blue-600 text-white shadow-lg shadow-blue-600/20'
                  : 'text-gray-400 hover:bg-white/5 hover:text-white'
              }`}
            >
              {tab.label}
              {count > 0 && (
                <span
                  className={`rounded-full px-1.5 py-0.5 text-[10px] font-bold ${
                    active === tab.id
                      ? 'bg-white/20 text-white'
                      : 'bg-white/10 text-gray-300'
                  }`}
                >
                  {count}
                </span>
              )}
            </button>
          );
        })}
      </div>

      {/* Panel Content */}
      <div className="p-4">
        {active === 'positions' && (
          <PositionsTab positions={positions} symbol={symbol} timeframe={timeframe} />
        )}
        {active === 'orders' && (
          <OrdersTab orders={orders} symbol={symbol} timeframe={timeframe} />
        )}
        {active === 'trades' && (
          <TradesTab trades={trades} symbol={symbol} timeframe={timeframe} />
        )}
      </div>
    </div>
  );
}
