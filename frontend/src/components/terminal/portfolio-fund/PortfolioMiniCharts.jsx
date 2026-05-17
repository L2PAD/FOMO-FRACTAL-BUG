import MiniSparkline from './MiniSparkline';
import { usePortfolioAssetPerformance } from '../../../hooks/portfolio/usePortfolioAssetPerformance';
import { usePortfolioAssets } from '../../../hooks/portfolio/usePortfolioAssets';

// Generate realistic mock sparkline data
function generateMockSparkline(pnl_pct) {
  const points = 20;
  const data = [];
  const baseValue = 100;
  const trend = pnl_pct / 100; // Convert to decimal
  
  for (let i = 0; i < points; i++) {
    const progress = i / (points - 1);
    const trendValue = baseValue + (baseValue * trend * progress);
    const noise = (Math.random() - 0.5) * baseValue * 0.05; // 5% noise
    data.push({ value: trendValue + noise });
  }
  
  return data;
}

export default function PortfolioMiniCharts() {
  const { assets, loading: assetsLoading } = usePortfolioAssets();
  
  // Call hooks for real assets
  const btcPerf = usePortfolioAssetPerformance('BTC');
  const ethPerf = usePortfolioAssetPerformance('ETH');

  // Real assets from backend
  const btcAsset = assets?.find(a => a.asset === 'BTC');
  const ethAsset = assets?.find(a => a.asset === 'ETH');

  // Mock additional assets for demo
  const mockAssets = [
    { symbol: 'SOL', amount: 15.5, price: 145.20, pnl_pct: 28.45, color: '#14F195' },
    { symbol: 'AVAX', amount: 50.0, price: 42.80, pnl_pct: 12.30, color: '#E84142' },
    { symbol: 'MATIC', amount: 500.0, price: 1.15, pnl_pct: -5.20, color: '#8247E5' },
    { symbol: 'LINK', amount: 25.0, price: 18.50, pnl_pct: 15.60, color: '#2A5ADA' },
    { symbol: 'UNI', amount: 30.0, price: 12.40, pnl_pct: 8.90, color: '#FF007A' },
    { symbol: 'AAVE', amount: 5.0, price: 180.00, pnl_pct: 22.10, color: '#B6509E' },
    { symbol: 'DOT', amount: 100.0, price: 8.20, pnl_pct: -3.50, color: '#E6007A' },
    { symbol: 'ATOM', amount: 75.0, price: 11.80, pnl_pct: 18.70, color: '#2E3148' }
  ];

  // Combine real and mock assets
  const allAssets = [
    ...(btcAsset ? [{
      symbol: 'BTC',
      amount: btcAsset.total,
      price: btcAsset.current_price,
      pnl_pct: btcAsset.pnl_pct,
      color: '#F7931A',
      perf: btcPerf
    }] : []),
    ...(ethAsset ? [{
      symbol: 'ETH',
      amount: ethAsset.total,
      price: ethAsset.current_price,
      pnl_pct: ethAsset.pnl_pct,
      color: '#627EEA',
      perf: ethPerf
    }] : []),
    ...mockAssets.map(a => ({ ...a, perf: null }))
  ];

  return (
    <div className="bg-white border border-[#E5E7EB] rounded-lg px-4 py-3 flex flex-col" style={{ height: '400px' }} data-testid="portfolio-mini-charts">
      <h3 className="text-xs font-bold text-gray-400 uppercase tracking-wider mb-3">Asset Performance</h3>
      
      {assetsLoading ? (
        <div className="flex items-center justify-center flex-1">
          <span className="text-sm text-neutral-500">Loading...</span>
        </div>
      ) : (
        <div className="grid grid-cols-5 gap-4 overflow-y-auto flex-1">
          {allAssets.map((asset) => (
            <div key={asset.symbol} className="flex flex-col">
              <div className="mb-2">
                <div className="text-sm font-medium text-gray-900 mb-1">{asset.symbol}</div>
                <div className="text-xs text-gray-500">
                  {asset.amount.toFixed(4)} @ ${asset.price.toLocaleString()}
                </div>
                <div className={`text-base font-semibold mt-1 ${
                  asset.pnl_pct >= 0 ? 'text-green-600' : 'text-red-600'
                }`}>
                  {asset.pnl_pct >= 0 ? '+' : ''}{asset.pnl_pct.toFixed(2)}%
                </div>
              </div>
              <div className="h-12">
                {asset.perf && !asset.perf.loading ? (
                  <MiniSparkline data={asset.perf.data} color={asset.color} />
                ) : (
                  <MiniSparkline 
                    data={generateMockSparkline(asset.pnl_pct)} 
                    color={asset.color} 
                  />
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
