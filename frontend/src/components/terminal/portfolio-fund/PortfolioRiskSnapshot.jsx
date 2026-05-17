import { usePortfolioSummary } from '../../../hooks/portfolio/usePortfolioSummary';

export default function PortfolioRiskSnapshot() {
  const { summary, loading } = usePortfolioSummary();

  const metrics = [
    { label: 'Cash', value: summary?.cash_balance || 0, format: 'currency' },
    { label: 'Invested', value: summary?.positions_value || 0, format: 'currency' },
    { label: 'ATH', value: summary?.ath || 0, format: 'currency' },
    { label: 'DD', value: summary?.drawdown_pct || 0, format: 'percent', negative: true }
  ];

  return (
    <div className="bg-white border border-[#E5E7EB] rounded-lg px-3 py-2" data-testid="portfolio-risk-snapshot">
      <h3 className="text-xs font-bold text-gray-400 uppercase tracking-wider mb-2">Risk Snapshot</h3>
      
      {loading ? (
        <div className="flex items-center justify-center h-20">
          <span className="text-sm text-neutral-500">Loading...</span>
        </div>
      ) : (
        <div className="space-y-2">
          {metrics.map(({ label, value, format, negative }) => (
            <div key={label} className="flex items-center justify-between">
              <span className="text-xs text-gray-500">{label}</span>
              <span className={`text-sm font-semibold ${
                format === 'percent' && value < 0 ? 'text-red-600' : 'text-gray-900'
              }`}>
                {format === 'currency' 
                  ? `$${value.toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 })}` 
                  : `${value.toFixed(2)}%`
                }
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
