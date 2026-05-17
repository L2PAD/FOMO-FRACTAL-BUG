export default function PortfolioClosedPositions({ positions, loading }) {
  // Mock closed positions if no real data
  const mockClosedPositions = [
    { symbol: 'BTCUSDT', side: 'LONG', entry: 68000, exit: 71000, pnl: 450.50, pnl_pct: 4.41, duration: '3d 5h', exit_reason: 'TAKE PROFIT' },
    { symbol: 'ETHUSDT', side: 'LONG', entry: 3400, exit: 3550, pnl: 220.30, pnl_pct: 4.41, duration: '2d 12h', exit_reason: 'TAKE PROFIT' },
    { symbol: 'SOLUSDT', side: 'SHORT', entry: 150, exit: 145, pnl: 180.00, pnl_pct: 3.33, duration: '1d 8h', exit_reason: 'TAKE PROFIT' },
    { symbol: 'AVAXUSDT', side: 'LONG', entry: 45, exit: 42, pnl: -120.50, pnl_pct: -6.67, duration: '4h', exit_reason: 'STOP LOSS' }
  ];

  const displayPositions = (positions && positions.length > 0) ? positions : mockClosedPositions;

  if (loading) {
    return (
      <div className="bg-white border border-[#E5E7EB] rounded-lg p-4">
        <div className="flex items-center justify-center h-20">
          <span className="text-sm text-neutral-500">Loading...</span>
        </div>
      </div>
    );
  }

  return (
    <div className="bg-white border border-[#E5E7EB] rounded-lg" data-testid="portfolio-closed-positions">
      {/* Header */}
      <div className="px-4 py-3 border-b border-[#E5E7EB]">
        <h3 className="text-sm font-bold text-gray-900">Closed Positions</h3>
      </div>

      {/* Positions List */}
      <div className="p-4 space-y-3">
        {displayPositions.map((pos, index) => (
          <div key={index} className="flex justify-between items-start">
            {/* LEFT: Position Info */}
            <div>
              <div className="text-base font-medium text-gray-900">
                {pos.symbol.replace('USDT', '')} · {pos.side}
              </div>
              <div className="text-sm text-gray-500" style={{ fontVariantNumeric: 'tabular-nums' }}>
                ${pos.entry.toLocaleString()} → ${pos.exit.toLocaleString()}
              </div>
              <div className="text-xs text-gray-400 mt-0.5">
                {pos.duration && <span>{pos.duration}</span>}
                {pos.exit_reason && pos.duration && <span> · </span>}
                {pos.exit_reason && <span>{pos.exit_reason}</span>}
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
