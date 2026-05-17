import { usePortfolioIntelligence } from '../../../hooks/portfolio/usePortfolioIntelligence';

export default function SystemIntelligencePanel() {
  const { data, loading } = usePortfolioIntelligence();

  if (loading || !data) {
    return (
      <div className="bg-white border border-[#E5E7EB] rounded-lg p-5">
        <div className="flex items-center justify-center h-20">
          <span className="text-sm text-neutral-500">Loading...</span>
        </div>
      </div>
    );
  }

  return (
    <div className="bg-white border border-[#E5E7EB] rounded-lg p-5 space-y-6 flex-1 flex flex-col" data-testid="system-intelligence">
      {/* HEADER */}
      <div className="text-xs uppercase tracking-wide text-gray-500 font-semibold">
        System Intelligence
      </div>

      {/* EXPOSURE BAR */}
      <div className="space-y-2 flex-1">
        <div className="flex justify-between text-sm">
          <span className="text-gray-600">Exposure</span>
          <span className="font-medium text-gray-900" style={{ fontVariantNumeric: 'tabular-nums' }}>
            {data.deployment_pct}%
          </span>
        </div>

        <div className="h-2 bg-gray-200 rounded-full overflow-hidden">
          <div
            className="h-full bg-green-500 transition-all duration-300"
            style={{ width: `${data.deployment_pct}%` }}
          />
        </div>
      </div>

      {/* PNL CONTRIBUTION */}
      {data.contributions && data.contributions.length > 0 && (
        <div>
          <div className="text-sm mb-2 font-medium text-gray-900">PnL Contribution</div>

          <div className="space-y-1">
            {data.contributions.map((c, index) => (
              <div
                key={index}
                className="flex justify-between text-sm"
              >
                <span className="text-gray-600">{c.symbol}</span>

                <span className={`font-medium ${c.pnl >= 0 ? 'text-green-600' : 'text-red-600'}`} style={{ fontVariantNumeric: 'tabular-nums' }}>
                  {c.pnl >= 0 ? '+' : ''}${c.pnl.toFixed(2)} · {c.contribution_pct}%
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* BEST / WORST */}
      {(data.best || data.worst) && (
        <div className="grid grid-cols-2 gap-4">
          {/* BEST */}
          <div>
            <div className="text-xs text-gray-500 mb-1 uppercase tracking-wide">Best</div>
            {data.best && (
              <div>
                <div className="font-medium text-gray-900">{data.best.symbol}</div>
                <div className="text-sm text-green-600 font-medium" style={{ fontVariantNumeric: 'tabular-nums' }}>
                  +${data.best.pnl.toFixed(2)}
                </div>
              </div>
            )}
          </div>

          {/* WORST */}
          <div>
            <div className="text-xs text-gray-500 mb-1 uppercase tracking-wide">Worst</div>
            {data.worst && (
              <div>
                <div className="font-medium text-gray-900">{data.worst.symbol}</div>
                <div className={`text-sm font-medium ${data.worst.pnl >= 0 ? 'text-green-600' : 'text-red-600'}`} style={{ fontVariantNumeric: 'tabular-nums' }}>
                  {data.worst.pnl >= 0 ? '+' : ''}${data.worst.pnl.toFixed(2)}
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* SYSTEM MODE */}
      {data.system_mode && (
        <div>
          <div className="text-xs text-gray-500 mb-1 uppercase tracking-wide">System Mode</div>

          <div className="font-semibold text-gray-900">
            {data.system_mode.regime}
          </div>

          <div className="text-sm text-gray-500">
            {data.system_mode.bias} · {data.system_mode.confidence}
          </div>
        </div>
      )}
    </div>
  );
}
