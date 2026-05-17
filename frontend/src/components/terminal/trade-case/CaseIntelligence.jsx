export default function CaseIntelligence({ caseData }) {
  if (!caseData) {
    return (
      <div className="flex items-center justify-center h-full" data-testid="case-intelligence-empty">
        <p className="text-sm text-neutral-500">No case selected</p>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full gap-4" data-testid="case-intelligence">
      {/* Block 1: Current Thesis */}
      <div className="bg-blue-50 rounded-xl p-4 border border-blue-200 transition-all duration-150 hover:bg-blue-100">
        <h3 className="text-xs font-bold text-blue-900 mb-3 uppercase tracking-wider">
          Current Thesis
        </h3>
        <p className="text-sm text-blue-900 leading-relaxed">
          {caseData.thesis || 'No thesis available'}
        </p>
      </div>

      {/* Block 2: Strategy Used */}
      <div className="bg-white rounded-xl p-4 border border-neutral-200 transition-all duration-150 hover:bg-neutral-50">
        <h3 className="text-xs font-bold text-neutral-500 mb-3 uppercase tracking-wider">
          Strategy Used
        </h3>
        <div className="text-sm text-neutral-900 font-bold">
          {caseData.strategy ? caseData.strategy.toUpperCase().replace('_', ' ') : 'N/A'}
        </div>
        <p className="text-xs text-neutral-600 mt-2">
          TF: {caseData.trading_tf || 'N/A'}
        </p>
      </div>

      {/* Block 3: Why Switched */}
      {caseData.switched_from && (
        <div className="bg-orange-50 rounded-xl p-4 border border-orange-200 transition-all duration-150 hover:bg-orange-100">
          <h3 className="text-xs font-bold text-orange-900 mb-3 uppercase tracking-wider">
            Why Switched
          </h3>
          <div className="text-sm text-orange-900 mb-2">
            <span className="font-bold">{caseData.switched_from}</span> → <span className="font-bold">{caseData.direction}</span>
          </div>
          <p className="text-xs text-orange-900 italic">
            {caseData.switch_reason || 'No reason available'}
          </p>
        </div>
      )}

      {/* Block 4: Execution Summary */}
      {caseData.execution_summary && (
        <div className="bg-white rounded-xl p-4 border border-neutral-200 transition-all duration-150 hover:bg-neutral-50">
          <h3 className="text-xs font-bold text-neutral-500 mb-3 uppercase tracking-wider">
            Execution Summary
          </h3>
          <div className="space-y-1.5 text-sm">
            <div className="flex justify-between">
              <span className="text-neutral-600">Fills:</span>
              <span className="font-bold text-neutral-900">{caseData.execution_summary.fills}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-neutral-600">Slippage:</span>
              <span className="font-bold text-neutral-900">{caseData.execution_summary.slippage_pct}%</span>
            </div>
            <div className="flex justify-between">
              <span className="text-neutral-600">Fees:</span>
              <span className="font-bold text-neutral-900">${caseData.execution_summary.fees_usd}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-neutral-600">Quality:</span>
              <span
                className={`font-bold ${
                  caseData.execution_summary.quality === 'GOOD'
                    ? 'text-green-700'
                    : caseData.execution_summary.quality === 'FAIR'
                    ? 'text-orange-700'
                    : 'text-red-700'
                }`}
              >
                {caseData.execution_summary.quality}
              </span>
            </div>
          </div>
        </div>
      )}

      {/* Block 5: Case Stats */}
      <div className="bg-white rounded-xl p-4 border border-neutral-200 transition-all duration-150 hover:bg-neutral-50">
        <h3 className="text-xs font-bold text-neutral-500 mb-3 uppercase tracking-wider">
          Case Stats
        </h3>
        <div className="space-y-1.5 text-sm">
          <div className="flex justify-between">
            <span className="text-neutral-600">Duration:</span>
            <span className="font-bold text-neutral-900">{caseData.duration}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-neutral-600">Total Trades:</span>
            <span className="font-bold text-neutral-900">{caseData.trade_count}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-neutral-600">Win/Loss:</span>
            <span className="font-bold text-neutral-900">
              {caseData.win_count}W / {caseData.loss_count}L
            </span>
          </div>
          <div className="flex justify-between">
            <span className="text-neutral-600">PnL:</span>
            <span className={`font-bold ${caseData.pnl >= 0 ? 'text-green-700' : 'text-red-700'}`}>
              {caseData.pnl >= 0 ? '+' : ''}${caseData.pnl} ({caseData.pnl_pct >= 0 ? '+' : ''}{caseData.pnl_pct}%)
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}
