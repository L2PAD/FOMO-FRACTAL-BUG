import { useEffect, useState } from 'react';

export default function PortfolioModeMini() {
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
        console.error('[PortfolioModeMini] Error:', err);
        setLoading(false);
      }
    };

    fetchIntelligence();
    const interval = setInterval(fetchIntelligence, 3000);
    return () => clearInterval(interval);
  }, []);

  const mode = intelligence?.system_mode || { regime: 'N/A', bias: 'N/A', confidence: 'N/A' };
  const exposure = intelligence?.deployment_pct || 0;

  return (
    <div className="bg-white border border-[#E5E7EB] rounded-lg px-3 py-2" data-testid="portfolio-mode-mini">
      <h3 className="text-xs font-bold text-gray-400 uppercase tracking-wider mb-2">System State</h3>
      
      {loading ? (
        <div className="flex items-center justify-center h-16">
          <span className="text-sm text-neutral-500">Loading...</span>
        </div>
      ) : (
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-xs text-gray-500">Mode</span>
            <span className="text-sm font-semibold text-gray-900">{mode.regime}</span>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-xs text-gray-500">Bias</span>
            <span className="text-sm font-semibold text-gray-900">{mode.bias}</span>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-xs text-gray-500">Conviction</span>
            <span className="text-sm font-medium text-gray-700">{mode.confidence}</span>
          </div>
          <div className="flex items-center justify-between pt-2 border-t border-gray-100">
            <span className="text-xs text-gray-500">Exposure</span>
            <span className="text-sm font-semibold text-gray-900">{exposure.toFixed(2)}%</span>
          </div>
        </div>
      )}
    </div>
  );
}
