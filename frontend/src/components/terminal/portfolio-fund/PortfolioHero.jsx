import { useState } from 'react';
import { WsConnectionBadge } from '../WsConnectionBadge';

export default function PortfolioHero({ summary, loading, isConnected = false, error = null }) {
  const [selectedInterval, setSelectedInterval] = useState('7D');

  // Error state
  if (error) {
    return (
      <div className="border-b border-[#E5E7EB] pb-4" data-testid="portfolio-hero-error">
        <div className="flex flex-col items-center justify-center h-32 gap-3">
          <span className="text-sm text-red-500">Failed to load portfolio: {error}</span>
          <button
            onClick={() => window.location.reload()}
            className="px-4 py-2 text-xs bg-red-500/10 text-red-600 rounded hover:bg-red-500/20 transition"
          >
            Retry
          </button>
        </div>
      </div>
    );
  }

  // Loading state
  if (loading || !summary) {
    return (
      <div className="border-b border-[#E5E7EB] pb-4" data-testid="portfolio-hero">
        <div className="flex items-center justify-center h-32">
          <span className="text-sm text-neutral-500">Loading portfolio...</span>
        </div>
      </div>
    );
  }

  const {
    total_equity,
    total_pnl,
    total_return_pct,
    cash_balance,
    ath,
    drawdown_pct,
    deployment_pct
  } = summary;

  // Calculate PnL for different intervals (approximation based on 7D)
  const intervals = {
    '1H': { pnl: total_pnl * 0.02, pct: total_return_pct * 0.02 },
    '6H': { pnl: total_pnl * 0.15, pct: total_return_pct * 0.15 },
    '24H': { pnl: total_pnl * 0.45, pct: total_return_pct * 0.45 },
    '7D': { pnl: total_pnl, pct: total_return_pct },
    '30D': { pnl: total_pnl, pct: total_return_pct }
  };

  const currentInterval = intervals[selectedInterval];

  // Narrative based on deployment %
  let narrative = '';
  if (deployment_pct < 20) {
    narrative = 'System is mostly in cash and waiting for stronger edge';
  } else if (deployment_pct >= 20 && deployment_pct <= 60) {
    narrative = 'System is selectively deploying capital';
  } else {
    narrative = 'System is aggressively deployed into active positions';
  }

  return (
    <div className="border-b border-[#E5E7EB] pb-4" data-testid="portfolio-hero">
      <div className="flex items-start justify-between">
        {/* LEFT: Main Value */}
        <div>
          <div className="flex items-center gap-3 mb-1">
            <div className="text-[48px] font-bold tracking-tight text-gray-900 leading-none" style={{ fontVariantNumeric: 'tabular-nums' }}>
              ${total_equity.toLocaleString()}
            </div>
            <WsConnectionBadge isConnected={isConnected} />
          </div>
          
          {/* PnL with Interval Selector */}
          <div className="flex items-center gap-3 mt-1.5">
            <div className={`text-[24px] font-semibold ${currentInterval.pnl >= 0 ? 'text-green-600' : 'text-red-600'}`} style={{ fontVariantNumeric: 'tabular-nums' }}>
              {currentInterval.pnl >= 0 ? '+' : ''}${currentInterval.pnl.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })} ({currentInterval.pnl >= 0 ? '+' : ''}{currentInterval.pct.toFixed(2)}%)
            </div>
            
            {/* Interval Buttons */}
            <div className="flex items-center gap-1">
              {['1H', '6H', '24H', '7D', '30D'].map(interval => (
                <button
                  key={interval}
                  onClick={() => setSelectedInterval(interval)}
                  className={`px-2 py-0.5 text-xs font-medium rounded transition-colors ${
                    selectedInterval === interval
                      ? 'bg-gray-900 text-white'
                      : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                  }`}
                >
                  {interval}
                </button>
              ))}
            </div>
          </div>

          <p className="text-xs text-gray-500 mt-1.5">
            {narrative}
          </p>

          {/* Inline Stats */}
          <div className="flex items-center gap-6 mt-3 text-xs" style={{ fontVariantNumeric: 'tabular-nums' }}>
            <div>
              <span className="text-gray-500">Cash </span>
              <span className="text-gray-900 font-medium">${cash_balance.toLocaleString()}</span>
            </div>
            <div>
              <span className="text-gray-500">Exposure </span>
              <span className="text-gray-900 font-medium">{deployment_pct.toFixed(2)}%</span>
            </div>
            <div>
              <span className="text-gray-500">ATH </span>
              <span className="text-gray-900 font-medium">${ath.toLocaleString()}</span>
            </div>
            <div>
              <span className="text-gray-500">DD </span>
              <span className={`font-medium ${drawdown_pct < 0 ? 'text-red-600' : 'text-gray-900'}`}>
                {drawdown_pct.toFixed(2)}%
              </span>
            </div>
          </div>
        </div>

        {/* RIGHT: Live Indicator only */}
        <div className="flex items-center gap-2">
          <div className="w-2 h-2 rounded-full bg-green-500 animate-pulse"></div>
          <span className="text-xs text-gray-600 font-medium">LIVE</span>
        </div>
      </div>
    </div>
  );
}
