export default function PortfolioCasesPanel({ cases }) {
  // Empty state check
  const activeCases = cases.filter(c => c.status === 'ACTIVE');
  const hasActiveCases = activeCases.length > 0;

  return (
    <div className="rounded-[var(--radius)] bg-[hsl(var(--surface))]" data-testid="portfolio-cases-panel">
      
      {/* NO HEADER — данные → смысл → структура */}

      {/* Cases List */}
      <div className="px-4 py-4">
        {!hasActiveCases ? (
          // NARRATIVE EMPTY STATE
          <div className="py-8 text-center space-y-2" data-testid="portfolio-empty-state">
            <div className="text-base font-medium text-gray-700">Capital not deployed</div>
            <div className="text-sm text-gray-500 leading-relaxed">
              System is waiting for edge,<br />
              not forcing exposure
            </div>
          </div>
        ) : (
          // PROP DESK STYLE — каждый кейс = мини PnL блок
          <div>
            {cases.map((caseData, idx) => (
              <CasePerformanceRow key={caseData.id} caseData={caseData} isLast={idx === cases.length - 1} />
            ))}
          </div>
        )}
      </div>

    </div>
  );
}

function CasePerformanceRow({ caseData, isLast }) {
  const { symbol, direction, status, trading_tf, pnl, pnl_pct, duration, trade_count } = caseData;
  
  const isActive = status === 'ACTIVE';
  const isWin = status === 'CLOSED_WIN';
  const isLoss = status === 'CLOSED_LOSS';
  const isPositive = pnl >= 0;

  // Status badge color
  let statusColor = 'text-gray-500';
  if (isActive) statusColor = 'text-amber-700';
  if (isWin) statusColor = 'text-green-600';
  if (isLoss) statusColor = 'text-red-600';

  return (
    <div 
      className={`py-3.5 ${
        !isLast ? 'border-b border-[rgba(0,0,0,0.04)]' : ''
      } transition-colors duration-100 hover:bg-[rgba(0,0,0,0.02)]`}
      data-testid={`case-row-${symbol}`}
    >
      
      {/* Row 1: Symbol + PnL (якорь) */}
      <div className="flex items-baseline justify-between mb-1.5">
        <span className="font-mono text-sm font-semibold text-gray-900">{symbol}</span>
        
        {/* PnL — PROP DESK STYLE (18px, font-semibold) */}
        <div 
          className={`font-mono text-lg font-semibold tabular-nums ${
            isPositive ? 'text-green-600' : 'text-red-600'
          }`}
        >
          {isPositive ? '+' : ''}{pnl_pct.toFixed(1)}%
        </div>
      </div>

      {/* Row 2: Direction + Status + TF (контекст) */}
      <div className="flex items-center gap-2 mb-1 text-xs">
        <span className={`uppercase font-medium ${statusColor}`}>
          {direction}
        </span>
        <span className="text-gray-400">·</span>
        <span className={`uppercase ${statusColor}`}>
          {status.replace('_', ' ')}
        </span>
        {trading_tf && (
          <>
            <span className="text-gray-400">·</span>
            <span className="font-mono text-gray-500">
              {trading_tf}
            </span>
          </>
        )}
      </div>

      {/* Row 3: Duration + Executions */}
      <div className="text-xs text-gray-500">
        {duration} · {trade_count} {trade_count === 1 ? 'execution' : 'executions'}
      </div>

    </div>
  );
}
