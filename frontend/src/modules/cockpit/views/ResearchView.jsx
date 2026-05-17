import React, { useEffect, useRef, useState } from 'react';
import styled from 'styled-components';
import { TrendingUp, TrendingDown, Zap, AlertTriangle, RefreshCw, Loader2, Activity, Target, BarChart2, Shield } from 'lucide-react';
import { createChart, CandlestickSeries, HistogramSeries, LineSeries } from 'lightweight-charts';
import { 
  useMarket, 
  useMarketPrice, 
  useMarketRegime, 
  useCapitalFlow, 
  useFractalState, 
  useHypotheses,
  useSignalExplanation 
} from '../../../store/marketStore';
import { ChartObjectRenderer } from '../../../components/chart-engine/ChartObjectRenderer';

// ============================================
// STYLED COMPONENTS
// ============================================

const Container = styled.div`
  display: flex;
  flex-direction: column;
  height: 100%;
  overflow-y: auto;
`;

const MainColumn = styled.div`
  display: flex;
  flex-direction: column;
  gap: 0;
`;

const ChartCard = styled.div`
  background: #ffffff;
  border-radius: 12px;
  border: 1px solid #eef1f5;
  overflow: hidden;
`;

const ChartHeader = styled.div`
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 16px;
  border-bottom: 1px solid #eef1f5;
  background: #fafbfc;
`;

const ChartControls = styled.div`
  display: flex;
  align-items: center;
  gap: 10px;
`;

const Select = styled.select`
  padding: 7px 12px;
  background: #ffffff;
  border: 1px solid #eef1f5;
  border-radius: 8px;
  font-size: 14px;
  font-weight: 600;
  color: #0f172a;
  cursor: pointer;
  &:focus { outline: none; border-color: #05A584; }
`;

// Asset search autocomplete
const AssetSearchWrapper = styled.div`
  position: relative;
  width: 180px;
`;

const AssetInput = styled.input`
  width: 100%;
  padding: 10px 14px;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  font-size: 15px;
  font-weight: 600;
  color: #0f172a;
  letter-spacing: 0.5px;
  &:focus { 
    outline: none; 
    border-color: #05A584; 
    background: #fff;
  }
  &::placeholder { color: #94a3b8; font-weight: 500; }
`;

const AssetDropdown = styled.div`
  position: absolute;
  top: 100%;
  left: 0;
  right: 0;
  margin-top: 4px;
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  box-shadow: 0 4px 12px rgba(0,0,0,0.1);
  z-index: 100;
  max-height: 240px;
  overflow-y: auto;
`;

const AssetOption = styled.div`
  padding: 10px 14px;
  font-size: 14px;
  font-weight: 600;
  color: #0f172a;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 8px;
  &:hover { background: #f8fafc; }
  &:first-child { border-radius: 10px 10px 0 0; }
  &:last-child { border-radius: 0 0 10px 10px; }
  .name { flex: 1; }
  .full { font-size: 12px; color: #64748b; font-weight: 500; }
`;

const TfGroup = styled.div`
  display: flex;
  gap: 2px;
  background: #f5f7fa;
  padding: 2px;
  border-radius: 8px;
`;

const TfButton = styled.button`
  padding: 5px 12px;
  border-radius: 6px;
  font-size: 13px;
  font-weight: 600;
  border: none;
  background: ${({ $active }) => $active ? '#ffffff' : 'transparent'};
  color: ${({ $active }) => $active ? '#0f172a' : '#738094'};
  cursor: pointer;
  box-shadow: ${({ $active }) => $active ? '0 1px 3px rgba(0,0,0,0.08)' : 'none'};
  &:hover { color: #0f172a; }
`;

const RefreshBtn = styled.button`
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 6px 12px;
  border-radius: 8px;
  border: 1px solid #eef1f5;
  background: #ffffff;
  cursor: pointer;
  color: #738094;
  font-size: 12px;
  font-weight: 500;
  &:hover { border-color: #05A584; color: #05A584; }
  svg { ${({ $loading }) => $loading ? 'animation: spin 1s linear infinite;' : ''} }
  @keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
`;

const PriceBlock = styled.div`
  text-align: right;
  .price { font-size: 22px; font-weight: 700; color: #0f172a; font-variant-numeric: tabular-nums; }
  .change { display: flex; align-items: center; justify-content: flex-end; gap: 4px; font-size: 13px; font-weight: 600; color: ${({ $positive }) => $positive ? '#05A584' : '#ef4444'}; }
`;

const ChartContainer = styled.div`
  height: 180px;
  min-height: 160px;
  max-height: 200px;
  width: 100%;
  overflow: hidden;
`;

const LoadingOverlay = styled.div`
  position: absolute;
  inset: 0;
  background: rgba(255,255,255,0.85);
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  svg { animation: spin 1s linear infinite; }
  @keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
`;

const IntelGrid = styled.div`
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 1px;
  background: #eef1f5;
  border-top: 1px solid #eef1f5;
`;

// Layer toggles strip
const LayerStrip = styled.div`
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 14px;
  background: #fafbfc;
  border-top: 1px solid #eef1f5;
  font-size: 11px;
`;

const LayerChip = styled.button`
  padding: 4px 10px;
  border-radius: 12px;
  border: 1px solid ${({ $on }) => $on ? '#05A584' : '#e2e8f0'};
  background: ${({ $on }) => $on ? 'rgba(5,165,132,0.08)' : '#fff'};
  color: ${({ $on }) => $on ? '#05A584' : '#64748b'};
  font-size: 11px;
  font-weight: 600;
  cursor: pointer;
  &:hover { border-color: #05A584; }
`;

// Pattern overlay on chart
const PatternOverlay = styled.div`
  position: absolute;
  top: 12px;
  right: 12px;
  padding: 8px 12px;
  background: rgba(59, 130, 246, 0.95);
  border-radius: 8px;
  font-size: 12px;
  font-weight: 600;
  color: #fff;
  z-index: 5;
  text-transform: capitalize;
  .confidence { opacity: 0.9; font-size: 11px; margin-left: 6px; }
`;

const BiasOverlay = styled.div`
  position: absolute;
  top: 52px;
  right: 12px;
  display: flex;
  align-items: center;
  gap: 5px;
  padding: 6px 10px;
  background: ${({ $type }) => 
    $type === 'bullish' ? 'rgba(5, 165, 132, 0.95)' : 
    $type === 'bearish' ? 'rgba(239, 68, 68, 0.95)' : 
    'rgba(100, 116, 139, 0.95)'};
  color: #fff;
  border-radius: 6px;
  font-weight: 600;
  font-size: 11px;
  z-index: 5;
`;

/* SideColumn no longer used — panels go into IntelGrid */

const Panel = styled.div`
  background: #ffffff;
  padding: 10px 14px;
`;

const PanelHeader = styled.div`
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 6px;
  .title { font-size: 10px; font-weight: 700; color: #94a3b8; text-transform: uppercase; letter-spacing: 0.3px; }
`;

const PanelContent = styled.div`
`;

const Badge = styled.span`
  padding: 3px 8px;
  border-radius: 5px;
  font-size: 10px;
  font-weight: 700;
  text-transform: uppercase;
  background: ${({ $type }) => {
    switch ($type) {
      case 'bullish': return '#e8f9f1';
      case 'bearish': return '#fef2f2';
      case 'strong': return '#dbeafe';
      default: return '#fef3c7';
    }
  }};
  color: ${({ $type }) => {
    switch ($type) {
      case 'bullish': return '#05A584';
      case 'bearish': return '#ef4444';
      case 'strong': return '#3b82f6';
      default: return '#d97706';
    }
  }};
`;

const MetricRow = styled.div`
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 4px 0;
  .label { font-size: 11px; color: #94a3b8; }
  .value { font-size: 12px; font-weight: 600; color: ${({ $color }) => $color || '#0f172a'}; font-variant-numeric: tabular-nums; }
`;

const ProgressBar = styled.div`
  height: 4px;
  background: #eef1f5;
  border-radius: 2px;
  overflow: hidden;
  margin-top: 4px;
  .fill { height: 100%; background: ${({ $color }) => $color || '#05A584'}; width: ${({ $value }) => Math.min($value, 100)}%; border-radius: 2px; }
`;

const ScenarioItem = styled.div`
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 6px 10px;
  background: ${({ $primary }) => $primary ? '#f0fdf4' : '#f8fafc'};
  border-radius: 6px;
  border-left: 3px solid ${({ $color }) => $color || '#05A584'};
  margin-bottom: 4px;
  .type { font-size: 11px; font-weight: 600; color: #0f172a; text-transform: capitalize; }
  .target { font-size: 11px; font-weight: 700; color: ${({ $color }) => $color || '#05A584'}; font-variant-numeric: tabular-nums; }
  .prob { font-size: 10px; color: #94a3b8; margin-left: 8px; }
`;

const DriverItem = styled.div`
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 11px;
  color: #64748b;
  padding: 3px 0;
  border-bottom: 1px solid #f1f5f9;
  &:last-child { border-bottom: none; }
  .dot { width: 6px; height: 6px; border-radius: 50%; background: ${({ $color }) => $color || '#05A584'}; flex-shrink: 0; }
  .name { flex: 1; color: #475569; font-weight: 500; }
`;

const SCENARIO_COLORS = { base: '#05A584', bull: '#3b82f6', bear: '#ef4444', extreme: '#8b5cf6' };

// ============================================
// COMPONENT
// ============================================

const ResearchView = () => {
  const { symbol, timeframe, setSymbol, setTimeframe, loading, error, refresh, researchState } = useMarket();
  const marketPrice = useMarketPrice();
  const regime = useMarketRegime();
  const capitalFlow = useCapitalFlow();
  const fractal = useFractalState();
  const hypotheses = useHypotheses();
  const signal = useSignalExplanation();

  const chartRef = useRef(null);
  const chartInstanceRef = useRef(null);
  const objectRendererRef = useRef(null);
  
  // Chart analysis data with TA objects
  const [chartData, setChartData] = useState(null);
  const [chartLoading, setChartLoading] = useState(false);

  // Layer toggles — patterns and levels enabled by default
  const [layers, setLayers] = useState({ Patterns: true, Levels: true, Hypothesis: true });

  // Asset search state
  const [searchQuery, setSearchQuery] = useState('');
  const [showDropdown, setShowDropdown] = useState(false);
  const searchRef = useRef(null);

  const timeframes = ['4h', '1d', '7d', '30d'];
  
  // Extended crypto list for search
  const allAssets = [
    { symbol: 'BTC', name: 'Bitcoin' },
    { symbol: 'ETH', name: 'Ethereum' },
    { symbol: 'SOL', name: 'Solana' },
    { symbol: 'BNB', name: 'Binance Coin' },
    { symbol: 'XRP', name: 'Ripple' },
    { symbol: 'ADA', name: 'Cardano' },
    { symbol: 'DOGE', name: 'Dogecoin' },
    { symbol: 'AVAX', name: 'Avalanche' },
    { symbol: 'DOT', name: 'Polkadot' },
    { symbol: 'MATIC', name: 'Polygon' },
    { symbol: 'LINK', name: 'Chainlink' },
    { symbol: 'UNI', name: 'Uniswap' },
    { symbol: 'ATOM', name: 'Cosmos' },
    { symbol: 'LTC', name: 'Litecoin' },
    { symbol: 'ETC', name: 'Ethereum Classic' },
    { symbol: 'FIL', name: 'Filecoin' },
    { symbol: 'APT', name: 'Aptos' },
    { symbol: 'ARB', name: 'Arbitrum' },
    { symbol: 'OP', name: 'Optimism' },
    { symbol: 'NEAR', name: 'Near Protocol' },
    { symbol: 'INJ', name: 'Injective' },
    { symbol: 'SUI', name: 'Sui' },
    { symbol: 'AAVE', name: 'Aave' },
    { symbol: 'MKR', name: 'Maker' },
    { symbol: 'CRV', name: 'Curve' },
  ];

  // Filter assets based on search
  const filteredAssets = searchQuery
    ? allAssets.filter(a => 
        a.symbol.toLowerCase().includes(searchQuery.toLowerCase()) ||
        a.name.toLowerCase().includes(searchQuery.toLowerCase())
      ).slice(0, 5)
    : allAssets.slice(0, 5);

  // Get display symbol (without USDT)
  const displaySymbol = symbol.replace('USDT', '');

  // Handle asset selection
  const handleSelectAsset = (asset) => {
    setSymbol(asset.symbol + 'USDT'); // Internal format still uses USDT
    setSearchQuery('');
    setShowDropdown(false);
  };

  // Close dropdown on outside click
  useEffect(() => {
    const handleClickOutside = (e) => {
      if (searchRef.current && !searchRef.current.contains(e.target)) {
        setShowDropdown(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  // Fetch chart analysis with TA objects
  useEffect(() => {
    const fetchChartAnalysis = async () => {
      console.log('[Research] Fetching chart for:', symbol, timeframe);
      setChartLoading(true);
      setChartData(null); // Clear old data immediately
      try {
        const base = process.env.REACT_APP_BACKEND_URL || '';
        const apiSymbol = symbol.replace('USDT', '');
        const apiTf = timeframe.toUpperCase();
        console.log('[Research] API URL:', `${base}/api/v1/chart/full-analysis/${apiSymbol}/${apiTf}`);
        const res = await fetch(`${base}/api/v1/chart/full-analysis/${apiSymbol}/${apiTf}?include_hypothesis=true&limit=500`);
        if (res.ok) {
          const data = await res.json();
          console.log('[Research] Got data:', data.hypothesis?.direction, data.candles?.length);
          setChartData(data);
        }
      } catch (e) {
        console.error('[Research] Chart fetch error:', e);
      } finally {
        setChartLoading(false);
      }
    };
    fetchChartAnalysis();
  }, [symbol, timeframe]);

  // Get TA objects from chartData (not researchState)
  const taObjects = chartData?.objects || [];
  const topPattern = taObjects.find(o => o.category === 'pattern');
  const patternLabel = topPattern?.label || topPattern?.type?.replace(/_/g, ' ') || null;
  const patternConfidence = topPattern?.confidence ? Math.round(topPattern.confidence * 100) : null;

  // Main chart useEffect
  useEffect(() => {
    if (!chartRef.current) return;
    if (chartInstanceRef.current) { chartInstanceRef.current.remove(); chartInstanceRef.current = null; }

    const rect = chartRef.current.getBoundingClientRect();
    const chart = createChart(chartRef.current, {
      width: rect.width,
      height: rect.height,
      layout: { background: { type: 'solid', color: '#ffffff' }, textColor: '#64748b', fontFamily: "'Gilroy', -apple-system, BlinkMacSystemFont, sans-serif", fontSize: 11 },
      grid: { vertLines: { color: '#f8fafc' }, horzLines: { color: '#f8fafc' } },
      crosshair: { mode: 1, vertLine: { color: '#475569', style: 2, width: 1, labelBackgroundColor: '#475569' }, horzLine: { color: '#475569', style: 2, width: 1, labelBackgroundColor: '#475569' } },
      rightPriceScale: { 
        borderColor: '#e2e8f0',
        scaleMargins: { top: 0.02, bottom: 0.02 },
        autoScale: true,
      },
      timeScale: { 
        borderColor: '#e2e8f0', 
        timeVisible: true, 
        secondsVisible: false,
        rightOffset: 15,
        barSpacing: 8,
      },
      handleScroll: { mouseWheel: true, pressedMouseMove: true },
      handleScale: { axisPressedMouseMove: true, mouseWheel: true, pinch: true },
    });
    chartInstanceRef.current = chart;

    const candleSeries = chart.addSeries(CandlestickSeries, {
      upColor: '#05A584', downColor: '#ef4444',
      borderUpColor: '#05A584', borderDownColor: '#ef4444',
      wickUpColor: '#05A584', wickDownColor: '#ef4444',
    });

    const volSeries = chart.addSeries(HistogramSeries, {
      priceFormat: { type: 'volume' },
      priceScaleId: 'vol',
      lastValueVisible: false,
      priceLineVisible: false,
    });
    chart.priceScale('vol').applyOptions({ scaleMargins: { top: 0.88, bottom: 0 }, visible: false });

    // Use chartData instead of researchState
    const candles = chartData?.candles || [];
    if (candles.length > 0) {
      const parseTime = (ts) => typeof ts === 'number' ? ts : typeof ts === 'string' ? Math.floor(new Date(ts).getTime() / 1000) : 0;
      const seen = new Set();
      const mapped = candles.map(c => ({
        time: parseTime(c.timestamp || c.time),
        open: c.open || c.o,
        high: c.high || c.h,
        low: c.low || c.l,
        close: c.close || c.c,
        volume: c.volume || c.v || 0,
      })).filter(c => c.time > 0).sort((a, b) => a.time - b.time).filter(c => { if (seen.has(c.time)) return false; seen.add(c.time); return true; });

      candleSeries.setData(mapped);
      volSeries.setData(mapped.map(c => ({ time: c.time, value: c.volume, color: c.close >= c.open ? 'rgba(5,165,132,0.25)' : 'rgba(239,68,68,0.25)' })));
      
      // Calculate optimal price range - fit to actual data with minimal padding
      const allHighs = mapped.map(c => c.high);
      const allLows = mapped.map(c => c.low);
      const dataHigh = Math.max(...allHighs);
      const dataLow = Math.min(...allLows);
      const range = dataHigh - dataLow;
      const paddingTop = range * 0.02; // 2% padding top - минимум
      const paddingBottom = range * 0.02; // 2% padding bottom - минимум
      
      // Override autoscale to fit data very tightly - убираем пустоты
      candleSeries.applyOptions({
        autoscaleInfoProvider: () => ({
          priceRange: {
            minValue: dataLow - paddingBottom,
            maxValue: dataHigh + paddingTop,
          },
        }),
      });
      
      // Initialize object renderer for TA overlays (recreate for new chart)
      objectRendererRef.current = new ChartObjectRenderer(chart, candleSeries);
      
      // Render TA objects with priority filtering
      const objects = chartData?.objects || [];
      console.log('[Research] Rendering objects:', objects.length, 'patterns:', objects.filter(o => o.category === 'pattern' || o.category === 'geometry').map(o => o.type));
      const pt = (ts) => typeof ts === 'number' ? ts : typeof ts === 'string' ? Math.floor(new Date(ts).getTime() / 1000) : 0;
      objectRendererRef.current.setTimeParser(pt);
      
      // Filter by layers and priority
      const categoryCounts = {};
      const categoryLimits = { pattern: 1, geometry: 2, liquidity: 3, hypothesis: 5 };
      
      objects
        .filter(obj => {
          const cat = obj.category;
          if ((cat === 'pattern' || cat === 'geometry') && !layers.Patterns) return false;
          if (cat === 'liquidity' && !layers.Levels) return false;
          if (cat === 'hypothesis' && !layers.Hypothesis) return false;
          return true;
        })
        .sort((a, b) => (b.priority || 0) - (a.priority || 0))
        .filter(obj => {
          const cat = obj.category || 'unknown';
          categoryCounts[cat] = (categoryCounts[cat] || 0) + 1;
          return categoryCounts[cat] <= (categoryLimits[cat] || 3);
        })
        .forEach(obj => {
          try { objectRendererRef.current.renderObject(obj); } catch (e) {}
        });
      
      chart.timeScale().fitContent();
    }

    const ro = new ResizeObserver(() => {
      if (chartRef.current && chartInstanceRef.current) {
        const w = chartRef.current.clientWidth;
        const h = chartRef.current.clientHeight;
        if (w > 0 && h > 0) chartInstanceRef.current.applyOptions({ width: w, height: h });
      }
    });
    ro.observe(chartRef.current);

    return () => { ro.disconnect(); if (chartInstanceRef.current) { chartInstanceRef.current.remove(); chartInstanceRef.current = null; } };
  }, [chartData, layers]);

  const formatPrice = (v) => v ? new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', minimumFractionDigits: 2 }).format(v) : '$0.00';
  const getBadgeType = (s) => {
    if (!s) return 'neutral';
    const l = s.toLowerCase();
    if (l.includes('up') || l.includes('bullish') || l.includes('risk_on') || l.includes('long')) return 'bullish';
    if (l.includes('down') || l.includes('bearish') || l.includes('risk_off') || l.includes('short')) return 'bearish';
    return 'neutral';
  };

  const top = hypotheses.top;
  const hypothesis = chartData?.hypothesis || researchState?.chart?.hypothesis;

  return (
    <Container data-testid="research-view">
      <MainColumn>
        {error && (
          <div style={{ padding: '10px 14px', background: 'rgba(239,68,68,0.08)', border: '1px solid rgba(239,68,68,0.15)', borderRadius: 8, color: '#ef4444', fontSize: 13 }}>
            <AlertTriangle size={14} style={{ marginRight: 6, verticalAlign: 'middle' }} />{error}
          </div>
        )}

        {/* Chart */}
        <ChartCard style={{ position: 'relative' }}>
          <ChartHeader>
            <ChartControls>
              {/* Asset search autocomplete */}
              <AssetSearchWrapper ref={searchRef}>
                <AssetInput
                  type="text"
                  value={showDropdown ? searchQuery : displaySymbol}
                  onChange={(e) => {
                    setSearchQuery(e.target.value);
                    setShowDropdown(true);
                  }}
                  onFocus={() => setShowDropdown(true)}
                  placeholder="Search asset..."
                  data-testid="research-asset-search"
                />
                {showDropdown && (
                  <AssetDropdown>
                    {filteredAssets.map(asset => (
                      <AssetOption 
                        key={asset.symbol} 
                        onClick={() => handleSelectAsset(asset)}
                        data-testid={`asset-option-${asset.symbol.toLowerCase()}`}
                      >
                        <span className="name">{asset.symbol}</span>
                        <span className="full">{asset.name}</span>
                      </AssetOption>
                    ))}
                    {filteredAssets.length === 0 && (
                      <AssetOption style={{ color: '#94a3b8', cursor: 'default' }}>
                        No assets found
                      </AssetOption>
                    )}
                  </AssetDropdown>
                )}
              </AssetSearchWrapper>
              <TfGroup>
                {timeframes.map(tf => (
                  <TfButton key={tf} $active={timeframe === tf} onClick={() => setTimeframe(tf)} data-testid={`research-tf-${tf}`}>
                    {tf.toUpperCase()}
                  </TfButton>
                ))}
              </TfGroup>
              <RefreshBtn onClick={refresh} disabled={loading} $loading={loading} data-testid="research-refresh-btn">
                <RefreshCw size={14} /> Refresh
              </RefreshBtn>
            </ChartControls>
            <PriceBlock $positive={marketPrice.change >= 0}>
              <div className="price">{formatPrice(marketPrice.price)}</div>
              <div className="change">
                {marketPrice.change >= 0 ? <TrendingUp size={14} /> : <TrendingDown size={14} />}
                {marketPrice.change >= 0 ? '+' : ''}{(marketPrice.change || 0).toFixed(2)}%
              </div>
            </PriceBlock>
          </ChartHeader>
          <ChartContainer ref={chartRef} style={{ height: '180px' }} />
          
          {/* Pattern overlay */}
          {patternLabel && layers.Patterns && (
            <PatternOverlay data-testid="research-pattern-label">
              {patternLabel}
              {patternConfidence && <span className="confidence">{patternConfidence}%</span>}
            </PatternOverlay>
          )}
          
          {/* Bias overlay */}
          {hypothesis && (
            <BiasOverlay $type={getBadgeType(hypothesis.direction)} data-testid="research-bias-label">
              {hypothesis.direction?.toLowerCase().includes('bull') ? '↑' : hypothesis.direction?.toLowerCase().includes('bear') ? '↓' : '→'}
              {hypothesis.direction || 'NEUTRAL'}
              <span style={{ opacity: 0.9, marginLeft: 4 }}>{Math.round((hypothesis.confidence || 0) * 100)}%</span>
            </BiasOverlay>
          )}
          
          {loading && <LoadingOverlay><Loader2 size={24} color="#05A584" /><span style={{ fontSize: 13, color: '#738094' }}>Loading...</span></LoadingOverlay>}
          
          {/* Layer toggles */}
          <LayerStrip>
            <span style={{ color: '#94a3b8', fontWeight: 600 }}>Layers:</span>
            <LayerChip $on={layers.Patterns} onClick={() => setLayers(p => ({ ...p, Patterns: !p.Patterns }))} data-testid="layer-patterns">Patterns</LayerChip>
            <LayerChip $on={layers.Levels} onClick={() => setLayers(p => ({ ...p, Levels: !p.Levels }))} data-testid="layer-levels">S/R Levels</LayerChip>
            <LayerChip $on={layers.Hypothesis} onClick={() => setLayers(p => ({ ...p, Hypothesis: !p.Hypothesis }))} data-testid="layer-hypothesis">Hypothesis</LayerChip>
          </LayerStrip>
        </ChartCard>

        {/* All intelligence panels below chart */}
        <IntelGrid>
          {/* Forecast Summary */}
          <Panel>
            <PanelHeader>
              <span className="title">Forecast Summary</span>
            </PanelHeader>
            <PanelContent>
              {hypothesis?.scenarios?.slice(0, 3).map((s, i) => {
                const type = s.type || ['base', 'bull', 'bear'][i];
                const targetPct = hypothesis.current_price ? ((s.target_price - hypothesis.current_price) / hypothesis.current_price * 100) : 0;
                return (
                  <ScenarioItem key={i} $primary={i === 0} $color={SCENARIO_COLORS[type]} data-testid={`scenario-${type}`}>
                    <span className="type">{type}</span>
                    <span className="target">{targetPct > 0 ? '+' : ''}{targetPct.toFixed(1)}%</span>
                    <span className="prob">{Math.round((s.probability || 0.25) * 100)}%</span>
                  </ScenarioItem>
                );
              }) || <div style={{ fontSize: 11, color: '#94a3b8' }}>No forecast data</div>}
              {hypothesis && (
                <MetricRow style={{ marginTop: 4 }}>
                  <span className="label">Confidence</span>
                  <span className="value" style={{ color: '#05A584' }}>{Math.round((hypothesis.confidence || 0) * 100)}%</span>
                </MetricRow>
              )}
            </PanelContent>
          </Panel>

          {/* Market Regime */}
          <Panel>
            <PanelHeader>
              <span className="title">Market Regime</span>
              <Badge $type={getBadgeType(regime.state)}>{(regime.state || 'N/A').replace(/_/g, ' ')}</Badge>
            </PanelHeader>
            <PanelContent>
              <MetricRow>
                <span className="label">Confidence</span>
                <span className="value">{regime.confidence || 0}%</span>
              </MetricRow>
              <MetricRow>
                <span className="label">Transition Risk</span>
                <span className="value" style={{ color: '#f59e0b' }}>{regime.transitionRisk || 0}%</span>
              </MetricRow>
            </PanelContent>
          </Panel>

          {/* Capital Flow */}
          <Panel>
            <PanelHeader>
              <span className="title">Capital Flow</span>
              <Badge $type={getBadgeType(capitalFlow.bias)}>{capitalFlow.bias || 'NEUTRAL'}</Badge>
            </PanelHeader>
            <PanelContent>
              <MetricRow>
                <span className="label">Rotation</span>
                <span className="value">{(capitalFlow.rotation || 'NEUTRAL').replace(/_/g, ' ')}</span>
              </MetricRow>
              <MetricRow>
                <span className="label">Strength</span>
                <span className="value" style={{ color: '#05A584' }}>{capitalFlow.strength || 0}%</span>
              </MetricRow>
            </PanelContent>
          </Panel>

          {/* Fractal Match */}
          <Panel>
            <PanelHeader>
              <span className="title">Fractal Match</span>
              <Badge $type={getBadgeType(fractal.alignment)}>{fractal.alignment || 'NEUTRAL'}</Badge>
            </PanelHeader>
            <PanelContent>
              <MetricRow>
                <span className="label">Pattern</span>
                <span className="value">{fractal.match || '—'}</span>
              </MetricRow>
              <MetricRow>
                <span className="label">Similarity</span>
                <span className="value" style={{ color: '#05A584' }}>{fractal.similarity || 0}%</span>
              </MetricRow>
            </PanelContent>
          </Panel>

          {/* Key Drivers */}
          <Panel>
            <PanelHeader>
              <span className="title">Key Drivers</span>
            </PanelHeader>
            <PanelContent>
              <div style={{ fontSize: 11, color: '#64748b', lineHeight: 1.4, marginBottom: 4 }}>
                {signal.summary || hypothesis?.explanation || top?.explanation || 'Analyzing...'}
              </div>
              {(signal.drivers || hypothesis?.alpha_contributors || []).slice(0, 3).map((d, i) => (
                <DriverItem key={i} $color="#05A584">
                  <span className="dot" />
                  <span className="name">{d.name || d.indicator || d}</span>
                </DriverItem>
              ))}
            </PanelContent>
          </Panel>

          {/* Top Hypothesis */}
          <Panel>
            <PanelHeader>
              <span className="title">Top Hypothesis</span>
              {top && <Badge $type={getBadgeType(top.direction)}>{top.direction || 'NEUTRAL'}</Badge>}
            </PanelHeader>
            <PanelContent>
              {top ? (
                <>
                  <div style={{ fontSize: 11, fontWeight: 600, color: '#0f172a', marginBottom: 4 }}>
                    {top.name || top.type?.replace(/_/g, ' ') || 'Unknown'}
                  </div>
                  <MetricRow>
                    <span className="label">Confidence</span>
                    <span className="value" style={{ color: '#05A584' }}>{Math.round(top.confidence || 0)}%</span>
                  </MetricRow>
                  <MetricRow>
                    <span className="label">Target</span>
                    <span className="value">{top.targetMovePct ? `${top.targetMovePct}%` : '-'}</span>
                  </MetricRow>
                </>
              ) : (
                <div style={{ fontSize: 11, color: '#94a3b8' }}>Loading...</div>
              )}
            </PanelContent>
          </Panel>
        </IntelGrid>
      </MainColumn>
    </Container>
  );
};

export default ResearchView;
