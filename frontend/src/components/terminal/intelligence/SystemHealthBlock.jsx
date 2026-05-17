import React from 'react';
import { Shield, AlertTriangle, XOctagon } from 'lucide-react';

const SystemHealthBlock = ({ health }) => {
  if (!health) {
    return (
      <div className="bg-[#0A0E13] border border-gray-800 rounded-lg p-4" data-testid="system-health-block">
        <div className="text-sm text-gray-500">Health data unavailable</div>
      </div>
    );
  }

  const status = health.status || "HEALTHY";
  const metrics = health.metrics || {};

  // Determine visual style based on status
  let statusColor = 'text-green-400';
  let borderColor = 'border-green-800';
  let bgAccent = 'bg-green-950/20';
  let StatusIcon = Shield;
  let pulseClass = '';

  if (status === "CRITICAL") {
    statusColor = 'text-red-500';
    borderColor = 'border-red-800';
    bgAccent = 'bg-red-950/30';
    StatusIcon = XOctagon;
    pulseClass = 'animate-pulse';  // Pulse для CRITICAL
  } else if (status === "WARNING") {
    statusColor = 'text-amber-500';
    borderColor = 'border-amber-800';
    bgAccent = 'bg-amber-950/20';
    StatusIcon = AlertTriangle;
  }

  return (
    <div 
      className={`bg-[#0A0E13] border ${borderColor} rounded-lg p-4`}
      data-testid="system-health-block"
    >
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <Shield className="w-4 h-4 text-cyan-400" />
          <span className="text-sm font-medium text-gray-300">System Health</span>
        </div>
        <div className={`flex items-center gap-1.5 text-lg font-bold ${statusColor} ${pulseClass}`}>
          <StatusIcon className="w-5 h-5" />
          {status}
        </div>
      </div>

      {/* Metrics Grid */}
      <div className="grid grid-cols-2 gap-3">
        {/* Daily PnL % */}
        <div className={`rounded p-2 ${bgAccent}`}>
          <div className="text-xs text-gray-500 mb-0.5">Daily PnL</div>
          <div className={`text-base font-semibold ${
            (metrics.daily_pnl_pct || 0) >= 0 ? 'text-green-400' : 'text-red-400'
          }`}>
            {((metrics.daily_pnl_pct || 0) * 100).toFixed(2)}%
          </div>
        </div>

        {/* Drawdown % */}
        <div className={`rounded p-2 ${bgAccent}`}>
          <div className="text-xs text-gray-500 mb-0.5">Drawdown</div>
          <div className={`text-base font-semibold ${
            (metrics.drawdown_pct || 0) >= -0.05 ? 'text-green-400' :
            (metrics.drawdown_pct || 0) >= -0.10 ? 'text-amber-400' : 'text-red-400'
          }`}>
            {((metrics.drawdown_pct || 0) * 100).toFixed(2)}%
          </div>
        </div>

        {/* Reject Rate */}
        <div className={`rounded p-2 ${bgAccent}`}>
          <div className="text-xs text-gray-500 mb-0.5">Reject Rate</div>
          <div className={`text-base font-semibold ${
            (metrics.reject_rate || 0) < 0.1 ? 'text-green-400' :
            (metrics.reject_rate || 0) < 0.2 ? 'text-amber-400' : 'text-red-400'
          }`}>
            {((metrics.reject_rate || 0) * 100).toFixed(1)}%
          </div>
        </div>

        {/* Reconciliation Critical */}
        <div className={`rounded p-2 ${bgAccent}`}>
          <div className="text-xs text-gray-500 mb-0.5">Recon Critical</div>
          <div className={`text-base font-semibold ${
            (metrics.reconciliation_critical || 0) === 0 ? 'text-green-400' : 'text-red-500'
          }`}>
            {metrics.reconciliation_critical || 0}
          </div>
        </div>
      </div>
    </div>
  );
};

export default SystemHealthBlock;
