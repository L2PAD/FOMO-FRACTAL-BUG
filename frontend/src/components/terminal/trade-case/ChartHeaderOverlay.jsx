import { useState } from 'react';

const VIEW_TIMEFRAMES = ['1m', '5m', '15m', '1h', '4h', '1d', '1w'];

export default function ChartHeaderOverlay({ caseData, hasPosition }) {
  const [viewTF, setViewTF] = useState('1h');

  const tradingTF = caseData?.trading_tf || '4H';
  const symbol = caseData?.symbol?.replace('USDT', '') || 'BTC';
  const caseId = caseData?.id?.replace('case_', '') || '—';
  const direction = caseData?.direction || 'NONE';
  const status = caseData?.status || 'NONE';
  const pnl = caseData?.pnl_pct || 0;

  return (
    <div
      className="absolute top-0 left-0 right-0 h-10 px-3 flex items-center justify-between bg-white/95 backdrop-blur-sm border-b border-[#E5E7EB] z-10"
      data-testid="chart-header-overlay"
      style={{ fontFamily: 'Gilroy, sans-serif', fontVariantNumeric: 'tabular-nums' }}
    >
      {/* LEFT: Symbol + Status */}
      <div className="flex items-center gap-2 text-xs">
        <span className="font-bold text-neutral-900">
          {symbol}/USDT · #{caseId}
        </span>
        
        {hasPosition ? (
          <>
            <span className={`font-bold px-1.5 py-0.5 rounded-lg ${
              direction === 'LONG' ? 'bg-green-50 text-green-700' : 'bg-red-50 text-red-700'
            }`}>
              {direction} {status}
            </span>
            <span className={`font-bold ${pnl >= 0 ? 'text-green-700' : 'text-red-700'}`}>
              {pnl >= 0 ? '+' : ''}{pnl.toFixed(1)}%
            </span>
          </>
        ) : (
          <span className="text-neutral-500">
            NO POSITION · WAITING
          </span>
        )}
      </div>

      {/* CENTER: Timeframes */}
      <div className="flex items-center gap-3">
        <div className="flex items-center gap-1.5">
          <span className="text-xs text-neutral-500">Trading:</span>
          <span className="px-1.5 py-0.5 rounded-lg bg-blue-50 text-blue-700 font-bold text-xs">
            {tradingTF}
          </span>
        </div>

        <div className="w-px h-3 bg-neutral-300" />

        <div className="flex items-center gap-1.5">
          <span className="text-xs text-neutral-500">View:</span>
          <select
            value={viewTF}
            onChange={(e) => setViewTF(e.target.value)}
            className="px-1.5 py-0.5 rounded-lg bg-white border border-[#E5E7EB] text-neutral-900 font-bold text-xs cursor-pointer"
          >
            {VIEW_TIMEFRAMES.map((tf) => (
              <option key={tf} value={tf}>
                {tf.toUpperCase()}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* RIGHT: Live */}
      <div className="flex items-center gap-1.5">
        <div className="w-1.5 h-1.5 rounded-full bg-green-500 animate-pulse" />
        <span className="text-xs text-neutral-500">LIVE</span>
      </div>
    </div>
  );
}
