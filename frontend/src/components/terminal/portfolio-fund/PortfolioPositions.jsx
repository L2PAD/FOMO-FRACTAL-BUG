import { useState } from 'react';

export default function PortfolioPositions({ activePositions, closedPositions }) {
  const [closedFilter, setClosedFilter] = useState('ALL');

  const filteredClosed = closedPositions.filter(pos => {
    if (closedFilter === 'ALL') return true;
    if (closedFilter === 'WINS') return pos.pnl > 0;
    if (closedFilter === 'LOSSES') return pos.pnl < 0;
    return true;
  });

  const getExitReasonLabel = (reason) => {
    const labels = {
      target_hit: 'TARGET HIT',
      stop_loss: 'STOP LOSS',
      manual_exit: 'MANUAL EXIT',
      signal_flip: 'SIGNAL FLIP'
    };
    return labels[reason] || reason.toUpperCase();
  };

  const getExitReasonColor = (reason) => {
    if (reason === 'target_hit') return 'bg-green-100 text-green-700';
    if (reason === 'stop_loss') return 'bg-red-100 text-red-700';
    return 'bg-gray-100 text-gray-700';
  };

  return (
    <div className="grid grid-cols-12 gap-4">
      {/* Active Positions */}
      <div className="col-span-6">
        <div className="bg-white border border-[#E5E7EB] rounded-lg p-3" data-testid="active-positions">
          <div className="mb-3">
            <h3 className="text-sm font-semibold text-gray-900">Active Positions</h3>
            <p className="text-xs text-gray-500">Live exposures currently driving portfolio PnL</p>
          </div>

          <div className="space-y-2">
            {activePositions.map(pos => (
              <div
                key={pos.id}
                className="border border-[#E5E7EB] rounded-lg p-2.5 hover:bg-gray-50 transition-colors"
                data-testid={`position-${pos.id}`}
              >
                {/* Top row */}
                <div className="flex items-center justify-between mb-1.5">
                  <div className="flex items-center gap-1.5">
                    <span className="font-semibold text-sm text-gray-900">{pos.symbol}</span>
                    <span className={`px-1.5 py-0.5 text-xs font-medium rounded ${
                      pos.side === 'LONG' ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'
                    }`}>
                      {pos.side}
                    </span>
                    <span className="px-1.5 py-0.5 text-xs font-medium rounded-lg bg-gray-100 text-gray-600">
                      {pos.strategy.replace('_', ' ').toUpperCase()}
                    </span>
                    <span className="text-xs text-gray-500">{pos.tf}</span>
                  </div>
                </div>

                {/* Middle row */}
                <div className="flex items-center justify-between mb-1.5 text-xs">
                  <div className="font-mono text-gray-700">
                    Entry {pos.avg_entry.toLocaleString()} → Current {pos.current_price.toLocaleString()}
                  </div>
                  <div className="font-mono text-gray-600">
                    Size ${pos.size_usd.toLocaleString()}
                  </div>
                </div>

                {/* Bottom row */}
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2 text-xs">
                    <span className="text-gray-500">{pos.duration}</span>
                    <span className="text-gray-600">Near target</span>
                  </div>
                  <div className={`text-base font-semibold font-mono ${
                    pos.pnl >= 0 ? 'text-green-600' : 'text-red-600'
                  }`}>
                    {pos.pnl >= 0 ? '+' : ''}${pos.pnl.toLocaleString()} ({pos.pnl >= 0 ? '+' : ''}{pos.pnl_pct.toFixed(2)}%)
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Closed Positions */}
      <div className="col-span-6">
        <div className="bg-white border border-[#E5E7EB] rounded-lg p-3" data-testid="closed-positions">
          <div className="flex items-center justify-between mb-3">
            <div>
              <h3 className="text-sm font-semibold text-gray-900">Recent Closed Positions</h3>
            </div>
            <div className="flex items-center gap-1">
              {['ALL', 'WINS', 'LOSSES'].map(f => (
                <button
                  key={f}
                  onClick={() => setClosedFilter(f)}
                  className={`px-2 py-0.5 text-xs font-medium rounded-lg transition-colors ${
                    closedFilter === f
                      ? 'bg-gray-900 text-white'
                      : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                  }`}
                  data-testid={`closed-filter-${f}`}
                >
                  {f}
                </button>
              ))}
            </div>
          </div>

          <div className="space-y-2">
            {filteredClosed.map(pos => (
              <div
                key={pos.id}
                className="border border-[#E5E7EB] rounded-lg p-2.5 hover:bg-gray-50 transition-colors"
                data-testid={`closed-${pos.id}`}
              >
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <div className="flex items-center gap-1.5 mb-1">
                      <span className="font-semibold text-sm text-gray-900">{pos.symbol}</span>
                      <span className={`px-1.5 py-0.5 text-xs font-medium rounded ${
                        pos.side === 'LONG' ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'
                      }`}>
                        {pos.side}
                      </span>
                    </div>
                    <div className="font-mono text-xs text-gray-700 mb-1">
                      {pos.entry.toLocaleString()} → {pos.exit.toLocaleString()}
                    </div>
                    <div className="flex items-center gap-1.5 text-xs">
                      <span className="text-gray-500">{pos.duration}</span>
                      <span className={`px-1.5 py-0.5 text-xs font-medium rounded ${getExitReasonColor(pos.exit_reason)}`}>
                        {getExitReasonLabel(pos.exit_reason)}
                      </span>
                    </div>
                  </div>
                  <div className={`text-right font-mono font-semibold ${
                    pos.pnl >= 0 ? 'text-green-600' : 'text-red-600'
                  }`}>
                    <div className="text-base">
                      {pos.pnl >= 0 ? '+' : ''}${pos.pnl.toLocaleString()}
                    </div>
                    <div className="text-xs">
                      {pos.pnl >= 0 ? '+' : ''}{pos.pnl_pct.toFixed(2)}%
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
