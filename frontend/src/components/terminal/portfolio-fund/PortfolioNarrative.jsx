import { usePortfolioNarrative } from '../../../hooks/portfolio/usePortfolioNarrative';

export default function PortfolioNarrative() {
  const { narrative, loading } = usePortfolioNarrative();

  if (loading || !narrative) {
    return (
      <div className="bg-white border border-[#E5E7EB] rounded-lg px-5 py-4">
        <div className="text-xs font-bold text-gray-400 uppercase tracking-wider mb-2">System Insight</div>
        <div className="text-sm text-gray-500">Loading narrative...</div>
      </div>
    );
  }

  return (
    <div className="bg-white border border-[#E5E7EB] rounded-lg px-3 py-2" data-testid="portfolio-narrative">
      <div className="text-xs font-bold text-gray-400 uppercase tracking-wider mb-2">System Insight</div>
      
      <div className="text-sm text-gray-800 leading-6">
        {narrative.summary}
      </div>

      {narrative.signals && narrative.signals.length > 0 && (
        <div className="mt-3 space-y-1">
          {narrative.signals.map((signal, idx) => (
            <div key={idx} className="text-sm text-gray-600">
              • {signal}
            </div>
          ))}
        </div>
      )}

      {narrative.action && (
        <div className="mt-4 text-sm font-medium text-gray-900">
          → {narrative.action}
        </div>
      )}
    </div>
  );
}
