import { useEffect, useState } from 'react';

export default function PortfolioContributionMini({ onFocusAsset }) {
  const [intelligence, setIntelligence] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchIntelligence = async () => {
      try {
        const response = await fetch(`${process.env.REACT_APP_BACKEND_URL}/api/portfolio/intelligence`);
        const data = await response.json();
        setIntelligence(data);
        setLoading(false);
      } catch (err) {
        console.error('[PortfolioContributionMini] Error:', err);
        setLoading(false);
      }
    };

    fetchIntelligence();
    const interval = setInterval(fetchIntelligence, 3000);
    return () => clearInterval(interval);
  }, []);

  // Real contributions from backend
  const realContributions = intelligence?.contributions || [];

  // Mock additional contributions for demo
  const mockContributions = [
    { symbol: 'SOL', contribution_pct: 8.5, pnl: 450.20 },
    { symbol: 'AVAX', contribution_pct: 5.2, pnl: 280.50 },
    { symbol: 'MATIC', contribution_pct: -2.1, pnl: -120.30 },
    { symbol: 'LINK', contribution_pct: 6.8, pnl: 350.00 },
    { symbol: 'UNI', contribution_pct: 3.9, pnl: 190.40 },
    { symbol: 'AAVE', contribution_pct: 7.2, pnl: 420.80 },
    { symbol: 'DOT', contribution_pct: -1.5, pnl: -80.20 },
    { symbol: 'ATOM', contribution_pct: 4.6, pnl: 240.10 }
  ];

  // Combine real and mock
  const allContributions = [...realContributions, ...mockContributions];

  return (
    <div className="bg-white border border-[#E5E7EB] rounded-lg px-3 py-2 flex flex-col" style={{ height: '400px' }} data-testid="portfolio-contribution-mini">
      <h3 className="text-xs font-bold text-gray-400 uppercase tracking-wider mb-2">Contribution</h3>
      
      {loading ? (
        <div className="flex items-center justify-center flex-1">
          <span className="text-sm text-neutral-500">Loading...</span>
        </div>
      ) : allContributions.length === 0 ? (
        <div className="text-sm text-gray-500 text-center py-4">No active positions</div>
      ) : (
        <div className="space-y-2 overflow-y-auto flex-1">
          {allContributions.map(({ symbol, contribution_pct, pnl }) => (
            <button
              key={symbol}
              onClick={() => onFocusAsset?.(symbol)}
              className="w-full text-left hover:bg-gray-50 rounded px-2 py-1 -mx-2 transition-colors"
            >
              <div className="flex items-center justify-between mb-1">
                <span className="text-sm font-medium text-gray-700">{symbol}</span>
                <span className={`text-sm font-semibold ${
                  pnl >= 0 ? 'text-green-600' : 'text-red-600'
                }`}>
                  {Math.abs(contribution_pct).toFixed(2)}%
                </span>
              </div>
              <div className="w-full bg-gray-100 rounded-full h-1.5">
                <div 
                  className={`h-1.5 rounded-full ${
                    contribution_pct >= 0 ? 'bg-green-600' : 'bg-red-600'
                  }`}
                  style={{ width: `${Math.abs(contribution_pct)}%` }}
                />
              </div>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
