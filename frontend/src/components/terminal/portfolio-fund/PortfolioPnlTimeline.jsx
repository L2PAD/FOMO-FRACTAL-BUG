import { usePortfolioSummary } from '../../../hooks/portfolio/usePortfolioSummary';

export default function PortfolioPnlTimeline() {
  const { summary, loading } = usePortfolioSummary();

  // Mock timeline data (TODO: replace with real endpoint)
  const timeline = [
    { label: '1H', pnl: summary?.total_pnl * 0.02 || 0, pct: 0.42 },
    { label: '6H', pnl: summary?.total_pnl * 0.15 || 0, pct: 1.12 },
    { label: '24H', pnl: summary?.total_pnl * 0.45 || 0, pct: 5.61 },
    { label: '7D', pnl: summary?.total_pnl || 0, pct: summary?.total_return_pct || 0 }
  ];

  return (
    <div className="bg-white border border-[#E5E7EB] rounded-lg px-3 py-2" data-testid="portfolio-pnl-timeline">
      <h3 className="text-xs font-bold text-gray-400 uppercase tracking-wider mb-2">PnL Timeline</h3>
      
      {loading ? (
        <div className="flex items-center justify-center h-16">
          <span className="text-sm text-neutral-500">Loading...</span>
        </div>
      ) : (
        <div className="grid grid-cols-4 gap-4">
          {timeline.map(({ label, pct }) => (
            <div key={label} className="text-center">
              <div className="text-xs text-gray-500 mb-1">{label}</div>
              <div className={`text-lg font-semibold ${
                pct >= 0 ? 'text-green-600' : 'text-red-600'
              }`}>
                {pct >= 0 ? '+' : ''}{pct.toFixed(2)}%
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
