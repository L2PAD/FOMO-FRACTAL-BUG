import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts';
import { useMemo } from 'react';
import { usePortfolioMultiEquity } from '../../../hooks/portfolio/usePortfolioMultiEquity';

const RANGES = [
  { label: '24H', days: 1 },
  { label: '7D', days: 7 },
  { label: '30D', days: 30 },
  { label: 'ALL', days: null }
];

export default function PortfolioChart({ selectedRange, onRangeChange, focusAsset }) {
  const { data: multiEquity, loading } = usePortfolioMultiEquity();

  // Filter and format data
  const chartData = useMemo(() => {
    if (!multiEquity || multiEquity.length === 0) return [];

    const now = Math.floor(Date.now() / 1000);
    const range = RANGES.find(r => r.label === selectedRange);
    const cutoffTime = range && range.days ? now - (range.days * 86400) : 0;

    return multiEquity
      .filter(point => point.timestamp >= cutoffTime)
      .map(point => ({
        time: point.timestamp * 1000,
        total: point.total,
        btc: point.btc,
        eth: point.eth
      }))
      .sort((a, b) => a.time - b.time);
  }, [multiEquity, selectedRange]);

  const showInsufficientData = !loading && chartData.length > 0 && chartData.length < 2;

  return (
    <div className="bg-white border border-[#E5E7EB] rounded-lg" data-testid="portfolio-chart">
      {/* Header */}
      <div className="flex items-center justify-between px-3 py-2 border-b border-[#E5E7EB]">
        <div className="flex items-center gap-4">
          <h3 className="text-sm font-bold text-gray-900">Multi-Asset Equity Growth</h3>
          
          {/* Legend (moved to header) */}
          {!loading && chartData.length >= 2 && (
            <div className="flex items-center gap-3 text-xs">
              <div className="flex items-center gap-1.5">
                <div className="w-3 h-0.5 bg-[#111827]" />
                <span className="text-gray-600">Total Equity</span>
              </div>
              <div className="flex items-center gap-1.5">
                <div className="w-3 h-0.5 bg-[#F7931A]" />
                <span className="text-gray-600">BTC</span>
              </div>
              <div className="flex items-center gap-1.5">
                <div className="w-3 h-0.5 bg-[#627EEA]" />
                <span className="text-gray-600">ETH</span>
              </div>
            </div>
          )}
        </div>
        
        {/* Range Selector */}
        <div className="flex items-center gap-1">
          {RANGES.map(range => (
            <button
              key={range.label}
              onClick={() => onRangeChange(range.label)}
              className={`px-2.5 py-1 text-xs font-medium rounded-lg transition-colors ${
                selectedRange === range.label
                  ? 'bg-gray-900 text-white'
                  : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
              }`}
              data-testid={`range-${range.label}`}
            >
              {range.label}
            </button>
          ))}
        </div>
      </div>

      {/* Chart Container */}
      <div className="px-3 py-2">
        {loading && (
          <div className="flex items-center justify-center h-[320px]">
            <span className="text-sm text-neutral-500">Loading equity curve...</span>
          </div>
        )}

        {showInsufficientData && (
          <div className="flex flex-col items-center justify-center h-[320px] text-center">
            <div className="text-sm font-semibold text-gray-700 mb-2">Track Record Building</div>
            <div className="text-xs text-gray-500 max-w-xs">
              Equity history is still forming from live portfolio snapshots. The curve will become more detailed as the system accumulates data.
            </div>
            <div className="text-xs text-gray-400 mt-2">
              {chartData.length} snapshot{chartData.length !== 1 ? 's' : ''} collected
            </div>
          </div>
        )}

        {!loading && !showInsufficientData && chartData.length >= 2 && (
          <ResponsiveContainer width="100%" height={320}>
            <LineChart data={chartData} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
              <XAxis 
                dataKey="time" 
                stroke="#d1d5db"
                tick={{ fill: '#9ca3af', fontSize: 10 }}
                tickLine={false}
                axisLine={{ stroke: '#e5e7eb' }}
                tickFormatter={(time) => {
                  const date = new Date(time);
                  return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
                }}
                minTickGap={50}
              />
              <YAxis 
                stroke="#d1d5db"
                tick={{ fill: '#9ca3af', fontSize: 10 }}
                tickLine={false}
                axisLine={{ stroke: '#e5e7eb' }}
                tickFormatter={(value) => `$${(value / 1000).toFixed(0)}k`}
              />
              <Tooltip 
                contentStyle={{ 
                  backgroundColor: '#ffffff', 
                  border: '1px solid #e5e7eb',
                  borderRadius: '6px',
                  fontSize: '11px',
                  padding: '8px'
                }}
                formatter={(value, name) => {
                  const label = name === 'total' ? 'Total Equity' : name === 'btc' ? 'BTC' : 'ETH';
                  return [`$${value.toLocaleString()}`, label];
                }}
                labelFormatter={(time) => new Date(time).toLocaleString()}
              />
              
              {/* Total Equity Line (dominant) */}
              <Line 
                type="monotone" 
                dataKey="total" 
                stroke="#111827" 
                strokeWidth={3}
                dot={false}
                name="total"
              />
              
              {/* BTC Line */}
              <Line 
                type="monotone" 
                dataKey="btc" 
                stroke="#F7931A" 
                strokeWidth={focusAsset === 'BTC' || !focusAsset ? 2 : 1}
                strokeOpacity={focusAsset && focusAsset !== 'BTC' ? 0.3 : 1}
                dot={false}
                name="btc"
              />
              
              {/* ETH Line */}
              <Line 
                type="monotone" 
                dataKey="eth" 
                stroke="#627EEA" 
                strokeWidth={focusAsset === 'ETH' || !focusAsset ? 2 : 1}
                strokeOpacity={focusAsset && focusAsset !== 'ETH' ? 0.3 : 1}
                dot={false}
                name="eth"
              />
            </LineChart>
          </ResponsiveContainer>
        )}

        {!loading && chartData.length === 0 && (
          <div className="flex flex-col items-center justify-center h-[400px] text-center">
            <div className="text-sm font-semibold text-gray-700 mb-2">No Data</div>
            <div className="text-xs text-gray-500">No equity snapshots available</div>
          </div>
        )}
      </div>
    </div>
  );
}
