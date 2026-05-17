// Generate narrative system state description
function generateSystemNarrative(summary) {
  const { system, capital_deployed_pct, risk } = summary;
  
  const deployment = capital_deployed_pct > 50 ? 'actively deploying' : 
                     capital_deployed_pct > 20 ? 'selectively deploying' : 
                     'preserving';
  
  const regime = system.regime.toLowerCase();
  const conditions = regime === 'chop' ? 'choppy conditions' :
                     regime === 'trend' ? 'trending conditions' :
                     regime === 'wait' ? 'unclear conditions' :
                     'current conditions';
  
  return `System is ${deployment} capital in ${conditions}`;
}

export default function PortfolioHero({ summary }) {
  const { equity, total_pnl, total_return_pct, capital_deployed_pct, active_cases, watching_cases } = summary;

  const isPositive = total_pnl >= 0;
  const narrative = generateSystemNarrative(summary);

  return (
    <div className="flex flex-col gap-2" data-testid="portfolio-hero">
      
      {/* LEVEL 1 — CAPITAL (44px, font-bold, tracking-tight, slate-900) */}
      <div className="font-mono text-[44px] font-bold tracking-tight tabular-nums text-slate-900" data-testid="portfolio-equity">
        ${equity.toLocaleString()}
      </div>

      {/* LEVEL 2 — MONEY FLOW (20px, font-semibold, green-600) */}
      <div 
        className={`font-mono text-xl font-semibold tabular-nums ${
          isPositive ? 'text-green-600' : 'text-red-600'
        }`}
        data-testid="portfolio-pnl"
      >
        {isPositive ? '+' : ''}${total_pnl} ({isPositive ? '+' : ''}{total_return_pct.toFixed(1)}%)
      </div>

      {/* NARRATIVE — "голос системы" (13px, gray-700, спокойный) */}
      <div className="text-[13px] text-gray-700 mt-1.5 mb-2.5" data-testid="portfolio-narrative">
        {narrative}
      </div>

      {/* Secondary info — одна строка через · (13px, gray-600) */}
      <div className="text-[13px] text-gray-600">
        Capital deployed {capital_deployed_pct}% · {active_cases} active · {watching_cases} watching
      </div>

    </div>
  );
}
