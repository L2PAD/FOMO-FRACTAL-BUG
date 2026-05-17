// Session Metrics Panel

import React from 'react';
import { BarChart3, TrendingUp, TrendingDown } from 'lucide-react';

export default function SessionMetricsPanel({ sessionStats }) {
  const trades = sessionStats?.trades || 0;
  const winRate = sessionStats?.win_rate || 0;
  const avgWin = sessionStats?.avg_win || 0;
  const avgLoss = sessionStats?.avg_loss || 0;
  const bestSymbol = sessionStats?.best_symbol;
  const bestPnl = sessionStats?.best_pnl || 0;
  const worstSymbol = sessionStats?.worst_symbol;
  const worstPnl = sessionStats?.worst_pnl || 0;
  
  const winRateWidth = Math.min(winRate, 100);
  
  return (
    <div 
      className="bg-white rounded-xl border border-neutral-200 shadow-sm overflow-hidden hover:shadow-md transition-shadow duration-200" 
      data-testid="session-metrics-panel"
      style={{ fontFamily: 'Gilroy, sans-serif' }}
    >
      {/* Header */}
      <div className="px-4 py-3 bg-neutral-50 border-b border-neutral-200">
        <div className="flex items-center gap-2">
          <BarChart3 className="w-4 h-4 text-blue-600" />
          <h3 className="text-xs font-bold text-neutral-700 uppercase tracking-wider">
            SESSION METRICS
          </h3>
        </div>
      </div>
      
      {/* Content */}
      <div className="p-4 space-y-3">
        {/* Trades Count */}
        <div className="flex items-center justify-between py-2 border-b border-neutral-100">
          <span className="text-xs font-semibold text-neutral-600">TRADES</span>
          <span className="text-xl font-bold text-neutral-900">{trades}</span>
        </div>
        
        {/* Win Rate Bar */}
        <div className="space-y-1.5">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-neutral-600">WIN RATE</span>
            <span className={`text-sm font-bold ${winRate >= 50 ? 'text-green-700' : 'text-red-700'}`}>
              {winRate}%
            </span>
          </div>
          <div className="w-full h-2 bg-neutral-100 rounded-full overflow-hidden">
            <div 
              className={`h-full transition-all duration-300 ${winRate >= 50 ? 'bg-green-500' : 'bg-red-500'}`}
              style={{ width: `${winRateWidth}%` }}
            />
          </div>
        </div>
        
        {/* Avg Win/Loss */}
        <div className="grid grid-cols-2 gap-3 pt-2">
          <div className="px-3 py-2 bg-green-50 border border-green-200 rounded-lg">
            <div className="flex items-center gap-1 mb-1">
              <TrendingUp className="w-3 h-3 text-green-700" />
              <span className="text-xs font-semibold text-green-700">AVG WIN</span>
            </div>
            <span className="text-sm font-bold font-mono text-green-700">
              +${avgWin.toFixed(2)}
            </span>
          </div>
          
          <div className="px-3 py-2 bg-red-50 border border-red-200 rounded-lg">
            <div className="flex items-center gap-1 mb-1">
              <TrendingDown className="w-3 h-3 text-red-700" />
              <span className="text-xs font-semibold text-red-700">AVG LOSS</span>
            </div>
            <span className="text-sm font-bold font-mono text-red-700">
              ${avgLoss.toFixed(2)}
            </span>
          </div>
        </div>
        
        {/* Best/Worst */}
        {bestSymbol && (
          <div className="space-y-2 pt-2 border-t border-neutral-100">
            <div className="flex items-center justify-between px-2 py-1.5 bg-green-50 rounded border border-green-100">
              <span className="text-xs text-green-700 font-semibold">BEST</span>
              <div className="flex items-center gap-2">
                <span className="text-xs font-mono text-neutral-700">{bestSymbol}</span>
                <span className="text-xs font-bold font-mono text-green-700">+${bestPnl.toFixed(2)}</span>
              </div>
            </div>
          </div>
        )}
        
        {worstSymbol && (
          <div className="flex items-center justify-between px-2 py-1.5 bg-red-50 rounded border border-red-100">
            <span className="text-xs text-red-700 font-semibold">WORST</span>
            <div className="flex items-center gap-2">
              <span className="text-xs font-mono text-neutral-700">{worstSymbol}</span>
              <span className="text-xs font-bold font-mono text-red-700">${worstPnl.toFixed(2)}</span>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
