export default function CaseIntelligenceMinimal({ caseData }) {
  if (!caseData) {
    return (
      <div className="flex items-center justify-center h-full">
        <p className="text-xs text-neutral-400">No case</p>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full gap-2 p-3" data-testid="case-intelligence-minimal">
      {/* Section 1: Thesis */}
      <div className="bg-blue-50 rounded-lg p-2.5 border border-blue-200">
        <h3 className="text-xs font-bold text-blue-900 mb-1 uppercase">
          Thesis
        </h3>
        <p className="text-xs text-blue-900 leading-snug">
          {caseData.thesis || 'No thesis'}
        </p>
        {caseData.switched_from && (
          <p className="text-xs text-orange-700 mt-1.5 italic">
            ↑ Switched from {caseData.switched_from}: {caseData.switch_reason}
          </p>
        )}
      </div>

      {/* Section 2: Execution */}
      {caseData.execution_summary && (
        <div className="bg-white rounded-lg p-2.5 border border-[#E5E7EB]">
          <h3 className="text-xs font-bold text-neutral-500 mb-1 uppercase">
            Execution
          </h3>
          <div className="grid grid-cols-2 gap-x-2 gap-y-0.5 text-xs">
            <span className="text-neutral-600">Fills:</span>
            <span className="font-bold text-neutral-900 text-right">{caseData.execution_summary.fills}</span>
            <span className="text-neutral-600">Slip:</span>
            <span className="font-bold text-neutral-900 text-right">{caseData.execution_summary.slippage_pct}%</span>
            <span className="text-neutral-600">Fees:</span>
            <span className="font-bold text-neutral-900 text-right">${caseData.execution_summary.fees_usd}</span>
            <span className="text-neutral-600">Quality:</span>
            <span className={`font-bold text-right ${
              caseData.execution_summary.quality === 'GOOD' ? 'text-green-700' :
              caseData.execution_summary.quality === 'FAIR' ? 'text-orange-700' : 'text-red-700'
            }`}>
              {caseData.execution_summary.quality}
            </span>
          </div>
        </div>
      )}

      {/* Section 3: Stats */}
      <div className="bg-white rounded-lg p-2.5 border border-[#E5E7EB]">
        <h3 className="text-xs font-bold text-neutral-500 mb-1 uppercase">
          Stats
        </h3>
        <div className="grid grid-cols-2 gap-x-2 gap-y-0.5 text-xs">
          <span className="text-neutral-600">Duration:</span>
          <span className="font-bold text-neutral-900 text-right">{caseData.duration}</span>
          <span className="text-neutral-600">Trades:</span>
          <span className="font-bold text-neutral-900 text-right">{caseData.trade_count}</span>
          <span className="text-neutral-600">W/L:</span>
          <span className="font-bold text-neutral-900 text-right">
            {caseData.win_count}W / {caseData.loss_count}L
          </span>
          <span className="text-neutral-600">PnL:</span>
          <span className={`font-bold text-right ${caseData.pnl >= 0 ? 'text-green-700' : 'text-red-700'}`}>
            ${caseData.pnl} ({caseData.pnl_pct >= 0 ? '+' : ''}{caseData.pnl_pct}%)
          </span>
        </div>
      </div>

      {/* Section 4: Strategy (если нужно) */}
      <div className="bg-neutral-50 rounded-lg p-2 border border-[#E5E7EB]">
        <div className="flex justify-between items-center text-xs">
          <span className="text-neutral-600">Strategy:</span>
          <span className="font-bold text-neutral-900">
            {caseData.strategy ? caseData.strategy.toUpperCase().replace('_', ' ') : 'N/A'}
          </span>
        </div>
        <div className="flex justify-between items-center text-xs mt-0.5">
          <span className="text-neutral-600">TF:</span>
          <span className="font-bold text-neutral-900">{caseData.trading_tf}</span>
        </div>
      </div>
    </div>
  );
}
