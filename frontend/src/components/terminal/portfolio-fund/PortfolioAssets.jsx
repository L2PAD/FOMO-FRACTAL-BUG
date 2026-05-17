export default function PortfolioAssets({ assets, loading }) {
  if (loading) {
    return (
      <div className="bg-white border border-[#E5E7EB] rounded-lg p-4">
        <div className="flex items-center justify-center h-20">
          <span className="text-sm text-neutral-500">Loading assets...</span>
        </div>
      </div>
    );
  }

  if (!assets || assets.length === 0) {
    return (
      <div className="bg-white border border-[#E5E7EB] rounded-lg p-6 text-center">
        <div className="text-sm font-semibold text-gray-700 mb-2">No Assets</div>
        <div className="text-xs text-gray-500">Portfolio is empty</div>
      </div>
    );
  }

  return (
    <div className="bg-white border border-[#E5E7EB] rounded-lg" data-testid="portfolio-assets">
      {/* Header */}
      <div className="px-4 py-3 border-b border-[#E5E7EB]">
        <h3 className="text-sm font-bold text-gray-900">Assets</h3>
      </div>

      {/* Assets List */}
      <div className="p-4 space-y-3">
        {assets.map((asset, index) => (
          <div key={index} className="flex justify-between items-start">
            {/* LEFT: Asset Info */}
            <div>
              <div className="text-base font-medium text-gray-900">
                {asset.asset}
              </div>
              <div className="text-sm text-gray-500" style={{ fontVariantNumeric: 'tabular-nums' }}>
                {asset.total.toFixed(asset.asset === 'USDT' || asset.asset === 'USDC' ? 2 : 4)}
                {asset.avg_entry && (
                  <span> · avg ${asset.avg_entry.toLocaleString()}</span>
                )}
              </div>
            </div>

            {/* RIGHT: Value & PnL */}
            <div className="text-right">
              <div className="text-base font-semibold text-gray-900" style={{ fontVariantNumeric: 'tabular-nums' }}>
                ${asset.value.toLocaleString()}
              </div>
              {asset.pnl !== 0 && (
                <div className={`text-sm font-medium ${asset.pnl >= 0 ? 'text-green-600' : 'text-red-600'}`} style={{ fontVariantNumeric: 'tabular-nums' }}>
                  {asset.pnl >= 0 ? '+' : ''}{asset.pnl_pct.toFixed(2)}%
                </div>
              )}
              {asset.pnl === 0 && (
                <div className="text-sm text-gray-400">
                  {asset.allocation_pct.toFixed(1)}%
                </div>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
