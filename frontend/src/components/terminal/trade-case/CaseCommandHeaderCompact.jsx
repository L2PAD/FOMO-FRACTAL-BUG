export default function CaseCommandHeaderCompact({ caseData }) {
  if (!caseData) {
    return (
      <div
        className="bg-neutral-50 px-4 py-3 border-b border-neutral-200"
        data-testid="case-command-header-empty"
      >
        <p className="text-sm text-neutral-500">No case selected</p>
      </div>
    );
  }

  const isLong = caseData.direction === 'LONG';
  const bgColor = isLong ? 'bg-green-50' : 'bg-red-50';
  const borderColor = isLong ? 'border-l-green-500' : 'border-l-red-500';

  return (
    <div
      className={`${bgColor} px-4 py-3 border-b border-neutral-200 border-l-4 ${borderColor}`}
      data-testid="case-command-header-compact"
    >
      {/* Top Row: Title + Meta */}
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-3">
          <h2 className="text-lg font-bold text-neutral-900">
            {caseData.symbol.replace('USDT', '')} · CASE #{caseData.id.replace('case_', '')}
          </h2>
          <div className="flex items-center gap-1.5">
            <div className="w-1.5 h-1.5 rounded-full bg-green-500 animate-pulse" />
            <span className="text-xs text-neutral-500 font-medium uppercase">LIVE</span>
          </div>
        </div>
        
        <div className="flex items-center gap-3 text-sm">
          <span
            className={`font-bold px-2.5 py-1 rounded ${
              isLong ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'
            }`}
          >
            {caseData.direction} {caseData.status}
          </span>
          <span className={`font-bold ${caseData.pnl >= 0 ? 'text-green-700' : 'text-red-700'}`}>
            {caseData.pnl >= 0 ? '+' : ''}{caseData.pnl_pct.toFixed(1)}%
          </span>
          <span className="text-neutral-600">{caseData.duration}</span>
          <span className="text-neutral-500">·</span>
          <span className="text-neutral-600">{caseData.trade_count} exec</span>
        </div>
      </div>

      {/* Three Core Blocks - Horizontal */}
      <div className="grid grid-cols-3 gap-4">
        {/* WHY THIS TRADE EXISTS */}
        <div>
          <h3 className="text-xs font-bold text-neutral-500 mb-1 uppercase tracking-wide">
            Why This Trade Exists
          </h3>
          <p className="text-sm text-neutral-800 leading-snug">
            {caseData.thesis || 'No thesis available'}
          </p>
        </div>

        {/* WHAT SYSTEM WILL DO NEXT */}
        <div>
          <h3 className="text-xs font-bold text-neutral-500 mb-1 uppercase tracking-wide">
            What System Will Do Next
          </h3>
          <p className="text-sm text-neutral-800 leading-snug">
            {caseData.next_action || 'Monitoring position'}
          </p>
        </div>

        {/* WHAT BREAKS THIS TRADE */}
        <div>
          <h3 className="text-xs font-bold text-neutral-500 mb-1 uppercase tracking-wide">
            What Breaks This Trade
          </h3>
          <p className="text-sm text-neutral-800 leading-snug">
            {caseData.direction === 'LONG' ? 'Below' : 'Above'} {caseData.stop || 'N/A'}
          </p>
        </div>
      </div>
    </div>
  );
}
