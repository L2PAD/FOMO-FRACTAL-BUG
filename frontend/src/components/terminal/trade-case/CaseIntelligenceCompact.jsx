export default function CaseIntelligenceCompact({ caseData }) {
  if (!caseData) {
    return (
      <div className="flex items-center justify-center h-full" data-testid="case-intelligence-compact-empty">
        <p className="text-xs text-neutral-500">No case</p>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full gap-3 p-4" data-testid="case-intelligence-compact">
      {/* Block 1: Current Thesis */}
      <div className="bg-blue-50 rounded-lg p-3 border border-blue-200">
        <h3 className="text-xs font-bold text-blue-900 mb-1.5 uppercase tracking-wide">
          Thesis
        </h3>
        <p className="text-xs text-blue-900 leading-relaxed">
          {caseData.thesis || 'No thesis'}
        </p>
      </div>

      {/* Block 2: Strategy */}
      <div className="bg-white rounded-lg p-3 border border-neutral-200">
        <h3 className="text-xs font-bold text-neutral-500 mb-1.5 uppercase tracking-wide">
          Strategy
        </h3>
        <div className="text-xs text-neutral-900 font-bold">
          {caseData.strategy ? caseData.strategy.toUpperCase().replace('_', ' ') : 'N/A'}
        </div>
        <p className="text-xs text-neutral-600 mt-1">
          TF: {caseData.trading_tf || 'N/A'}
        </p>
      </div>

      {/* Block 3: Why Switched */}
      {caseData.switched_from && (
        <div className="bg-orange-50 rounded-lg p-3 border border-orange-200">
          <h3 className="text-xs font-bold text-orange-900 mb-1.5 uppercase tracking-wide">
            Why Switched
          </h3>
          <div className="text-xs text-orange-900 mb-1">
            <span className="font-bold">{caseData.switched_from}</span> → <span className="font-bold">{caseData.direction}</span>
          </div>
          <p className="text-xs text-orange-900 italic">
            {caseData.switch_reason || 'No reason'}
          </p>
        </div>
      )}

      {/* Block 4: Execution */}
      {caseData.execution_summary && (
        <div className="bg-white rounded-lg p-3 border border-neutral-200">
          <h3 className="text-xs font-bold text-neutral-500 mb-1.5 uppercase tracking-wide">
            Execution
          </h3>
          <div className="space-y-1 text-xs">
            <div className="flex justify-between">
              <span className="text-neutral-600">Fills:</span>
              <span className="font-bold text-neutral-900">{caseData.execution_summary.fills}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-neutral-600">Slip:</span>
              <span className="font-bold text-neutral-900">{caseData.execution_summary.slippage_pct}%</span>
            </div>
            <div className="flex justify-between">
              <span className="text-neutral-600">Fees:</span>
              <span className="font-bold text-neutral-900">${caseData.execution_summary.fees_usd}</span>
            </div>
          </div>
        </div>
      )}

      {/* Block 5: Stats */}
      <div className="bg-white rounded-lg p-3 border border-neutral-200">
        <h3 className="text-xs font-bold text-neutral-500 mb-1.5 uppercase tracking-wide">
          Stats
        </h3>
        <div className="space-y-1 text-xs">
          <div className="flex justify-between">
            <span className="text-neutral-600">Duration:</span>
            <span className="font-bold text-neutral-900">{caseData.duration}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-neutral-600">Trades:</span>
            <span className="font-bold text-neutral-900">{caseData.trade_count}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-neutral-600">W/L:</span>
            <span className="font-bold text-neutral-900">
              {caseData.win_count}W / {caseData.loss_count}L
            </span>
          </div>
          <div className="flex justify-between">
            <span className="text-neutral-600">PnL:</span>
            <span className={`font-bold ${caseData.pnl >= 0 ? 'text-green-700' : 'text-red-700'}`}>
              {caseData.pnl >= 0 ? '+' : ''}${caseData.pnl}
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}
