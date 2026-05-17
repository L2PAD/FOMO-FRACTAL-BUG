import { useState } from 'react';

const VIEW_TIMEFRAMES = ['1m', '5m', '15m', '1h', '4h', '1d', '1w'];

export default function CaseChartHeaderEnhanced({ caseData, hasPosition }) {
  const [viewTF, setViewTF] = useState('1h');

  const tradingTF = caseData?.trading_tf || '4H';
  const symbol = caseData?.symbol?.replace('USDT', '') || 'BTC';
  const caseId = caseData?.id?.replace('case_', '') || '—';
  const direction = caseData?.direction || 'NONE';
  const status = caseData?.status || 'NONE';
  const pnl = caseData?.pnl_pct || 0;

  return (
    <div
      className="flex items-center justify-between h-12 px-4 border-b border-neutral-200 bg-white"
      data-testid="case-chart-header-enhanced"
    >
      {/* LEFT: Symbol + Status */}
      <div className="flex items-center gap-3">
        <div className="font-bold text-sm text-neutral-900">
          {symbol}/USDT · CASE #{caseId}
        </div>
        
        {hasPosition ? (
          <div className="flex items-center gap-2">
            <span
              className={`text-xs font-bold px-2 py-0.5 rounded ${
                direction === 'LONG' ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'
              }`}
            >
              {direction} {status}
            </span>
            <span className={`text-xs font-bold ${pnl >= 0 ? 'text-green-700' : 'text-red-700'}`}>
              {pnl >= 0 ? '+' : ''}{pnl.toFixed(1)}%
            </span>
          </div>
        ) : (
          <div className="flex items-center gap-2">
            <span className="text-xs font-medium text-neutral-600">
              NO POSITION · WAITING FOR SETUP
            </span>
          </div>
        )}
      </div>

      {/* CENTER: Timeframes */}
      <div className="flex items-center gap-4">
        <div className="flex items-center gap-2">
          <span className="text-xs text-neutral-500 font-medium">Trading TF:</span>
          <div className="px-2.5 py-1 rounded bg-blue-100 text-blue-700 font-bold text-xs border border-blue-200">
            {tradingTF}
          </div>
        </div>

        <div className="w-px h-4 bg-neutral-300" />

        <div className="flex items-center gap-2">
          <span className="text-xs text-neutral-500 font-medium">View:</span>
          <select
            value={viewTF}
            onChange={(e) => setViewTF(e.target.value)}
            className="px-2.5 py-1 rounded bg-white border border-neutral-300 text-neutral-900 font-bold text-xs cursor-pointer hover:bg-neutral-50 hover:border-neutral-400 transition-all"
            data-testid="view-tf-selector"
          >
            {VIEW_TIMEFRAMES.map((tf) => (
              <option key={tf} value={tf}>
                {tf.toUpperCase()}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* RIGHT: Controls */}
      <div className="flex items-center gap-3">
        <div className="flex items-center gap-1.5">
          <div className="w-2 h-2 rounded-full bg-green-500 animate-pulse" />
          <span className="text-xs text-neutral-500 font-medium">LIVE</span>
        </div>
        
        <button className="text-xs text-neutral-600 hover:text-neutral-900 transition-colors">
          Indicators
        </button>
        <button className="text-xs text-neutral-600 hover:text-neutral-900 transition-colors">
          Heatmap
        </button>
      </div>
    </div>
  );
}
