/**
 * CHART LAB VIEW — FULL LAYOUT REBUILD
 * 
 * Architecture:
 *   TOOLBAR (one row)
 *   BIG CHART (full width, ~800px height)
 *   ANALYSIS BLOCKS (below chart, 3 sections)
 * 
 * NO right sidebar. Chart is THE page.
 */

import React, { useState, useEffect, useRef, useCallback } from 'react';
import styled from 'styled-components';
import { 
  TrendingUp, TrendingDown, RefreshCw, Loader2, 
  Target, Activity, ChevronDown, ChevronUp
} from 'lucide-react';
import { createChart, CandlestickSeries, LineSeries, HistogramSeries } from 'lightweight-charts';
import ChartObjectRenderer from '../../../components/chart-engine/ChartObjectRenderer';
import { useMarket, useMarketPrice, useMarketRegime, useCapitalFlow, useFractalState, useHypotheses, useSignalExplanation } from '../../../store/marketStore';
// NOTE: RenderPlanOverlay moved to ResearchViewNew per product rules
// Chart Lab = prediction/hypotheses only, NOT TA visualization

// ============================================
// LAYOUT — Single column, no sidebar
// ============================================

const Page = styled.div`
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 0;
  overflow-y: auto;
`;

// ============================================
// TOOLBAR — one compact row
// ============================================

const Toolbar = styled.div`
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 6px 16px;
  background: #fafbfc;
  border-bottom: 1px solid #eef1f5;
  flex-shrink: 0;
  gap: 8px;
  flex-wrap: wrap;
`;

const ToolbarLeft = styled.div`
  display: flex;
  align-items: center;
  gap: 8px;
`;

const ToolbarRight = styled.div`
  display: flex;
  align-items: center;
  gap: 12px;
`;

const Select = styled.select`
  padding: 6px 10px;
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  font-size: 13px;
  font-weight: 600;
  color: #0f172a;
  cursor: pointer;
  &:focus { outline: none; border-color: #05A584; }
`;

const BtnGroup = styled.div`
  display: flex;
  gap: 1px;
  background: #f1f5f9;
  padding: 2px;
  border-radius: 6px;
`;

const Btn = styled.button`
  padding: 5px 12px;
  border-radius: 4px;
  font-size: 12px;
  font-weight: 600;
  border: none;
  cursor: pointer;
  background: ${({ $active }) => $active ? '#fff' : 'transparent'};
  color: ${({ $active }) => $active ? '#0f172a' : '#94a3b8'};
  box-shadow: ${({ $active }) => $active ? '0 1px 2px rgba(0,0,0,0.06)' : 'none'};
  &:hover { color: #0f172a; }
`;

const ModeBtn = styled.button`
  display: flex;
  align-items: center;
  gap: 5px;
  padding: 5px 12px;
  border-radius: 5px;
  font-size: 12px;
  font-weight: 600;
  border: none;
  cursor: pointer;
  background: ${({ $active }) => $active ? '#05A584' : 'transparent'};
  color: ${({ $active }) => $active ? '#fff' : '#94a3b8'};
  &:hover { background: ${({ $active }) => $active ? '#05A584' : '#f1f5f9'}; color: ${({ $active }) => $active ? '#fff' : '#0f172a'}; }
  svg { width: 13px; height: 13px; }
`;

const Divider = styled.div`
  width: 1px;
  height: 18px;
  background: #e2e8f0;
`;

const RefreshButton = styled.button`
  display: flex;
  align-items: center;
  padding: 5px 8px;
  border-radius: 5px;
  border: 1px solid #e2e8f0;
  background: #fff;
  cursor: pointer;
  color: #94a3b8;
  &:hover { border-color: #05A584; color: #05A584; }
  svg { ${({ $spinning }) => $spinning ? 'animation: spin 1s linear infinite;' : ''} }
  @keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
`;

const PriceBlock = styled.div`
  text-align: right;
  .price { font-size: 20px; font-weight: 700; color: #0f172a; font-variant-numeric: tabular-nums; }
  .change { display: flex; align-items: center; justify-content: flex-end; gap: 3px; font-size: 12px; font-weight: 600; color: ${({ $up }) => $up ? '#05A584' : '#ef4444'}; }
`;

const RegimeBadge = styled.span`
  padding: 3px 8px;
  border-radius: 5px;
  font-size: 10px;
  font-weight: 700;
  text-transform: uppercase;
  background: ${({ $type }) => $type === 'bullish' ? '#e8f9f1' : $type === 'bearish' ? '#fef2f2' : '#fef3c7'};
  color: ${({ $type }) => $type === 'bullish' ? '#05A584' : $type === 'bearish' ? '#ef4444' : '#d97706'};
`;

// ============================================
// CHART AREA — optimized height, no nested scroll
// ============================================

const ChartSection = styled.div`
  position: relative;
  width: 100%;
  height: 720px;
  min-height: 600px;
  max-height: 800px;
  flex-shrink: 0;
  background: #fff;
  overflow: hidden; /* NO nested scroll */
`;

const ChartCanvas = styled.div`
  width: 100%;
  height: 100%;
  overflow: hidden; /* NO nested scroll */
`;

const LoadingOverlay = styled.div`
  position: absolute;
  inset: 0;
  background: rgba(255,255,255,0.85);
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  z-index: 10;
  svg { animation: spin 1s linear infinite; }
  @keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
`;

// Chart overlays
const ChartLegend = styled.div`
  position: absolute;
  top: 12px;
  left: 12px;
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  padding: 8px 12px;
  background: rgba(255,255,255,0.95);
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  font-size: 10px;
  z-index: 5;
  backdrop-filter: blur(4px);
`;

const LegendItem = styled.div`
  display: flex;
  align-items: center;
  gap: 5px;
  .dot { 
    width: 12px; height: 3px; border-radius: 2px; 
    background: ${({ $color }) => $color};
    ${({ $dashed }) => $dashed && `
      background: repeating-linear-gradient(90deg, ${$dashed} 0px, ${$dashed} 4px, transparent 4px, transparent 8px);
    `}
  }
  .label { color: #64748b; font-weight: 500; }
`;

const PatternOverlay = styled.div`
  position: absolute;
  top: 12px;
  right: 12px;
  padding: 10px 14px;
  background: rgba(59, 130, 246, 0.95);
  border-radius: 8px;
  font-size: 12px;
  font-weight: 600;
  color: #fff;
  z-index: 5;
  backdrop-filter: blur(4px);
  box-shadow: 0 2px 8px rgba(59, 130, 246, 0.3);
  .name { text-transform: capitalize; }
  .confidence { opacity: 0.9; font-size: 11px; margin-left: 6px; }
`;

const BiasOverlay = styled.div`
  position: absolute;
  top: 60px;
  right: 12px;
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 12px;
  background: ${({ $direction }) => 
    $direction === 'bullish' ? 'rgba(5, 165, 132, 0.95)' : 
    $direction === 'bearish' ? 'rgba(239, 68, 68, 0.95)' : 
    'rgba(100, 116, 139, 0.95)'};
  color: #fff;
  border-radius: 8px;
  font-weight: 600;
  font-size: 12px;
  z-index: 5;
  backdrop-filter: blur(4px);
  .arrow { font-size: 16px; }
  .label { text-transform: uppercase; }
  .conf { font-size: 11px; opacity: 0.9; }
`;

const ResetButton = styled.button`
  position: absolute;
  bottom: 12px;
  right: 12px;
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 6px 10px;
  background: rgba(255,255,255,0.95);
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  font-size: 10px;
  font-weight: 600;
  color: #64748b;
  cursor: pointer;
  z-index: 5;
  &:hover { border-color: #05A584; color: #05A584; }
  svg { width: 12px; height: 12px; }
`;

// ============================================
// LAYER TOGGLES — compact strip below chart
// ============================================

const ToggleStrip = styled.div`
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 5px 16px;
  background: #fafbfc;
  border-top: 1px solid #eef1f5;
  flex-wrap: wrap;
  flex-shrink: 0;
`;

const ToggleLabel = styled.span`
  font-size: 10px;
  font-weight: 700;
  color: #94a3b8;
  text-transform: uppercase;
  letter-spacing: 0.5px;
`;

const Chip = styled.button`
  padding: 3px 8px;
  border-radius: 4px;
  font-size: 10px;
  font-weight: 600;
  border: 1px solid ${({ $on }) => $on ? '#05A584' : '#e2e8f0'};
  background: ${({ $on }) => $on ? '#05A58412' : '#fff'};
  color: ${({ $on }) => $on ? '#05A584' : '#94a3b8'};
  cursor: pointer;
  &:hover { border-color: #05A584; color: #05A584; }
`;

// ============================================
// ANALYSIS GRID — below chart, 3 sections
// ============================================

const AnalysisGrid = styled.div`
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 1px;
  background: #eef1f5;
  border-top: 1px solid #eef1f5;
  flex-shrink: 0;
  
  @media (max-width: 900px) {
    grid-template-columns: 1fr;
  }
`;

const AnalysisSection = styled.div`
  background: #fff;
  padding: 12px 16px;
`;

const SectionTitle = styled.div`
  font-size: 10px;
  font-weight: 700;
  color: #94a3b8;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin-bottom: 8px;
  display: flex;
  align-items: center;
  justify-content: space-between;
`;

const Metric = styled.div`
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 3px 0;
  .k { font-size: 11px; color: #94a3b8; }
  .v { font-size: 11px; font-weight: 600; color: ${({ $c }) => $c || '#0f172a'}; font-variant-numeric: tabular-nums; }
`;

const Badge = styled.span`
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 9px;
  font-weight: 700;
  text-transform: uppercase;
  background: ${({ $t }) => $t === 'bullish' ? '#e8f9f1' : $t === 'bearish' ? '#fef2f2' : '#fef3c7'};
  color: ${({ $t }) => $t === 'bullish' ? '#05A584' : $t === 'bearish' ? '#ef4444' : '#d97706'};
`;

const ScenarioRow = styled.div`
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 3px 0;
  .dot { width: 8px; height: 3px; border-radius: 2px; background: ${({ $c }) => $c}; flex-shrink: 0; }
  .type { font-size: 10px; font-weight: 600; color: #475569; text-transform: capitalize; width: 36px; }
  .pct { font-size: 11px; font-weight: 700; color: ${({ $c }) => $c}; font-variant-numeric: tabular-nums; }
  .prob { font-size: 10px; color: #94a3b8; margin-left: auto; }
`;

// ============================================
// CONSTANTS
// ============================================

const SYMBOLS = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT'];
// Product timeframes per specification: 4H, 1D, 7D, 30D, 180D, 1Y
const TIMEFRAMES = ['4h', '1d', '7d', '30d', '180d', '1y'];
const TF_MAP = { '4h': '4H', '1d': '1D', '7d': '7D', '30d': '30D', '180d': '180D', '1y': '1Y' };
const HORIZONS = ['7D', '14D', '30D', '90D', '180D'];
const LAYERS = ['Patterns', 'S/R Levels', 'Liquidity', 'Hypothesis', 'Fractals', 'Forecast'];
const SCENARIO_COLORS = { base: '#05A584', bull: '#3b82f6', bear: '#ef4444', extreme: '#8b5cf6' };

// Indicator groups - main chart overlays vs separate pane oscillators
const MAIN_INDICATORS = ['EMA', 'SMA', 'Bollinger', 'Ichimoku', 'PSAR', 'Donchian', 'Keltner', 'Supertrend'];
const OSCILLATOR_INDICATORS = ['RSI', 'MACD', 'CCI', 'Williams%R', 'Stochastic', 'Momentum', 'OBV', 'ATR'];

// Indicator colors
const INDICATOR_COLORS = {
  ema_series: '#F59E0B',
  sma_series: '#3B82F6',
  bollinger_band: '#8B5CF6',
  donchian_channel: '#06B6D4',
  keltner_channel: '#10B981',
  ichimoku_cloud: '#0EA5E9',
  psar_series: '#EF4444',
  supertrend: '#22C55E',
  rsi_series: '#F59E0B',
  macd_series: '#3B82F6',
  cci_series: '#8B5CF6',
  williams_r_series: '#06B6D4',
  atr_band: '#EF4444',
};

const generateDefaultScenarios = (price) => [
  { type: 'base', target_price: price * 1.03, probability: 0.5 },
  { type: 'bull', target_price: price * 1.07, probability: 0.25 },
  { type: 'bear', target_price: price * 0.97, probability: 0.25 },
];

// ============================================
// COMPONENT
// ============================================

const ChartLabView = () => {
  const { symbol, timeframe, setSymbol, setTimeframe, loading } = useMarket();
  const marketPrice = useMarketPrice();
  const regime = useMarketRegime();
  const capitalFlow = useCapitalFlow();
  const fractal = useFractalState();
  const hypotheses = useHypotheses();
  const signal = useSignalExplanation();
  // NOTE: renderPlan/TA visualization moved to ResearchViewNew
  // Chart Lab is ONLY for prediction/hypotheses per product rules

  const [chartMode, setChartMode] = useState('forecast');
  const [forecastHorizon, setForecastHorizon] = useState('30D');
  const [analysisData, setAnalysisData] = useState(null);
  const [chartLoading, setChartLoading] = useState(false);
  const [deviationState, setDeviationState] = useState({ deviation: '0', forecastPrice: 0, actualPrice: 0, status: 'on_track' });

  // Layer toggles — Patterns and S/R on by default for better visualization
  const [layers, setLayers] = useState({ Patterns: true, 'S/R Levels': true, Liquidity: false, Hypothesis: true, Fractals: false, Forecast: true });
  const toggleLayer = (l) => setLayers(prev => ({ ...prev, [l]: !prev[l] }));

  // Indicator toggles
  const [activeIndicators, setActiveIndicators] = useState(['Bollinger']);
  const toggleIndicator = (ind) => setActiveIndicators(prev => 
    prev.includes(ind) ? prev.filter(i => i !== ind) : [...prev, ind]
  );

  // Chart refs
  const chartContainerRef = useRef(null);
  const chartRef = useRef(null);
  const candleSeriesRef = useRef(null);
  const volumeSeriesRef = useRef(null);
  const forecastSeriesRefs = useRef({});
  const indicatorSeriesRefs = useRef({});
  const objectRendererRef = useRef(null);

  // ============================================
  // FETCH DATA
  // ============================================

  const fetchAnalysis = useCallback(async () => {
    const apiSymbol = symbol.replace('USDT', '');
    const apiTf = TF_MAP[timeframe] || '1D';
    const base = process.env.REACT_APP_BACKEND_URL || '';
    setChartLoading(true);
    try {
      const res = await fetch(`${base}/api/v1/chart/full-analysis/${apiSymbol}/${apiTf}?include_hypothesis=true&include_fractals=true&limit=500`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      setAnalysisData(await res.json());
    } catch (err) {
      console.error('[ChartLab] Fetch error:', err);
    } finally {
      setChartLoading(false);
    }
  }, [symbol, timeframe]);

  useEffect(() => { fetchAnalysis(); }, [fetchAnalysis]);

  // ============================================
  // TIMEFRAME RESET — clear all overlays on TF change
  // ============================================
  
  useEffect(() => {
    // Clear candle series data
    if (candleSeriesRef.current) {
      try { candleSeriesRef.current.setData([]); } catch (e) {}
    }
    if (volumeSeriesRef.current) {
      try { volumeSeriesRef.current.setData([]); } catch (e) {}
    }
    // Clear all chart overlays when timeframe changes
    if (chartRef.current && objectRendererRef.current) {
      objectRendererRef.current.clearAll();
    }
    // Clear forecast series
    Object.values(forecastSeriesRefs.current).forEach(s => { 
      try { chartRef.current?.removeSeries(s); } catch (e) {} 
    });
    forecastSeriesRefs.current = {};
    // Clear indicator series
    Object.values(indicatorSeriesRefs.current).forEach(s => { 
      try { chartRef.current?.removeSeries(s); } catch (e) {} 
    });
    indicatorSeriesRefs.current = {};
    // Reset analysis data
    setAnalysisData(null);
  }, [symbol, timeframe]);

  // ============================================
  // CREATE CHART
  // ============================================

  useEffect(() => {
    if (!chartContainerRef.current) return;
    if (chartRef.current) { chartRef.current.remove(); chartRef.current = null; candleSeriesRef.current = null; volumeSeriesRef.current = null; forecastSeriesRefs.current = {}; objectRendererRef.current = null; }

    const rect = chartContainerRef.current.getBoundingClientRect();
    const chart = createChart(chartContainerRef.current, {
      width: rect.width,
      height: rect.height,
      layout: { background: { type: 'solid', color: '#ffffff' }, textColor: '#64748b', fontFamily: "'Gilroy', -apple-system, BlinkMacSystemFont, sans-serif", fontSize: 11 },
      grid: { vertLines: { color: '#f8fafc' }, horzLines: { color: '#f8fafc' } },
      crosshair: { mode: 1, vertLine: { color: '#475569', style: 2, width: 1, labelBackgroundColor: '#475569' }, horzLine: { color: '#475569', style: 2, width: 1, labelBackgroundColor: '#475569' } },
      rightPriceScale: { 
        borderColor: '#e2e8f0', 
        textColor: '#64748b',
        scaleMargins: { top: 0.08, bottom: 0.08 }, // 8% padding for auto-fit
        autoScale: true,
      },
      timeScale: { 
        borderColor: '#e2e8f0', 
        timeVisible: true, 
        secondsVisible: false, 
        rightOffset: 20, 
        barSpacing: 10,
        minBarSpacing: 4,
      },
      handleScroll: {
        mouseWheel: true,
        pressedMouseMove: true,
        horzTouchDrag: true,
        vertTouchDrag: false, // NO vertical touch scroll
      },
      handleScale: {
        axisPressedMouseMove: true,
        mouseWheel: true,
        pinch: true,
      },
    });
    chartRef.current = chart;

    candleSeriesRef.current = chart.addSeries(CandlestickSeries, {
      upColor: '#05A584', downColor: '#ef4444', borderUpColor: '#05A584', borderDownColor: '#ef4444', wickUpColor: '#05A584', wickDownColor: '#ef4444',
    });

    volumeSeriesRef.current = chart.addSeries(HistogramSeries, {
      priceFormat: { type: 'volume' }, priceScaleId: 'vol', lastValueVisible: false, priceLineVisible: false,
    });
    chart.priceScale('vol').applyOptions({ scaleMargins: { top: 0.88, bottom: 0 }, visible: false });

    objectRendererRef.current = new ChartObjectRenderer(chart);

    const ro = new ResizeObserver(() => {
      window.requestAnimationFrame(() => {
        if (chartContainerRef.current && chartRef.current) {
          const w = chartContainerRef.current.clientWidth;
          const h = chartContainerRef.current.clientHeight;
          if (w > 0 && h > 0) chartRef.current.applyOptions({ width: w, height: h });
        }
      });
    });
    ro.observe(chartContainerRef.current);

    return () => { ro.disconnect(); if (chartRef.current) { chartRef.current.remove(); chartRef.current = null; } };
  }, []);

  // ============================================
  // SET DATA ON CHART
  // ============================================

  useEffect(() => {
    if (!analysisData || !chartRef.current || !candleSeriesRef.current) return;

    const pt = (ts) => typeof ts === 'number' ? ts : typeof ts === 'string' ? Math.floor(new Date(ts).getTime() / 1000) : 0;

    // Candles
    const seen = new Set();
    const candles = (analysisData.candles || []).map(c => ({
      time: pt(c.timestamp || c.time), open: c.open, high: c.high, low: c.low, close: c.close, volume: c.volume || 0,
    })).filter(c => c.time > 0).sort((a, b) => a.time - b.time).filter(c => { if (seen.has(c.time)) return false; seen.add(c.time); return true; });

    if (candles.length > 0) {
      candleSeriesRef.current.setData(candles);
      volumeSeriesRef.current.setData(candles.map(c => ({ time: c.time, value: c.volume, color: c.close >= c.open ? 'rgba(5,165,132,0.2)' : 'rgba(239,68,68,0.2)' })));
    }

    // TA Objects with PRIORITY SYSTEM
    if (objectRendererRef.current) {
      objectRendererRef.current.clearAll();
      
      // Filter and prioritize objects
      const allObjects = analysisData.objects || [];
      
      // 1. Filter by layer toggles
      let filteredObjects = allObjects.filter(obj => {
        const cat = obj.category, type = obj.type;
        if ((cat === 'geometry' || cat === 'pattern') && !layers.Patterns) return false;
        if (cat === 'liquidity' && (type === 'resistance_cluster' || type === 'support_cluster') && !layers['S/R Levels']) return false;
        if (cat === 'liquidity' && type === 'liquidity_zone' && !layers.Liquidity) return false;
        if (cat === 'hypothesis' && !layers.Hypothesis) return false;
        if (cat === 'fractal' && !layers.Fractals) return false;
        return true;
      });
      
      // 2. Sort by priority (highest first)
      filteredObjects.sort((a, b) => (b.priority || 0) - (a.priority || 0));
      
      // 3. Apply LIMITS per category to avoid visual noise
      const categoryLimits = {
        pattern: 1,          // Only 1 strongest pattern
        liquidity: 3,        // Max 3 levels (support + resistance)
        hypothesis: 5,       // Entry, SL, TP1, TP2, TP3
        fractal: 2,          // Reference + projection
        geometry: 2,
      };
      
      const categoryCounts = {};
      const limitedObjects = filteredObjects.filter(obj => {
        const cat = obj.category || 'unknown';
        categoryCounts[cat] = (categoryCounts[cat] || 0) + 1;
        const limit = categoryLimits[cat] || 3;
        return categoryCounts[cat] <= limit;
      });
      
      // 4. Render limited objects
      limitedObjects.forEach(obj => { 
        try { 
          objectRendererRef.current.renderObject(obj); 
        } catch (e) {
          console.warn('Failed to render object:', obj.id, e);
        } 
      });
    }

    // Clear old indicator series
    Object.values(indicatorSeriesRefs.current).forEach(s => { try { chartRef.current.removeSeries(s); } catch (e) {} });
    indicatorSeriesRefs.current = {};

    // Render active indicators from backend data
    if (analysisData.indicators && analysisData.indicators.length > 0) {
      renderIndicators(analysisData.indicators, pt);
    }

    // Clear old forecast series
    Object.values(forecastSeriesRefs.current).forEach(s => { try { chartRef.current.removeSeries(s); } catch (e) {} });
    forecastSeriesRefs.current = {};

    if (chartMode === 'forecast' && layers.Forecast) {
      renderForecast(candles, analysisData.hypothesis, pt);
    }
    if (chartMode === 'deviation') {
      renderDeviation(candles, analysisData.hypothesis, pt);
    }

    setTimeout(() => { if (chartRef.current) chartRef.current.timeScale().fitContent(); }, 100);
  }, [analysisData, layers, chartMode, forecastHorizon, activeIndicators]);

  // ============================================
  // RENDER FORECAST
  // ============================================

  const renderForecast = (candles, hypothesis, pt) => {
    if (!chartRef.current || !candles.length) return;

    const lastCandle = candles[candles.length - 1];
    const currentPrice = lastCandle.close;
    const lastTime = lastCandle.time;
    const horizonDays = parseInt(forecastHorizon.replace('D', ''), 10);
    const daySeconds = 86400;
    const endTime = lastTime + horizonDays * daySeconds;

    // NOW vertical line — use a price line on the candle series at current price
    // The visual "NOW" boundary is where forecast lines begin (from lastTime)

    const scenarios = hypothesis?.scenarios || generateDefaultScenarios(currentPrice);

    scenarios.forEach((scenario, idx) => {
      const type = scenario.type || ['base', 'bull', 'bear', 'extreme'][idx] || 'base';
      const color = SCENARIO_COLORS[type] || '#05A584';
      const isPrimary = idx === 0 || type === 'base';

      // Build forecast data — use expected_path or generate from horizon
      let data = [];
      if (scenario.expected_path && scenario.expected_path.length > 0) {
        data = scenario.expected_path
          .map(p => ({ time: pt(p.timestamp), value: p.price }))
          .filter(p => p.time > 0 && p.time <= endTime)
          .sort((a, b) => a.time - b.time);
        // Deduplicate
        const s = new Set();
        data = data.filter(p => { if (s.has(p.time)) return false; s.add(p.time); return true; });
      }
      
      // If no path or path too short, generate synthetic for the selected horizon
      if (data.length < 2) {
        const targetPrice = scenario.target_price || currentPrice;
        data = [{ time: lastTime, value: currentPrice }];
        for (let d = 1; d <= horizonDays; d++) {
          const progress = d / horizonDays;
          data.push({ time: lastTime + d * daySeconds, value: currentPrice + (targetPrice - currentPrice) * progress });
        }
      }

      // Ensure path starts from lastTime
      if (data.length > 0 && data[0].time > lastTime) {
        data.unshift({ time: lastTime, value: currentPrice });
      }

      const series = chartRef.current.addSeries(LineSeries, {
        color, lineWidth: isPrimary ? 3 : 2, lineStyle: isPrimary ? 0 : 2,
        priceLineVisible: false, lastValueVisible: isPrimary, crosshairMarkerVisible: isPrimary,
      });
      series.setData(data);
      forecastSeriesRefs.current[type] = series;

      // Confidence bands for primary
      if (isPrimary) {
        const upper = scenario.upper_band && scenario.expected_path
          ? scenario.expected_path.map((p, i) => ({ time: pt(p.timestamp), value: scenario.upper_band[i] })).filter(p => p.time > 0 && p.time <= endTime)
          : data.map(p => ({ time: p.time, value: p.value * 1.02 }));
        const lower = scenario.lower_band && scenario.expected_path
          ? scenario.expected_path.map((p, i) => ({ time: pt(p.timestamp), value: scenario.lower_band[i] })).filter(p => p.time > 0 && p.time <= endTime)
          : data.map(p => ({ time: p.time, value: p.value * 0.98 }));

        const dedup = (arr) => { const s = new Set(); return arr.filter(p => { if (s.has(p.time)) return false; s.add(p.time); return true; }); };
        
        const uSeries = chartRef.current.addSeries(LineSeries, { color: `${color}30`, lineWidth: 1, lineStyle: 1, priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false });
        uSeries.setData(dedup(upper));
        forecastSeriesRefs.current[`${type}_u`] = uSeries;

        const lSeries = chartRef.current.addSeries(LineSeries, { color: `${color}30`, lineWidth: 1, lineStyle: 1, priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false });
        lSeries.setData(dedup(lower));
        forecastSeriesRefs.current[`${type}_l`] = lSeries;
      }
    });

    // TP lines
    if (hypothesis?.take_profit) {
      hypothesis.take_profit.forEach((tp, i) => {
        const price = typeof tp === 'number' ? tp : tp?.price;
        if (!price) return;
        const s = chartRef.current.addSeries(LineSeries, { color: '#05A584', lineWidth: 1, lineStyle: 2, priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false, title: `TP${i+1}` });
        s.setData([{ time: lastTime, value: price }, { time: endTime, value: price }]);
        forecastSeriesRefs.current[`tp${i}`] = s;
      });
    }

    // SL line
    if (hypothesis?.stop_loss && typeof hypothesis.stop_loss === 'number') {
      const s = chartRef.current.addSeries(LineSeries, { color: '#ef4444', lineWidth: 1, lineStyle: 2, priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false, title: 'SL' });
      s.setData([{ time: lastTime, value: hypothesis.stop_loss }, { time: endTime, value: hypothesis.stop_loss }]);
      forecastSeriesRefs.current['sl'] = s;
    }
  };

  // ============================================
  // RENDER DEVIATION
  // ============================================

  const renderDeviation = (candles, hypothesis, pt) => {
    if (!chartRef.current || !candles.length) return;

    const base = hypothesis?.scenarios?.[0];
    if (!base) return;

    const lastCandle = candles[candles.length - 1];

    // Forecast path
    if (base.expected_path && base.expected_path.length > 0) {
      const data = base.expected_path.map(p => ({ time: pt(p.timestamp), value: p.price })).filter(p => p.time > 0).sort((a, b) => a.time - b.time);
      const s = new Set();
      const unique = data.filter(p => { if (s.has(p.time)) return false; s.add(p.time); return true; });

      const fSeries = chartRef.current.addSeries(LineSeries, { color: '#3b82f6', lineWidth: 2, lineStyle: 2, priceLineVisible: false, lastValueVisible: true, crosshairMarkerVisible: false, title: 'Forecast' });
      fSeries.setData(unique);
      forecastSeriesRefs.current['forecast_path'] = fSeries;

      // Confidence corridor
      if (base.upper_band && base.lower_band && base.expected_path.length === base.upper_band.length) {
        const timestamps = base.expected_path.map(p => pt(p.timestamp));
        const dedup = (arr) => { const s = new Set(); return arr.filter(p => { if (s.has(p.time)) return false; s.add(p.time); return true; }); };
        const uS = chartRef.current.addSeries(LineSeries, { color: '#3b82f630', lineWidth: 1, lineStyle: 1, priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false });
        uS.setData(dedup(timestamps.map((t, i) => ({ time: t, value: base.upper_band[i] }))));
        forecastSeriesRefs.current['dev_u'] = uS;
        const lS = chartRef.current.addSeries(LineSeries, { color: '#3b82f630', lineWidth: 1, lineStyle: 1, priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false });
        lS.setData(dedup(timestamps.map((t, i) => ({ time: t, value: base.lower_band[i] }))));
        forecastSeriesRefs.current['dev_l'] = lS;
      }
    }

    // Deviation state
    const forecastMap = new Map();
    if (base.expected_path) base.expected_path.forEach(p => { const t = pt(p.timestamp); if (t > 0) forecastMap.set(t, p.price); });
    const fp = forecastMap.get(lastCandle.time) || base.target_price || lastCandle.close;
    const dev = ((lastCandle.close - fp) / fp) * 100;
    setDeviationState({ deviation: dev.toFixed(2), forecastPrice: fp, actualPrice: lastCandle.close, status: Math.abs(dev) < 1 ? 'on_track' : Math.abs(dev) < 3 ? 'drifting' : 'invalidated' });
  };

  // ============================================
  // RENDER INDICATORS (Overlays on main chart)
  // ============================================

  const renderIndicators = (indicators, pt) => {
    if (!chartRef.current) return;

    indicators.forEach(ind => {
      const type = ind.type || '';
      const indicatorName = type.split('_')[0].toUpperCase();
      
      // Check if this indicator is active
      const isActive = activeIndicators.some(active => 
        type.toLowerCase().includes(active.toLowerCase())
      );
      
      if (!isActive) return;

      const color = INDICATOR_COLORS[type] || '#F59E0B';

      // Handle band-type indicators (Bollinger, Donchian, Keltner, ATR)
      if (ind.upper_band && ind.lower_band && ind.timestamps) {
        const timestamps = ind.timestamps.map(t => pt(t)).filter(t => t > 0);
        
        // Upper band
        if (ind.upper_band.length === timestamps.length) {
          const upperData = timestamps.map((t, i) => ({ time: t, value: ind.upper_band[i] }))
            .filter(d => d.value != null)
            .sort((a, b) => a.time - b.time);
          
          // Deduplicate
          const seenU = new Set();
          const uniqueUpper = upperData.filter(d => { if (seenU.has(d.time)) return false; seenU.add(d.time); return true; });
          
          if (uniqueUpper.length > 1) {
            const uSeries = chartRef.current.addSeries(LineSeries, {
              color: color + '99', lineWidth: 1, lineStyle: 2,
              priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false,
            });
            uSeries.setData(uniqueUpper);
            indicatorSeriesRefs.current[`${ind.id}_upper`] = uSeries;
          }
        }

        // Middle band (SMA)
        if (ind.middle_band && ind.middle_band.length === timestamps.length) {
          const middleData = timestamps.map((t, i) => ({ time: t, value: ind.middle_band[i] }))
            .filter(d => d.value != null)
            .sort((a, b) => a.time - b.time);
          
          const seenM = new Set();
          const uniqueMiddle = middleData.filter(d => { if (seenM.has(d.time)) return false; seenM.add(d.time); return true; });
          
          if (uniqueMiddle.length > 1) {
            const mSeries = chartRef.current.addSeries(LineSeries, {
              color: color, lineWidth: 2, lineStyle: 0,
              priceLineVisible: false, lastValueVisible: true, crosshairMarkerVisible: false,
            });
            mSeries.setData(uniqueMiddle);
            indicatorSeriesRefs.current[`${ind.id}_middle`] = mSeries;
          }
        }

        // Lower band
        if (ind.lower_band.length === timestamps.length) {
          const lowerData = timestamps.map((t, i) => ({ time: t, value: ind.lower_band[i] }))
            .filter(d => d.value != null)
            .sort((a, b) => a.time - b.time);
          
          const seenL = new Set();
          const uniqueLower = lowerData.filter(d => { if (seenL.has(d.time)) return false; seenL.add(d.time); return true; });
          
          if (uniqueLower.length > 1) {
            const lSeries = chartRef.current.addSeries(LineSeries, {
              color: color + '99', lineWidth: 1, lineStyle: 2,
              priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false,
            });
            lSeries.setData(uniqueLower);
            indicatorSeriesRefs.current[`${ind.id}_lower`] = lSeries;
          }
        }
      }

      // Handle line-type indicators (EMA, SMA)
      else if (ind.series && ind.timestamps) {
        const timestamps = ind.timestamps.map(t => pt(t)).filter(t => t > 0);
        
        if (ind.series.length === timestamps.length) {
          const lineData = timestamps.map((t, i) => ({ time: t, value: ind.series[i] }))
            .filter(d => d.value != null)
            .sort((a, b) => a.time - b.time);
          
          const seen = new Set();
          const unique = lineData.filter(d => { if (seen.has(d.time)) return false; seen.add(d.time); return true; });
          
          if (unique.length > 1) {
            const series = chartRef.current.addSeries(LineSeries, {
              color: color, lineWidth: 2, lineStyle: 0,
              priceLineVisible: false, lastValueVisible: true, crosshairMarkerVisible: false,
            });
            series.setData(unique);
            indicatorSeriesRefs.current[ind.id] = series;
          }
        }
      }
    });
  };

  // ============================================
  // HELPERS
  // ============================================

  const fmt = (v) => v ? new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', minimumFractionDigits: 2 }).format(v) : '$0.00';
  const regType = (s) => { if (!s) return 'neutral'; const l = s.toLowerCase(); if (l.includes('up') || l.includes('bull') || l.includes('risk_on')) return 'bullish'; if (l.includes('down') || l.includes('bear') || l.includes('risk_off')) return 'bearish'; return 'neutral'; };

  // Reset chart view to fit content
  const resetChartView = () => {
    if (chartRef.current) {
      chartRef.current.timeScale().fitContent();
    }
  };

  const hypothesis = analysisData?.hypothesis;
  
  // Get top pattern for display
  const topPattern = (analysisData?.objects || []).find(o => o.category === 'pattern');
  const patternLabel = topPattern?.label || topPattern?.type?.replace(/_/g, ' ') || null;
  const patternConfidence = topPattern?.confidence ? Math.round(topPattern.confidence * 100) : null;

  // ============================================
  // RENDER
  // ============================================

  return (
    <Page data-testid="chart-lab-view">
      {/* ─── TOOLBAR ─── */}
      <Toolbar data-testid="chart-toolbar">
        <ToolbarLeft>
          <Select value={symbol} onChange={e => setSymbol(e.target.value)} data-testid="symbol-select">
            {SYMBOLS.map(s => <option key={s}>{s}</option>)}
          </Select>

          <BtnGroup>
            {TIMEFRAMES.map(tf => (
              <Btn key={tf} $active={timeframe === tf} onClick={() => setTimeframe(tf)} data-testid={`tf-btn-${tf}`}>{tf.toUpperCase()}</Btn>
            ))}
          </BtnGroup>

          <Divider />

          <ModeBtn $active={chartMode === 'forecast'} onClick={() => setChartMode('forecast')} data-testid="mode-forecast">
            <Target /> Forecast
          </ModeBtn>
          <ModeBtn $active={chartMode === 'deviation'} onClick={() => setChartMode('deviation')} data-testid="mode-deviation">
            <Activity /> Deviation
          </ModeBtn>

          {chartMode === 'forecast' && (
            <>
              <Divider />
              <BtnGroup>
                {HORIZONS.map(h => (
                  <Btn key={h} $active={forecastHorizon === h} onClick={() => setForecastHorizon(h)} data-testid={`horizon-${h}`}>{h}</Btn>
                ))}
              </BtnGroup>
            </>
          )}

          <RefreshButton onClick={fetchAnalysis} disabled={loading || chartLoading} $spinning={chartLoading} data-testid="refresh-btn">
            <RefreshCw size={14} />
          </RefreshButton>
        </ToolbarLeft>

        <ToolbarRight>
          <RegimeBadge $type={regType(regime.state)} data-testid="regime-badge">{regime.state?.replace(/_/g, ' ') || 'LOADING'}</RegimeBadge>
          <PriceBlock $up={marketPrice.change >= 0}>
            <div className="price" data-testid="current-price">{fmt(marketPrice.price)}</div>
            <div className="change">
              {marketPrice.change >= 0 ? <TrendingUp size={12} /> : <TrendingDown size={12} />}
              {marketPrice.change >= 0 ? '+' : ''}{(marketPrice.change || 0).toFixed(2)}%
            </div>
          </PriceBlock>
        </ToolbarRight>
      </Toolbar>

      {/* ─── BIG CHART (FULL WIDTH) ─── */}
      <ChartSection data-testid="chart-section">
        <ChartCanvas ref={chartContainerRef} data-testid="chart-canvas" />
        
        {/* Legend */}
        <ChartLegend data-testid="chart-legend">
          <LegendItem $color="#05A584"><div className="dot" /><span className="label">Support</span></LegendItem>
          <LegendItem $color="#ef4444"><div className="dot" /><span className="label">Resistance</span></LegendItem>
          <LegendItem $color="#3b82f6"><div className="dot" /><span className="label">Pattern</span></LegendItem>
          <LegendItem $dashed="#22c55e"><div className="dot" /><span className="label">Entry</span></LegendItem>
          <LegendItem $color="#ef4444"><div className="dot" /><span className="label">Stop</span></LegendItem>
          <LegendItem $dashed="#3b82f6"><div className="dot" /><span className="label">Target</span></LegendItem>
        </ChartLegend>
        
        {/* Pattern Label */}
        {patternLabel && layers.Patterns && (
          <PatternOverlay data-testid="pattern-overlay">
            <span className="name">{patternLabel}</span>
            {patternConfidence && <span className="confidence">{patternConfidence}%</span>}
          </PatternOverlay>
        )}
        
        {/* Bias Indicator */}
        {hypothesis && (
          <BiasOverlay $direction={regType(hypothesis.direction)} data-testid="bias-overlay">
            <span className="arrow">{hypothesis.direction?.toLowerCase().includes('bull') ? '↑' : hypothesis.direction?.toLowerCase().includes('bear') ? '↓' : '→'}</span>
            <span className="label">{hypothesis.direction || 'NEUTRAL'}</span>
            <span className="conf">{Math.round((hypothesis.confidence || 0) * 100)}%</span>
          </BiasOverlay>
        )}
        
        {/* Reset View Button */}
        <ResetButton onClick={resetChartView} data-testid="reset-view-btn">
          <RefreshCw /> Reset View
        </ResetButton>
        
        {/* NOTE: RenderPlanOverlay REMOVED from Chart Lab */}
        {/* TA visualization is now in Research page only */}
        {/* Chart Lab = prediction/hypotheses only */}
        
        {(loading || chartLoading) && (
          <LoadingOverlay><Loader2 size={28} color="#05A584" /><span style={{ fontSize: 12, color: '#94a3b8' }}>Loading...</span></LoadingOverlay>
        )}
      </ChartSection>

      {/* ─── LAYER TOGGLES — Prediction layers only ─── */}
      <ToggleStrip data-testid="layer-strip">
        <ToggleLabel>Layers</ToggleLabel>
        {LAYERS.map(l => (
          <Chip key={l} $on={layers[l]} onClick={() => toggleLayer(l)} data-testid={`layer-${l.toLowerCase().replace(/\s|\//g, '-')}`}>{l}</Chip>
        ))}
        <Divider style={{ margin: '0 8px' }} />
        <ToggleLabel>Indicators</ToggleLabel>
        {MAIN_INDICATORS.slice(0, 5).map(ind => (
          <Chip key={ind} $on={activeIndicators.includes(ind)} onClick={() => toggleIndicator(ind)} data-testid={`ind-${ind.toLowerCase()}`}>{ind}</Chip>
        ))}
      </ToggleStrip>

      {/* ─── ANALYSIS BELOW CHART ─── */}
      <AnalysisGrid data-testid="analysis-grid">
        {/* Section 1: Market State */}
        <AnalysisSection>
          <SectionTitle>
            Market State
            <Badge $t={regType(regime.state)}>{regime.state?.replace(/_/g, ' ') || 'N/A'}</Badge>
          </SectionTitle>
          <Metric><span className="k">Confidence</span><span className="v">{regime.confidence || 0}%</span></Metric>
          <Metric><span className="k">Capital Flow</span><span className="v" style={{ color: capitalFlow.bias === 'INFLOW' ? '#05A584' : '#ef4444' }}>{capitalFlow.bias || 'NEUTRAL'}</span></Metric>
          <Metric><span className="k">Flow Strength</span><span className="v">{capitalFlow.strength || 0}%</span></Metric>
          <Metric><span className="k">Fractal</span><span className="v">{fractal.match || '—'}</span></Metric>
          <Metric><span className="k">Similarity</span><span className="v" style={{ color: '#05A584' }}>{fractal.similarity || 0}%</span></Metric>
          {chartMode === 'deviation' && (
            <>
              <div style={{ height: 1, background: '#f1f5f9', margin: '6px 0' }} />
              <Metric $c={Math.abs(parseFloat(deviationState.deviation)) < 1 ? '#05A584' : '#ef4444'}>
                <span className="k">Deviation</span><span className="v">{deviationState.deviation}%</span>
              </Metric>
              <Metric><span className="k">Status</span>
                <Badge $t={deviationState.status === 'on_track' ? 'bullish' : deviationState.status === 'drifting' ? 'neutral' : 'bearish'}>
                  {deviationState.status?.replace(/_/g, ' ')}
                </Badge>
              </Metric>
            </>
          )}
        </AnalysisSection>

        {/* Section 2: Hypothesis & Signal */}
        <AnalysisSection>
          <SectionTitle>
            Hypothesis
            {hypothesis && <Badge $t={regType(hypothesis.direction)}>{hypothesis.direction || 'NEUTRAL'}</Badge>}
          </SectionTitle>
          {hypothesis ? (
            <>
              <Metric><span className="k">Confidence</span><span className="v" style={{ color: '#05A584' }}>{Math.round((hypothesis.confidence || 0) * 100)}%</span></Metric>
              {hypothesis.scenarios?.slice(0, 3).map((s, i) => {
                const type = s.type || ['base', 'bull', 'bear'][i];
                const pct = s.target_pct ?? ((s.target_price - hypothesis.current_price) / hypothesis.current_price);
                return (
                  <ScenarioRow key={i} $c={SCENARIO_COLORS[type]}>
                    <span className="dot" />
                    <span className="type">{type}</span>
                    <span className="pct">{pct > 0 ? '+' : ''}{(pct * 100).toFixed(1)}%</span>
                    <span className="prob">{Math.round((s.probability || 0.25) * 100)}%</span>
                  </ScenarioRow>
                );
              })}
              <div style={{ height: 1, background: '#f1f5f9', margin: '6px 0' }} />
              <div style={{ fontSize: 11, color: '#64748b', lineHeight: 1.4 }}>
                {signal.summary || hypothesis.explanation || 'Analyzing...'}
              </div>
            </>
          ) : (
            <div style={{ fontSize: 11, color: '#94a3b8' }}>Loading hypothesis...</div>
          )}
        </AnalysisSection>

        {/* Section 3: Trading Levels */}
        <AnalysisSection>
          <SectionTitle>Trading Levels</SectionTitle>
          {hypothesis?.entry_price && <Metric><span className="k">Entry</span><span className="v">{fmt(hypothesis.entry_price)}</span></Metric>}
          {hypothesis?.stop_loss && <Metric $c="#ef4444"><span className="k">Stop Loss</span><span className="v" style={{ color: '#ef4444' }}>{fmt(hypothesis.stop_loss)}</span></Metric>}
          {hypothesis?.take_profit?.map((tp, i) => (
            <Metric key={i}><span className="k">TP{i + 1}</span><span className="v" style={{ color: '#05A584' }}>{fmt(typeof tp === 'number' ? tp : tp?.price)}</span></Metric>
          ))}
          {hypothesis?.alpha_contributors && hypothesis.alpha_contributors.length > 0 && (
            <>
              <div style={{ height: 1, background: '#f1f5f9', margin: '6px 0' }} />
              <div style={{ fontSize: 10, fontWeight: 700, color: '#94a3b8', marginBottom: 4 }}>KEY DRIVERS</div>
              {hypothesis.alpha_contributors.slice(0, 4).map((c, i) => (
                <Metric key={i}><span className="k">{c.name}</span><span className="v" style={{ color: c.signal === 'bullish' ? '#05A584' : c.signal === 'bearish' ? '#ef4444' : '#94a3b8' }}>{c.signal}</span></Metric>
              ))}
            </>
          )}
        </AnalysisSection>
      </AnalysisGrid>
    </Page>
  );
};

export default ChartLabView;
