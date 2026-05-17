export default function PortfolioRiskStack({ summary }) {
  const { risk, capital_deployed_pct, performance, system } = summary;

  return (
    <div className="rounded-[var(--radius)] bg-[hsl(var(--surface))] h-full flex flex-col" data-testid="portfolio-risk-stack">
      
      {/* Sections Stack — Bloomberg style */}
      <div className="flex-1 flex flex-col">
        
        {/* SECTION: RISK */}
        <div className="px-4 py-3 border-b border-[rgba(0,0,0,0.06)]">
          {/* Section Title — 11px, gray-400, uppercase, tracking-wider */}
          <div className="text-[11px] text-gray-400 uppercase tracking-wider mb-1">Risk</div>
          {/* Section Main — 16px, font-semibold */}
          <div className="font-mono text-base font-semibold text-gray-900 my-1" data-testid="risk-mode">
            {risk.mode}
          </div>
          {/* Параметры — 14px, gray-600 */}
          <div className="text-sm text-gray-600 space-y-0.5">
            <div>Heat {risk.heat}%</div>
            <div className="text-red-600">DD {risk.drawdown}%</div>
          </div>
        </div>

        {/* SECTION: DEPLOYMENT */}
        <div className="px-4 py-3 border-b border-[rgba(0,0,0,0.06)]">
          <div className="text-[11px] text-gray-400 uppercase tracking-wider mb-1">Deployment</div>
          <div className="font-mono text-base font-semibold text-gray-900 my-1">
            {capital_deployed_pct > 0 ? 'Moderate' : 'None'}
          </div>
          <div className="text-sm text-gray-600">
            {capital_deployed_pct}% in use
          </div>
        </div>

        {/* SECTION: PERFORMANCE */}
        <div className="px-4 py-3 border-b border-[rgba(0,0,0,0.06)]">
          <div className="text-[11px] text-gray-400 uppercase tracking-wider mb-1">Performance</div>
          <div className="font-mono text-base font-semibold text-gray-900 my-1" data-testid="performance-winrate">
            {performance.winrate}%
          </div>
          <div className="text-sm text-gray-600 space-y-0.5">
            <div>Avg Win {performance.avg_win}%</div>
            <div>PF {performance.profit_factor.toFixed(1)}</div>
          </div>
        </div>

        {/* SECTION: SYSTEM POSTURE */}
        <div className="px-4 py-3">
          <div className="text-[11px] text-gray-400 uppercase tracking-wider mb-1">System Posture</div>
          <div className="font-mono text-base font-semibold text-gray-900 my-1" data-testid="system-regime">
            {system.regime}
          </div>
          <div className="text-sm text-gray-600 space-y-0.5">
            <div>{system.bias}</div>
            <div className="text-xs text-gray-500">{system.best_strategy}</div>
          </div>
        </div>

      </div>
    </div>
  );
}
