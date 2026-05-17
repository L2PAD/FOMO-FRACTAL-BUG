export default function PortfolioInsights() {
  const insights = [
    'BTC contributes 42% of total gains',
    'Stablecoin share rising → defensive posture',
    'ETH underperforming vs portfolio average',
    '2 active positions drive current live PnL'
  ];

  const savedViews = [
    'Moonshot Tracker',
    'Bear Market',
    'Core Holdings',
    'GameFi Watch'
  ];

  return (
    <div className="bg-white border border-[#E5E7EB] rounded-lg p-3" data-testid="insights">
      <div className="mb-3">
        <h3 className="text-sm font-semibold text-gray-900">Portfolio Insights</h3>
      </div>

      {/* Insights */}
      <div className="space-y-2 mb-4">
        {insights.map((insight, i) => (
          <div key={i} className="flex items-start gap-1.5 text-xs">
            <div className="w-1 h-1 rounded-full bg-blue-500 mt-1.5 flex-shrink-0" />
            <p className="text-gray-700">{insight}</p>
          </div>
        ))}
      </div>

      {/* Saved Views */}
      <div>
        <div className="text-xs font-semibold text-gray-500 uppercase mb-2">Saved Views</div>
        <div className="space-y-1.5">
          {savedViews.map((view, i) => (
            <button
              key={i}
              className="w-full text-left px-2 py-1.5 text-xs rounded border border-[#E5E7EB] hover:bg-gray-50 transition-colors text-gray-700"
            >
              {view}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
