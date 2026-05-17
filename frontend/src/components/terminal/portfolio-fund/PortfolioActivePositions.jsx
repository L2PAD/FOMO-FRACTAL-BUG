export default function PortfolioActivePositions({ positions, loading }) {
  if (loading) {
    return (
      <div className="bg-white border border-[#E5E7EB] rounded-lg p-4">
        <div className="flex items-center justify-center h-20">
          <span className="text-sm text-neutral-500">Loading...</span>
        </div>
      </div>
    );
  }

  if (!positions || positions.length === 0) {
    return (
      <div className="bg-white border border-[#E5E7EB] rounded-lg p-6 text-center">
        <div className="text-sm font-semibold text-gray-700 mb-2">No Active Positions</div>
        <div className="text-xs text-gray-500">No positions currently open</div>
      </div>
    );
  }

  return (
    <div className="bg-white border border-[#E5E7EB] rounded-lg" data-testid="portfolio-active-positions">
      {/* Header */}
      <div className="px-4 py-3 border-b border-[#E5E7EB]">
        <h3 className="text-sm font-bold text-gray-900">Active Positions</h3>
      </div>

      {/* Positions List */}
      <div className="p-4 space-y-3">
        {positions.map((pos, index) => (
          <div key={index} className="flex justify-between items-start">
            {/* LEFT: Position Info */}
            <div>
              <div className="text-base font-medium text-gray-900">
                {pos.symbol.replace('USDT', '')} · {pos.side}
              </div>
              <div className="text-sm text-gray-500" style={{ fontVariantNumeric: 'tabular-nums' }}>
                ${pos.entry_price.toLocaleString()} → ${pos.mark_price.toLocaleString()}
              </div>
              <div className="text-xs text-gray-400 mt-0.5">
                {pos.duration && <span>{pos.duration}</span>}
                {pos.strategy && pos.duration && <span> · </span>}
                {pos.strategy && <span>{pos.strategy}</span>}
              </div>
            </div>

            {/* RIGHT: PnL */}
            <div className="text-right">
              <div className={`text-base font-semibold ${pos.pnl >= 0 ? 'text-green-600' : 'text-red-600'}`} style={{ fontVariantNumeric: 'tabular-nums' }}>
                {pos.pnl >= 0 ? '+' : ''}${pos.pnl.toFixed(2)}
              </div>
              <div className="text-sm text-gray-500" style={{ fontVariantNumeric: 'tabular-nums' }}>
                {pos.pnl_pct >= 0 ? '+' : ''}{pos.pnl_pct.toFixed(2)}%
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
