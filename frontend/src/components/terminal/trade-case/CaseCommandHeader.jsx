export default function CaseCommandHeader({ caseData }) {
  if (!caseData) {
    return (
      <div
        className="bg-neutral-50 rounded-2xl p-6 border border-neutral-200 shadow-sm transition-all duration-150 hover:shadow-md"
        data-testid="case-command-header-empty"
      >
        <div className="text-center py-8">
          <p className="text-sm text-neutral-500 font-medium">No active case selected</p>
          <p className="text-xs text-neutral-400 mt-1">Select a case from the left rail</p>
        </div>
      </div>
    );
  }

  const isLong = caseData.direction === 'LONG';
  const bgColor = isLong ? 'bg-green-50' : 'bg-red-50';
  const borderColor = isLong ? 'border-green-100' : 'border-red-100';
  const accentBorder = isLong ? 'border-l-green-500' : 'border-l-red-500';

  return (
    <div
      className={`${bgColor} rounded-2xl p-6 border ${borderColor} border-l-4 ${accentBorder} shadow-sm transition-all duration-150 hover:shadow-md hover:-translate-y-0.5`}
      data-testid="case-command-header"
    >
      {/* Live indicator */}
      <div className="flex items-center gap-2 mb-3">
        <div className="w-2 h-2 rounded-full bg-green-500 animate-pulse" />
        <span className="text-xs text-neutral-500 font-medium uppercase tracking-wide">LIVE</span>
      </div>

      {/* Case ID + Symbol */}
      <div className="mb-4">
        <h1 className="text-2xl font-bold text-neutral-900 mb-2">
          {caseData.symbol.replace('USDT', '')} · CASE #{caseData.id.replace('case_', '')}
        </h1>
        <div className="flex items-center gap-3 text-sm">
          <span
            className={`font-bold px-3 py-1 rounded-lg ${
              isLong ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'
            }`}
          >
            {caseData.direction} {caseData.status}
          </span>
          <span className="text-neutral-600">{caseData.duration}</span>
          <span className="text-neutral-500">·</span>
          <span className="text-neutral-600">{caseData.trade_count} executions</span>
          <span className="text-neutral-500">·</span>
          <span className={`font-bold ${caseData.pnl >= 0 ? 'text-green-700' : 'text-red-700'}`}>
            {caseData.pnl >= 0 ? '+' : ''}{caseData.pnl_pct.toFixed(1)}%
          </span>
        </div>
      </div>

      {/* System Thesis */}
      <div className="mb-4">
        <h3 className="text-xs font-bold text-neutral-500 mb-2 uppercase tracking-wider">
          System Thesis
        </h3>
        <p className="text-base font-medium text-neutral-800">
          {caseData.thesis || 'No thesis available'}
        </p>
      </div>

      {/* Next System Action */}
      <div className="mb-5">
        <h3 className="text-xs font-bold text-neutral-500 mb-2 uppercase tracking-wider">
          Next System Action
        </h3>
        <p className="text-sm text-neutral-700">
          {caseData.next_action || 'Monitoring position'}
        </p>
      </div>

      {/* Action Pills */}
      <div className="flex gap-2.5 flex-wrap">
        <button
          className="px-4 py-2 rounded-lg border bg-white border-neutral-300 text-neutral-700 font-semibold text-xs uppercase tracking-wide transition-all duration-150 hover:scale-105 hover:bg-neutral-50"
          data-testid="action-entry"
        >
          Entry
        </button>
        <button
          className="px-4 py-2 rounded-lg border bg-white border-neutral-300 text-neutral-700 font-semibold text-xs uppercase tracking-wide transition-all duration-150 hover:scale-105 hover:bg-neutral-50"
          data-testid="action-add"
        >
          Add
        </button>
        <button
          className="px-4 py-2 rounded-lg border bg-white border-neutral-300 text-neutral-700 font-semibold text-xs uppercase tracking-wide transition-all duration-150 hover:scale-105 hover:bg-neutral-50"
          data-testid="action-exit"
        >
          Exit
        </button>
      </div>
    </div>
  );
}
