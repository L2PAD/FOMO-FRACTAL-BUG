export default function ChartMiniStatus({ caseData }) {
  if (!caseData || caseData.status !== 'ACTIVE') return null;

  const isLong = caseData.direction === 'LONG';
  const bgColor = isLong ? 'bg-green-900/80' : 'bg-red-900/80';
  const textColor = isLong ? 'text-green-300' : 'text-red-300';
  const pnlColor = caseData.pnl >= 0 ? 'text-green-300' : 'text-red-300';

  return (
    <div 
      className={`absolute top-3 right-3 ${bgColor} backdrop-blur-sm px-3 py-2 rounded-lg border border-white/10 z-20`}
      data-testid="chart-mini-status"
    >
      <div className={`${textColor} font-bold text-xs mb-1`}>
        {caseData.direction} ACTIVE
      </div>
      <div className={`${pnlColor} font-bold text-sm`}>
        {caseData.pnl >= 0 ? '+' : ''}{caseData.pnl_pct.toFixed(1)}%
      </div>
      <div className="text-gray-400 text-xs mt-1">
        EDGE: MODERATE
      </div>
      <div className="text-gray-400 text-xs">
        RISK: CONTROLLED
      </div>
    </div>
  );
}
