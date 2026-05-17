const ASSET_COLORS = {
  'CASH': '#6b7280',
  'BTC': '#f59e0b',
  'ETH': '#3b82f6',
  'SOL': '#10b981',
  'BNB': '#f0b90b',
  'ADA': '#0033ad',
  'XRP': '#23292f'
};

export default function PortfolioSidebar({ allocations, summary, loading }) {
  // Loading state
  if (loading || !allocations || !summary) {
    return (
      <div className="bg-white border border-[#E5E7EB] rounded-lg p-4">
        <div className="flex items-center justify-center h-32">
          <span className="text-sm text-neutral-500">Loading...</span>
        </div>
      </div>
    );
  }

  const total = summary.total_equity;

  // Donut calculation
  const radius = 110;
  let currentAngle = -90;

  const segments = allocations.map(item => {
    const angle = (item.pct / 100) * 360;
    const segment = {
      ...item,
      color: ASSET_COLORS[item.asset] || '#9ca3af',
      startAngle: currentAngle,
      endAngle: currentAngle + angle
    };
    currentAngle += angle;
    return segment;
  });

  return (
    <div className="bg-white border border-[#E5E7EB] rounded-lg flex flex-col" style={{ height: '378px' }} data-testid="allocation-sidebar">
      {/* Header */}
      <div className="px-4 py-3 border-b border-[#E5E7EB]">
        <h3 className="text-sm font-bold text-gray-900">Allocation</h3>
      </div>

      <div className="p-4 flex-1 flex flex-col justify-center">
        {/* SVG Donut */}
        <div className="relative w-[200px] h-[200px] mx-auto mb-4">
          <svg width="200" height="200" viewBox="0 0 240 240" className="transform -rotate-90">
            {segments.map((seg, i) => {
              const x1 = 120 + radius * Math.cos((seg.startAngle * Math.PI) / 180);
              const y1 = 120 + radius * Math.sin((seg.startAngle * Math.PI) / 180);
              const x2 = 120 + radius * Math.cos((seg.endAngle * Math.PI) / 180);
              const y2 = 120 + radius * Math.sin((seg.endAngle * Math.PI) / 180);
              const largeArc = seg.endAngle - seg.startAngle > 180 ? 1 : 0;

              return (
                <path
                  key={i}
                  d={`M 120 120 L ${x1} ${y1} A ${radius} ${radius} 0 ${largeArc} 1 ${x2} ${y2} Z`}
                  fill={seg.color}
                  opacity="0.9"
                />
              );
            })}
            {/* Center circle */}
            <circle cx="120" cy="120" r="70" fill="white" />
          </svg>
          
          {/* Center text */}
          <div className="absolute inset-0 flex flex-col items-center justify-center">
            <div className="text-xl font-bold text-gray-900" style={{ fontVariantNumeric: 'tabular-nums' }}>
              ${total.toLocaleString()}
            </div>
            <div className="text-xs text-gray-500">Total Equity</div>
          </div>
        </div>

        {/* Legend */}
        <div className="space-y-2">
          {allocations.map((item, i) => (
            <div key={i} className="flex items-center justify-between text-xs">
              <div className="flex items-center gap-2">
                <div className="w-2 h-2 rounded-full" style={{ backgroundColor: ASSET_COLORS[item.asset] || '#9ca3af' }} />
                <span className="text-gray-700 font-medium">{item.asset}</span>
              </div>
              <div className="flex items-center gap-3" style={{ fontVariantNumeric: 'tabular-nums' }}>
                <span className="text-gray-500">{item.pct.toFixed(2)}%</span>
                <span className="text-gray-900 font-medium">${item.value.toLocaleString()}</span>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
