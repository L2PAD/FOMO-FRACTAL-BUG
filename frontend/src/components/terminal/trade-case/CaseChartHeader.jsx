import { useState } from 'react';

const VIEW_TIMEFRAMES = ['1m', '5m', '15m', '1h', '4h', '1d', '1w'];

export default function CaseChartHeader({ caseData }) {
  const [viewTF, setViewTF] = useState('1h');

  if (!caseData) {
    return null;
  }

  const tradingTF = caseData.trading_tf || '4H';

  return (
    <div
      className="flex items-center justify-between px-4 py-3 bg-white border-b border-neutral-200"
      data-testid="case-chart-header"
    >
      {/* Left: Symbol + Case */}
      <div className="flex items-center gap-3">
        <h2 className="text-lg font-bold text-neutral-900">
          {caseData.symbol.replace('USDT', '')}/USDT
        </h2>
        <span className="text-xs text-neutral-500">Case #{caseData.id.replace('case_', '')}</span>
      </div>

      {/* Right: Timeframes */}
      <div className="flex items-center gap-4">
        {/* Trading TF (fixed, system) */}
        <div className="flex items-center gap-2">
          <span className="text-xs text-neutral-500 font-medium">Trading TF:</span>
          <div className="px-3 py-1.5 rounded-lg bg-blue-100 text-blue-700 font-bold text-sm border border-blue-200">
            {tradingTF}
          </div>
        </div>

        {/* View TF (user dropdown) */}
        <div className="flex items-center gap-2">
          <span className="text-xs text-neutral-500 font-medium">View TF:</span>
          <select
            value={viewTF}
            onChange={(e) => setViewTF(e.target.value)}
            className="px-3 py-1.5 rounded-lg bg-white border border-neutral-300 text-neutral-900 font-bold text-sm cursor-pointer transition-all duration-150 hover:bg-neutral-50 hover:border-neutral-400"
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
    </div>
  );
}
