import React from 'react';
import { TrendingUp, AlertTriangle, Shield, Activity } from 'lucide-react';

const PortfolioIntelligenceBlock = ({ portfolio }) => {
  if (!portfolio) {
    return (
      <div className="bg-[#0A0E13] border border-gray-800 rounded-lg p-4">
        <div className="text-sm text-gray-500">Portfolio data unavailable</div>
      </div>
    );
  }

  const equity = portfolio?.equity || {};
  const heat = portfolio?.heat || {};
  const drawdown = portfolio?.drawdown || {};
  const allocator = portfolio?.allocator || {};
  const policy = portfolio?.policy || {};

  // Determine status
  let status = 'NORMAL';
  let statusColor = 'text-green-400';
  let StatusIcon = Shield;

  if (policy.hard_stop) {
    status = 'HARD STOP';
    statusColor = 'text-red-500';
    StatusIcon = AlertTriangle;
  } else if (heat.heat > 0.35 || drawdown.current_dd_pct < -10) {
    status = 'THROTTLED';
    statusColor = 'text-amber-500';
    StatusIcon = AlertTriangle;
  }

  return (
    <div className="bg-[#0A0E13] border border-gray-800 rounded-lg p-4" data-testid="portfolio-intelligence-block">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <Activity className="w-4 h-4 text-blue-400" />
          <span className="text-sm font-medium text-gray-300">Portfolio Intelligence</span>
        </div>
        <div className={`flex items-center gap-1.5 text-xs font-medium ${statusColor}`}>
          <StatusIcon className="w-3.5 h-3.5" />
          {status}
        </div>
      </div>

      {/* Metrics Grid */}
      <div className="grid grid-cols-2 gap-3">
        {/* Equity */}
        <div>
          <div className="text-xs text-gray-500 mb-0.5">Equity</div>
          <div className="text-lg font-semibold text-white">
            ${equity.equity?.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) || '0.00'}
          </div>
          <div className="text-xs text-gray-500">
            Balance: ${equity.balance?.toLocaleString('en-US', { maximumFractionDigits: 0 }) || '0'}
          </div>
        </div>

        {/* PnL */}
        <div>
          <div className="text-xs text-gray-500 mb-0.5">PnL</div>
          <div className={`text-lg font-semibold ${
            (equity.unrealized_pnl || 0) + (equity.realized_pnl || 0) >= 0 ? 'text-green-400' : 'text-red-400'
          }`}>
            {((equity.unrealized_pnl || 0) + (equity.realized_pnl || 0)) >= 0 ? '+' : ''}
            ${((equity.unrealized_pnl || 0) + (equity.realized_pnl || 0)).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
          </div>
          <div className="text-xs text-gray-500">
            Unrealized: ${equity.unrealized_pnl?.toFixed(2) || '0.00'}
          </div>
        </div>

        {/* Drawdown */}
        <div>
          <div className="text-xs text-gray-500 mb-0.5">Drawdown</div>
          <div className={`text-base font-medium ${
            drawdown.current_dd_pct >= -2 ? 'text-green-400' :
            drawdown.current_dd_pct >= -5 ? 'text-amber-400' : 'text-red-400'
          }`}>
            {drawdown.current_dd_pct?.toFixed(2) || '0.00'}%
          </div>
          <div className="text-xs text-gray-500">
            Peak: ${equity.equity_peak?.toLocaleString('en-US', { maximumFractionDigits: 0 }) || '0'}
          </div>
        </div>

        {/* Heat */}
        <div>
          <div className="text-xs text-gray-500 mb-0.5">Heat</div>
          <div className={`text-base font-medium ${
            heat.heat <= 0.21 ? 'text-green-400' :
            heat.heat <= 0.35 ? 'text-amber-400' : 'text-red-400'
          }`}>
            {heat.heat?.toFixed(2) || '0.00'}
          </div>
          <div className="text-xs text-gray-500">
            Max: {heat.max_heat?.toFixed(2) || '0.35'}
          </div>
        </div>
      </div>

      {/* Allocator Multiplier */}
      <div className="mt-3 pt-3 border-t border-gray-800">
        <div className="flex items-center justify-between">
          <span className="text-xs text-gray-500">Allocator Multiplier</span>
          <span className={`text-sm font-medium ${
            allocator.multiplier >= 1.0 ? 'text-green-400' :
            allocator.multiplier >= 0.7 ? 'text-amber-400' : 'text-red-400'
          }`}>
            {allocator.multiplier?.toFixed(2) || '1.00'}x
          </span>
        </div>
        {allocator.reason_chain && allocator.reason_chain.length > 0 && (
          <div className="mt-1 text-xs text-gray-600">
            {allocator.reason_chain.slice(0, 2).join(', ')}
          </div>
        )}
      </div>
    </div>
  );
};

export default PortfolioIntelligenceBlock;
