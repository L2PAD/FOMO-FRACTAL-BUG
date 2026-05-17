// Risk Health Panel

import React from 'react';
import { Shield, AlertTriangle, TrendingUp, TrendingDown } from 'lucide-react';

export default function RiskHealthPanel({ riskHealth }) {
  const state = riskHealth?.state || 'UNKNOWN';
  const exposurePct = riskHealth?.exposure_pct || 0;
  const activePositions = riskHealth?.active_positions || 0;
  const maxPositions = riskHealth?.max_positions || 3;
  const dailyPnl = riskHealth?.daily_pnl || 0;
  const lossLimit = riskHealth?.loss_limit || -200;
  const rejectsLastHour = riskHealth?.rejects_last_hour || 0;
  const lastRejectReason = riskHealth?.last_reject_reason;
  
  const getStateColor = (state) => {
    switch (state) {
      case 'NORMAL': return { text: 'text-green-700', bg: 'bg-green-50', border: 'border-green-200' };
      case 'WARNING': return { text: 'text-yellow-700', bg: 'bg-yellow-50', border: 'border-yellow-200' };
      case 'CRITICAL': return { text: 'text-red-700', bg: 'bg-red-50', border: 'border-red-200' };
      default: return { text: 'text-neutral-500', bg: 'bg-neutral-50', border: 'border-neutral-200' };
    }
  };
  
  const stateColors = getStateColor(state);
  
  const getPnlColor = (pnl) => {
    if (pnl > 0) return 'text-green-700';
    if (pnl < 0) return 'text-red-700';
    return 'text-neutral-500';
  };
  
  const exposureWidth = Math.min((exposurePct / 100) * 100, 100);
  
  return (
    <div 
      className="bg-white rounded-xl border border-neutral-200 shadow-sm overflow-hidden hover:shadow-md transition-shadow duration-200" 
      data-testid="risk-health-panel"
      style={{ fontFamily: 'Gilroy, sans-serif' }}
    >
      {/* Header */}
      <div className="px-4 py-3 bg-neutral-50 border-b border-neutral-200">
        <div className="flex items-center gap-2">
          <Shield className="w-4 h-4 text-blue-600" />
          <h3 className="text-xs font-bold text-neutral-700 uppercase tracking-wider">
            RISK HEALTH
          </h3>
        </div>
      </div>
      
      {/* Content */}
      <div className="p-4 space-y-3">
        {/* Risk State Card */}
        <div className={`px-3 py-2 rounded-lg border ${stateColors.bg} ${stateColors.border}`}>
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-neutral-600">RISK STATE</span>
            <div className="flex items-center gap-2">
              {state !== 'NORMAL' && <AlertTriangle className={`w-3.5 h-3.5 ${stateColors.text}`} />}
              <span className={`text-sm font-bold ${stateColors.text}`}>
                {state}
              </span>
            </div>
          </div>
        </div>
        
        {/* Exposure Bar */}
        <div className="space-y-1.5">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-neutral-600">EXPOSURE</span>
            <span className={`text-sm font-bold ${exposurePct > 70 ? 'text-yellow-700' : 'text-neutral-700'}`}>
              {exposurePct.toFixed(1)}%
            </span>
          </div>
          <div className="w-full h-2 bg-neutral-100 rounded-full overflow-hidden">
            <div 
              className={`h-full transition-all duration-300 ${exposurePct > 70 ? 'bg-yellow-500' : 'bg-blue-500'}`}
              style={{ width: `${exposureWidth}%` }}
            />
          </div>
        </div>
        
        {/* Positions */}
        <div className="flex items-center justify-between py-2 border-b border-neutral-100">
          <span className="text-xs font-semibold text-neutral-600">POSITIONS</span>
          <span className="text-sm font-bold text-neutral-900">
            {activePositions} / {maxPositions}
          </span>
        </div>
        
        {/* Daily PnL */}
        <div className="flex items-center justify-between py-2 border-b border-neutral-100">
          <span className="text-xs font-semibold text-neutral-600">DAILY P&L</span>
          <div className="flex items-center gap-1">
            {dailyPnl > 0 && <TrendingUp className="w-3 h-3 text-green-700" />}
            {dailyPnl < 0 && <TrendingDown className="w-3 h-3 text-red-700" />}
            <span className={`text-sm font-bold font-mono ${getPnlColor(dailyPnl)}`}>
              {dailyPnl >= 0 ? '+' : ''}${dailyPnl.toFixed(2)}
            </span>
          </div>
        </div>
        
        {/* Loss Limit */}
        <div className="flex items-center justify-between py-2 border-b border-neutral-100">
          <span className="text-xs font-semibold text-neutral-600">LOSS LIMIT</span>
          <span className="text-sm font-mono text-neutral-700">
            ${lossLimit}
          </span>
        </div>
        
        {/* Rejects */}
        <div className="pt-2 space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-xs text-neutral-500">Rejects (1h)</span>
            <span className={`text-xs font-bold ${rejectsLastHour > 0 ? 'text-yellow-700' : 'text-neutral-500'}`}>
              {rejectsLastHour}
            </span>
          </div>
          {lastRejectReason && (
            <div className="px-2 py-1 bg-yellow-50 border border-yellow-200 rounded text-xs text-yellow-800">
              Last: {lastRejectReason}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
