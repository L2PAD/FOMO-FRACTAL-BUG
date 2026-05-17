/**
 * Price vs Expectation V2 Page
 * 
 * New forecast-based prediction system:
 * - Fixed target prices (not soft signals)
 * - Confidence bands
 * - Outcome markers (TP/FP/WEAK)
 * - Real accuracy metrics
 * 
 * NOW USES VERDICT ENGINE (V4) with SMART CACHING:
 * - P3: Smart Caching Layer for <2s response times
 * - Heavy ML computations are cached (5min TTL)
 * - Light overlay adjustments applied in real-time
 * - Multi-horizon ensemble (1D, 7D, 30D)
 * - Rules + Meta-Brain + Calibration pipeline
 * - Shows all horizon candidates
 * - Position sizing recommendations (Kelly-lite)
 * 
 * TradingView-like Chart Implementation:
 * - Using lightweight-charts for professional candlestick rendering
 * - OHLC candlestick data with dynamic resolution
 * - Volume histogram below price
 * - Short forecast segment (NOT stretched across chart)
 * - Proper zoom/pan/crosshair interactions
 * 
 * Uses /api/market/chart/price-vs-expectation-v4 endpoint
 * Uses /api/market/candles endpoint for OHLC data
 */

import { useState, useEffect, useCallback, useMemo } from 'react';
import { 
  RefreshCwIcon, 
  TrendingUpIcon, 
  TrendingDownIcon, 
  MinusIcon, 
  ActivityIcon,
  BarChart3Icon,
  CheckCircleIcon,
  Info,
  Zap,
  Target,
  Shield,
  AlertTriangle,
  Brain,
  LineChart,
  Gauge
} from 'lucide-react';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip';
import TradingViewChartV2 from '../../components/charts/TradingViewChartV2';
import ForecastOnlyChart from '../../components/charts/ForecastOnlyChart';
import SegmentedForecastChart from '../../components/charts/SegmentedForecastChart';
import SentimentForecastChartV2 from '../../components/charts/SentimentForecastChartV2';
import ChartControlsBar from '../../components/intelligence/ChartControlsBar';
import MetaBrainCorePanel from '../../components/MetaBrainCorePanel';
import TopConvictionTable from '../../components/TopConvictionTable.tsx';
import SentimentAltSignalsCompact from '../../components/sentiment/SentimentAltSignalsCompact';
import SentimentPerformanceTableV3 from '../../components/sentiment/SentimentPerformanceTableV3';
import SentimentForecastCard from '../../components/sentiment/SentimentForecastCard';
// Exchange V2 components (E1-E5)
import ExchangeForecastChartV2 from '../../components/exchange/ExchangeForecastChartV2';
import ExchangeForecastChartV3 from '../../components/exchange/ExchangeForecastChartV3';
import ExchangeForecastCardV2 from '../../components/exchange/ExchangeForecastCardV2';
import ExchangePerformanceTableV2 from '../../components/exchange/ExchangePerformanceTableV2';
import ExchangeAltSignalsCompact from '../../components/exchange/ExchangeAltSignalsCompact';
import OnchainAltSignalsCompact from '../../components/onchain/OnchainAltSignalsCompact';
import BtcFractalForecastTable from '../../components/fractal/BtcFractalForecastTable';
// OnChain V2 components (O9.5) → PHASE 3: Alt Liquidity Signal
import { 
  OnchainContextSection,
  OnChainForecastChartV2,
  OnChainForecastCardV2,
  OnChainPerformanceTableV2
} from '../../components/onchain';
// PHASE 3 + BLOCK 8: LARE v2 Panel (New UI Discipline)
import { LareV2Panel } from '../../components/onchain-liquidity';
import OnchainMarketPrediction from '../../components/prediction/OnchainMarketPrediction';
import ForecastTable from '../../components/forecast/ForecastTable';
// Meta Brain components — used for Forecast tab
import MetaBrainChart from '../../modules/meta-brain-ui/MetaBrainChart';
import MetaBrainForecastTable from '../../modules/meta-brain-ui/MetaBrainForecastTable';
import FractalPredictionPanel from '../../modules/meta-brain-ui/FractalPredictionPanel';
import AssetPicker from '../../components/market/AssetPicker';
import { normalizeSymbol, extractBase } from '../../lib/api/market';
import { fetchMultiModelForecast } from '../../lib/api/forecastSeries';
import '../../styles/prediction-polish.css';
// FOMO AI Intelligence components (moved from FOMO AI tab)
import { useFomoAiWidgets } from '../../hooks/useFomoAiWidgets';

const API_URL = process.env.REACT_APP_BACKEND_URL || '';

const RANGES = ['24h', '7d', '30d', '90d'];

// ═══════════════════════════════════════════════════════════════
// MAIN COMPONENT
// ═══════════════════════════════════════════════════════════════

export default function PriceExpectationV2Page() {
  // Use canonical symbol format (BTCUSDT)
  const [symbol, setSymbol] = useState('BTCUSDT');
  const [range, setRange] = useState('7d');
  const [horizon, setHorizon] = useState('1D');
  const [activeLayer, setActiveLayer] = useState('forecast'); // Prediction = forecast (MetaBrain)
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  
  // TradingView Chart Data (OHLC Candles)
  const [candles, setCandles] = useState([]);
  const [volume, setVolume] = useState([]);
  const [candlesLoading, setCandlesLoading] = useState(false);
  
  // Chart toggle states
  const [showVolume, setShowVolume] = useState(true);
  const [showOutcomes, setShowOutcomes] = useState(true);
  
  // Header price from reliable source (Binance via /api/ui/candles)
  const [headerPrice, setHeaderPrice] = useState(null);
  const [headerPriceChange, setHeaderPriceChange] = useState(null);
  
  // V3.1: Unified chart controls
  const [viewMode, setViewMode] = useState('candle'); // 'candle' | 'line'
  const [signalSource, setSignalSource] = useState('exchange'); // 'exchange' | 'sentiment' | 'onchain'
  const [enabledLayers, setEnabledLayers] = useState(new Set(['prediction'])); // Start with just prediction
  const [forecastData, setForecastData] = useState(null); // { candles: [], lines: {} }
  const [forecastLoading, setForecastLoading] = useState(false);
  
  // Derived: base asset name for display
  const asset = extractBase(symbol);
  
  // FOMO AI Intelligence data (Labs, Sectors, Macro)
  const { labsData, sectorsData, macroData } = useFomoAiWidgets(symbol);
  
  // Legacy compatibility wrapper
  const setAsset = (base) => {
    const canonical = normalizeSymbol(base);
    setSymbol(canonical);
  };
  
  // V3.1: Toggle layer handler - SINGLE SELECT (only one active)
  const handleToggleLayer = useCallback((layerKey) => {
    // Single select - only one layer can be active
    setEnabledLayers(new Set([layerKey]));
    setActiveLayer(layerKey);
  }, []);
  
  // V3.1: View mode change handler
  const handleViewModeChange = useCallback((mode) => {
    setViewMode(mode);
  }, []);
  
  // V3.1: Layer change handler
  const handleLayerChange = useCallback((layerKey) => {
    setActiveLayer(layerKey);
  }, []);
  
  // Fetch OHLC candles for TradingView chart
  const fetchCandles = useCallback(async () => {
    setCandlesLoading(true);
    try {
      const res = await fetch(
        `${API_URL}/api/market/candles?symbol=${symbol}&range=${range}`
      );
      if (!res.ok) throw new Error(`Candles: ${res.status}`);
      const json = await res.json();
      
      if (json.ok && json.candles) {
        // Normalize candle format: API may return {t,o,h,l,c} or {time,open,high,low,close}
        const normalized = json.candles.map(c => ({
          time: c.time ?? (c.t ? Math.floor(new Date(c.t).getTime() / 1000) : 0),
          open: c.open ?? c.o ?? 0,
          high: c.high ?? c.h ?? 0,
          low: c.low ?? c.l ?? 0,
          close: c.close ?? c.c ?? 0,
          volume: c.volume ?? c.v ?? 0,
        })).filter(c => c.time > 0);
        setCandles(normalized);
        
        const vol = (json.volume || []).map(v => ({
          time: v.time ?? (v.t ? Math.floor(new Date(v.t).getTime() / 1000) : 0),
          value: v.value ?? v.volume ?? v.v ?? 0,
        })).filter(v => v.time > 0);
        setVolume(vol.length > 0 ? vol : normalized.map(c => ({ time: c.time, value: c.volume })));
      }
    } catch (err) {
      console.error('[Candles] Error:', err.message);
    } finally {
      setCandlesLoading(false);
    }
  }, [symbol, range]);
  
  // Fetch BTC price for header from reliable source
  useEffect(() => {
    const fetchHeaderPrice = async () => {
      try {
        const res = await fetch(`${API_URL}/api/ui/candles?asset=${asset}&days=2`);
        if (!res.ok) return;
        const json = await res.json();
        const c = json.candles || [];
        if (c.length > 0) {
          const last = c[c.length - 1];
          const price = last.close ?? last.c;
          setHeaderPrice(price);
          if (c.length > 1) {
            const prev = c[c.length - 2];
            const prevClose = prev.close ?? prev.c;
            if (prevClose && price) {
              setHeaderPriceChange(((price - prevClose) / prevClose * 100).toFixed(2));
            }
          }
        }
      } catch (e) { /* ignore */ }
    };
    fetchHeaderPrice();
    const interval = setInterval(fetchHeaderPrice, 60000);
    return () => clearInterval(interval);
  }, [asset]);
  
  // Fetch verdict/intelligence data
  const fetchData = useCallback(async () => {
    setLoading(true);
    setError(null);
    
    try {
      const res = await fetch(
        `${API_URL}/api/market/chart/price-vs-expectation-v4?asset=${asset}&range=${range}&horizon=${horizon}`
      );
      if (!res.ok) throw new Error(`Server error: ${res.status}`);
      const json = await res.json();
      
      if (!json.ok) {
        throw new Error(json.error || 'Failed to load data');
      }
      
      setData(json);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [asset, range, horizon]);
  
  // V3.1: Fetch forecast data for chart overlay
  // Map layer keys to API model names
  const layerToApiModel = (layerKey) => {
    const mapping = {
      'forecast': 'combined',  // forecast layer uses combined model
      'exchange': 'exchange',
      'onchain': 'onchain',
      'sentiment': 'sentiment',
    };
    return mapping[layerKey] || layerKey;
  };
  
  const fetchForecastOverlays = useCallback(async () => {
    // V3.2: Skip forecast fetch for non-prediction layers (they use ForecastOnlyChart)
    // V3.4: Also skip for prediction layer (uses TradingViewChartV2)
    const forecastLayers = ['forecast', 'exchange', 'onchain', 'sentiment'];
    if (forecastLayers.includes(activeLayer) || activeLayer === 'prediction') {
      setForecastData(null);
      setForecastLoading(false);
      return;
    }
    
    if (enabledLayers.size === 0) {
      setForecastData(null);
      return;
    }
    
    setForecastLoading(true);
    try {
      const baseSymbol = extractBase(symbol);
      const models = Array.from(enabledLayers)
        .filter(l => !forecastLayers.includes(l)) // Skip forecast layers
        .map(layerToApiModel);
      
      if (models.length === 0) {
        setForecastData(null);
        setForecastLoading(false);
        return;
      }
      
      // Fetch both candle and line formats
      const [candleData, lineData] = await Promise.all([
        fetchMultiModelForecast({
          symbol: baseSymbol,
          horizon: horizon,
          models: [layerToApiModel(activeLayer)], // Candles for active layer only
          format: 'candles',
        }),
        fetchMultiModelForecast({
          symbol: baseSymbol,
          horizon: horizon,
          models: models, // Lines for all enabled layers (already mapped)
          format: 'line',
        }),
      ]);
      
      // Build forecast data structure - use layer key for internal mapping
      const apiModel = layerToApiModel(activeLayer);
      const forecastCandles = candleData.get(apiModel)?.candles || [];
      const lines = {};
      // Reverse map: API model name back to layer key for internal use
      const apiModelToLayer = {
        'combined': 'forecast',
        'exchange': 'exchange',
        'onchain': 'onchain',
        'sentiment': 'sentiment',
      };
      lineData.forEach((response, apiModel) => {
        if (response.line?.length) {
          const layerKey = apiModelToLayer[apiModel] || apiModel;
          lines[layerKey] = response.line;
        }
      });
      
      setForecastData({
        candles: forecastCandles,
        lines: lines,
      });
    } catch (err) {
      console.error('[ForecastData] Error:', err);
      setForecastData(null);
    } finally {
      setForecastLoading(false);
    }
  }, [symbol, horizon, enabledLayers, activeLayer]);
  
  // Fetch both candles and intelligence data
  useEffect(() => {
    fetchCandles();
    fetchData();
  }, [fetchCandles, fetchData]);
  
  // Fetch forecast overlays when dependencies change
  useEffect(() => {
    fetchForecastOverlays();
  }, [fetchForecastOverlays]);
  
  // Build outcome markers for TradingViewChart
  const outcomes = (data?.outcomes || [])
    .filter(o => o.ts && (o.label === 'TP' || o.label === 'FP'))
    .map(o => ({
      time: Math.floor(new Date(o.ts).getTime() / 1000),
      win: o.label === 'TP',
    }));
  
  // Current asset info (derived from symbol)
  const currentAsset = {
    symbol: symbol,
    name: asset,
    short: asset,
  };
  
  // Latest price from candles
  const latestCandle = candles?.[candles.length - 1];
  const firstCandle = candles?.[0];
  const latestPrice = latestCandle?.close;
  const firstPrice = firstCandle?.close;
  const priceChange = latestPrice && firstPrice 
    ? ((latestPrice - firstPrice) / firstPrice * 100).toFixed(2)
    : null;
  
  // Future forecast
  const futurePoint = data?.layers?.meta?.futurePoint;
  const futureBand = data?.layers?.meta?.futureBand;
  
  return (
    <div className="min-h-screen bg-white" data-testid="price-expectation-v2-page">
      {/* Header — unified 71px */}
      <div className="border-b border-gray-200 bg-white h-[71px]">
        <div className="px-6 w-full h-full flex items-center justify-between">
          <div className="flex items-center gap-3">
            <svg className="w-5 h-5 text-gray-400" viewBox="0 0 24 24" fill="currentColor" stroke="none">
              <rect x="2" y="16" width="3.5" height="5" rx="0.4" opacity="0.4" />
              <rect x="7" y="12" width="3.5" height="9" rx="0.4" opacity="0.55" />
              <rect x="12" y="8.5" width="3.5" height="12.5" rx="0.4" opacity="0.75" />
              <rect x="17" y="5" width="3.5" height="16" rx="0.4" />
            </svg>
            <div>
              <h1 className="text-xl font-bold text-gray-900">Alpha</h1>
              <p className="text-sm text-gray-500">Cross-layer intelligence & meta analysis</p>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <span className="text-xl font-bold text-gray-900" data-testid="header-btc-price">
              ${headerPrice?.toLocaleString() || latestPrice?.toLocaleString() || '—'}
            </span>
            {(headerPriceChange || priceChange) && (
              <span className={`text-sm font-medium ${
                parseFloat(headerPriceChange || priceChange) >= 0 ? 'text-green-600' : 'text-red-600'
              }`}>
                {parseFloat(headerPriceChange || priceChange) >= 0 ? '+' : ''}{headerPriceChange || priceChange}%
              </span>
            )}
          </div>
        </div>
      </div>
      
      {/* Main Content */}
      <div className="px-6 py-6">
        {error && (
          <div className="mb-4 p-4 bg-red-50 border border-red-200 rounded-lg text-red-700">
            {error}
          </div>
        )}
        
        <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
          {/* Chart Area - Full width on mobile, 3 columns on desktop */}
          <div className="lg:col-span-3 space-y-4">
            {/* Controls row — layers, view mode, horizons */}
            <div className="flex items-center justify-between gap-4 flex-wrap">
              <ChartControlsBar
                activeLayer={activeLayer}
                onLayerChange={handleLayerChange}
                viewMode={viewMode}
                onViewModeChange={handleViewModeChange}
                horizon={horizon}
                onHorizonChange={setHorizon}
                enabledLayers={enabledLayers}
                onToggleLayer={handleToggleLayer}
              />
            </div>
            
            {/* TradingView-like Chart */}
            <div className="relative">
              {/* Loading indicator */}
              {(loading || candlesLoading || forecastLoading) && (
                <div className="absolute inset-0 flex items-center justify-center bg-white/50 z-10 rounded-xl">
                  <div className="flex items-center gap-2 text-gray-500">
                    <RefreshCwIcon className="w-5 h-5 animate-spin" />
                    <span className="text-sm">Loading...</span>
                  </div>
                </div>
              )}
              
              {/* TradingViewChartV2 - V3.1 Clean Implementation */}
              {/* V3.2: Use ForecastOnlyChart for forecast/onchain/sentiment tabs */}
              {/* V4.5: Use SegmentedForecastChart for exchange tab (BLOCK 5-6) */}
              {/* Chart area — layer-specific */}
              {activeLayer === 'forecast' ? (
                <MetaBrainChart
                  asset={extractBase(symbol)}
                  horizonDays={horizon === '1D' ? 1 : horizon === '30D' ? 30 : 7}
                  viewMode={viewMode}
                />
              ) : activeLayer === 'exchange' ? (
                <ExchangeForecastChartV3
                  symbol={extractBase(symbol)}
                  horizon={horizon === '30D' ? '30D' : horizon === '1D' ? '1D' : '7D'}
                  viewMode={viewMode}
                />
              ) : activeLayer === 'sentiment' ? (
                <SentimentForecastChartV2
                  symbol={extractBase(symbol)}
                  windowKey={horizon === '1D' ? '24H' : horizon === '30D' ? '30D' : '7D'}
                  height={500}
                  viewMode={viewMode}
                />
              ) : activeLayer === 'onchain' ? (
                // V2: On-chain Market Prediction (dark theme, 9 blocks)
                <OnchainMarketPrediction />
              ) : activeLayer === 'fractal' ? (
                <FractalPredictionPanel
                  horizonDays={horizon === '1D' ? 1 : horizon === '30D' ? 30 : 7}
                  viewMode={viewMode}
                >
                  <BtcFractalForecastTable
                    horizon={horizon === '30D' ? '30D' : '7D'}
                    limit={horizon === '30D' ? 40 : 15}
                  />
                </FractalPredictionPanel>
              ) : activeLayer === 'ta' ? (
                <div className="h-[500px] flex flex-col items-center justify-center rounded-xl border border-gray-200 bg-gradient-to-br from-pink-50/50 to-white gap-3">
                  <BarChart3Icon className="w-10 h-10 text-pink-400" />
                  <div className="text-center">
                    <div className="text-gray-800 font-semibold text-base mb-1">Tech Analysis · Native v1</div>
                    <div className="text-gray-500 text-sm mb-3">
                      Trend · Momentum · RSI · Support / Resistance — live engine for 11 production assets.
                    </div>
                    <a
                      href="/tech-analysis"
                      className="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg bg-pink-500 hover:bg-pink-600 text-white text-sm font-medium transition-colors"
                      data-testid="ta-open-terminal"
                    >
                      Open Tech Analysis Terminal →
                    </a>
                  </div>
                </div>
              ) : (
                <ForecastOnlyChart
                  symbol={extractBase(symbol)}
                  layer={activeLayer}
                  horizon={horizon}
                  height={500}
                  viewMode={viewMode}
                  showOutcomes={showOutcomes}
                  showVolume={showVolume}
                />
              )}
            </div>
            
            {/* Forecast Performance Table - показывает историю прогнозов */}
            {/* Use layer-specific tables */}
            {activeLayer === 'sentiment' ? (
              <SentimentPerformanceTableV3
                symbol={extractBase(symbol)}
                horizon={horizon === '1D' ? '24H' : horizon === '30D' ? '30D' : '7D'}
                limit={horizon === '30D' ? 30 : horizon === '7D' ? 7 : 1}
              />
            ) : activeLayer === 'exchange' ? (
              <ExchangePerformanceTableV2
                symbol={extractBase(symbol)}
                horizon={horizon === '1D' ? '24H' : horizon === '30D' ? '30D' : '7D'}
                limit={horizon === '30D' ? 40 : horizon === '7D' ? 15 : 10}
              />
            ) : activeLayer === 'onchain' ? (
              // PHASE 3: Performance table is now inside AltLiquidityPanel
              null
            ) : activeLayer === 'forecast' ? (
              <>
                {futurePoint && (
                  <FutureForecastCard 
                    forecast={futurePoint} 
                    band={futureBand}
                    currentPrice={latestPrice}
                    horizon={horizon}
                    metaForecast={data?.metaForecast}
                  />
                )}
                <MetaBrainForecastTable
                  asset={extractBase(symbol)}
                  horizonDays={horizon === '1D' ? 1 : horizon === '30D' ? 30 : 7}
                />
              </>
            ) : activeLayer === 'fractal' || activeLayer === 'ta' ? (
              null
            ) : (
              <ForecastTable 
                symbol={extractBase(symbol)} 
                horizon={horizon} 
              />
            )}
            
            {/* Future Forecast Card */}
            {/* Use layer-specific forecast cards */}
            {activeLayer === 'sentiment' ? (
              <SentimentForecastCard
                key={`sentiment-forecast-${symbol}-${horizon}`}
                symbol={extractBase(symbol)}
                windowKey={horizon === '1D' ? '24H' : horizon === '30D' ? '30D' : '7D'}
                currentPrice={latestPrice}
              />
            ) : activeLayer === 'exchange' ? (
              <ExchangeForecastCardV2
                key={`exchange-forecast-${symbol}-${horizon}`}
                symbol={extractBase(symbol)}
                horizon={horizon === '1D' ? '24H' : horizon === '30D' ? '30D' : '7D'}
              />
            ) : activeLayer === 'onchain' ? (
              // PHASE 3: Forecast card is now inside AltLiquidityPanel
              null
            ) : activeLayer === 'forecast' ? (
              null
            ) : activeLayer === 'fractal' || activeLayer === 'ta' ? (
              null
            ) : (
              futurePoint && (
                <FutureForecastCard 
                  forecast={futurePoint} 
                  band={futureBand}
                  currentPrice={latestPrice}
                  horizon={horizon}
                  metaForecast={data?.metaForecast}
                />
              )
            )}
            
            {/* Analytics Row - Model Health, Performance, Error Analysis, Outcomes (hidden for onchain V2) */}
            {activeLayer !== 'onchain' && (
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
              <ModelHealthPanelCompact metrics={data?.metrics} />
              <PerformancePanelCompact metrics={data?.metrics} />
              <ErrorClusterPanelCompact errorClusters={data?.errorClusters} />
              <OutcomesCardCompact metrics={data?.metrics} />
            </div>
            )}
            
            {/* BLOCK P1.2: Layer-specific Top Tables */}
            {activeLayer === 'sentiment' ? (
              <SentimentAltSignalsCompact
                windowKey={horizon === '1D' ? '24H' : horizon === '30D' ? '30D' : '7D'}
                onSelectSymbol={(sym) => setSymbol(normalizeSymbol(sym))}
                selectedSymbol={extractBase(symbol)}
              />
            ) : activeLayer === 'exchange' ? (
              <ExchangeAltSignalsCompact
                horizon={horizon === '1D' ? '24H' : horizon === '30D' ? '30D' : '7D'}
                selectedSymbol={extractBase(symbol)}
                onSelectSymbol={(sym) => setSymbol(normalizeSymbol(sym))}
              />
            ) : activeLayer === 'fractal' || activeLayer === 'ta' ? (
              null
            ) : activeLayer === 'forecast' ? (
              <div data-testid="prediction-unified-signals">
                <div className="flex items-center gap-2 mb-3">
                  {[
                    { key: 'exchange', label: 'Exchange' },
                    { key: 'sentiment', label: 'Sentiment' },
                    { key: 'onchain', label: 'On-chain' },
                  ].map(({ key, label }) => (
                    <button
                      key={key}
                      data-testid={`signal-source-${key}`}
                      onClick={() => setSignalSource(key)}
                      className={`px-3 py-1.5 text-xs font-medium rounded-lg transition-all ${
                        signalSource === key
                          ? 'bg-gray-900 text-white'
                          : 'bg-gray-100 text-gray-500 hover:bg-gray-200'
                      }`}
                    >
                      {label}
                    </button>
                  ))}
                </div>
                {signalSource === 'exchange' ? (
                  <ExchangeAltSignalsCompact
                    horizon={horizon === '1D' ? '24H' : horizon === '30D' ? '30D' : '7D'}
                    selectedSymbol={extractBase(symbol)}
                    onSelectSymbol={(sym) => setSymbol(normalizeSymbol(sym))}
                  />
                ) : signalSource === 'sentiment' ? (
                  <SentimentAltSignalsCompact
                    windowKey={horizon === '1D' ? '24H' : horizon === '30D' ? '30D' : '7D'}
                    onSelectSymbol={(sym) => setSymbol(normalizeSymbol(sym))}
                    selectedSymbol={extractBase(symbol)}
                  />
                ) : (
                  <OnchainAltSignalsCompact
                    horizon={horizon === '1D' ? '1D' : horizon === '30D' ? '30D' : '7D'}
                    selectedSymbol={extractBase(symbol)}
                    onSelectSymbol={(sym) => setSymbol(normalizeSymbol(sym))}
                  />
                )}
              </div>
            ) : activeLayer === 'onchain' ? (
              <OnchainAltSignalsCompact
                horizon={horizon === '1D' ? '1D' : horizon === '30D' ? '30D' : '7D'}
                selectedSymbol={extractBase(symbol)}
                onSelectSymbol={(sym) => setSymbol(normalizeSymbol(sym))}
              />
            ) : (
              <TopConvictionTable 
                horizon={horizon}
                selectedSymbol={symbol}
                onSelectSymbol={(newSymbol) => setSymbol(normalizeSymbol(newSymbol))}
              />
            )}
            
            {/* Exchange Segments Info - Only show for exchange layer */}
            {activeLayer === 'exchange' && (
              <div className="flex items-center gap-2 mt-4 px-1">
                <TooltipProvider>
                  <Tooltip>
                    <TooltipTrigger>
                      <div className="flex items-center gap-1 text-[11px] text-slate-400 cursor-help">
                        <Info className="w-3 h-3" />
                        <span>Forecast Methodology</span>
                      </div>
                    </TooltipTrigger>
                    <TooltipContent side="top" className="max-w-xs text-xs">
                      <p className="font-medium mb-1">Rolling Forecast Curve</p>
                      <p>Forecast candles built from real model predictions, not simulations. Each candle = one DB record. Curve smooths as more forecasts accumulate.</p>
                    </TooltipContent>
                  </Tooltip>
                </TooltipProvider>
              </div>
            )}
            
            {/* Sentiment Info - Only show for sentiment layer */}
            {activeLayer === 'sentiment' && (
              <div className="bg-cyan-50 rounded-lg border border-cyan-200 p-3 mt-4">
                <div className="text-xs text-cyan-700 space-y-1">
                  <div className="font-medium text-cyan-800 mb-1">How Sentiment Forecast Works</div>
                  <div>• Aggregates Twitter sentiment from tracked influencers</div>
                  <div>• Weighted by author score, influence, and recency</div>
                  <div>• <span className="text-emerald-600 font-medium">LONG</span> = positive bias, <span className="text-red-600 font-medium">SHORT</span> = negative bias</div>
                  <div>• Expected return based on sentiment strength</div>
                </div>
              </div>
            )}
            
            {/* PHASE 3: Alt Liquidity Signal Info — removed in V2 redesign */}

            {/* Market Context — macro gauges, alerts, sectors — Exchange only */}
            {activeLayer === 'exchange' && (
              <FomoIntelSection 
                symbol={symbol}
                macroData={macroData}
                labsData={labsData}
                sectorsData={sectorsData}
              />
            )}
          </div>
          
          {/* Side Panel - Core Panel (always visible across all tabs) */}
          <div className="space-y-3">
            <MetaBrainCorePanel verdict={data?.verdict} candidates={data?.candidates} overlay={data?.overlay} currentPrice={headerPrice || latestPrice} />
          </div>
        </div>
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════
// CHART BUILDER (DEPRECATED - Now using TradingViewChart)
// The buildChartOption function was removed as part of the
// TradingView Lightweight Charts migration.
// ═══════════════════════════════════════════════════════════════

// ═══════════════════════════════════════════════════════════════
// FOMO Intelligence Section (bottom of Prediction page)
// Compact single-row block matching card height
// ═══════════════════════════════════════════════════════════════
function FomoIntelSection({ symbol, macroData, labsData, sectorsData }) {
  const labsSummary = labsData?.summary || { bullish: 0, caution: 0, bearish: 0, bias: 'Neutral' };
  const labsAlerts = labsData?.alerts || [];
  const sectors = sectorsData?.sectors || [];
  const macroFearGreed = macroData?.fearGreed ?? 0;
  const macroBlocked = macroData?.blocked || false;
  const macroPenalty = macroData?.penalty || 0;

  const fgLabel = macroFearGreed <= 25 ? 'Extreme Fear' : macroFearGreed <= 45 ? 'Fear' : macroFearGreed <= 55 ? 'Neutral' : macroFearGreed <= 75 ? 'Greed' : 'Extreme Greed';
  const fgColor = macroFearGreed <= 25 ? '#dc2626' : macroFearGreed <= 45 ? '#ea580c' : macroFearGreed <= 55 ? '#d97706' : macroFearGreed <= 75 ? '#16a34a' : '#059669';
  const biasColor = labsSummary.bias === 'Bullish' ? '#16a34a' : labsSummary.bias === 'Bearish' ? '#dc2626' : '#64748b';

  // Human-readable alert names
  const alertLabel = (name) => {
    const map = { liquidity: 'Low Liquidity', dataquality: 'Data Quality', volatility: 'High Volatility', momentum: 'Momentum Shift', volume: 'Volume Alert', funding: 'Funding Rate', whale: 'Whale Activity' };
    return map[name?.toLowerCase()] || name;
  };

  return (
    <div className="bg-white rounded-xl border border-gray-200 overflow-hidden" data-testid="market-context-section">
      {/* Header */}
      <div className="px-4 py-2.5 border-b border-gray-100">
        <div className="text-xs font-medium text-gray-500 uppercase tracking-wide">Market Context</div>
      </div>

      {/* Single compact macro row: F&G + BTC Dom + Stable Dom + Bias + BLOCKED */}
      <div className="px-4 py-2.5 flex flex-wrap items-center gap-4 border-b border-gray-100" data-testid="macro-gauges">
        <div className="flex items-center gap-1.5">
          <span className="text-lg font-bold tabular-nums" style={{ color: fgColor }}>{macroFearGreed}</span>
          <span className="text-[11px] font-medium" style={{ color: fgColor }}>{fgLabel}</span>
        </div>
        <div className="h-5 w-px bg-gray-200" />
        <div className="flex items-center gap-1">
          <span className="text-xs font-bold text-gray-800 tabular-nums">{macroData?.btcDominance?.toFixed(1) ?? '—'}%</span>
          <span className="text-[10px] text-gray-400">BTC</span>
        </div>
        <div className="flex items-center gap-1">
          <span className="text-xs font-bold text-gray-800 tabular-nums">{macroData?.stableDominance?.toFixed(1) ?? '—'}%</span>
          <span className="text-[10px] text-gray-400">Stable</span>
        </div>
        <div className="h-5 w-px bg-gray-200" />
        <div className="flex items-center gap-1.5">
          <span className="text-[11px] font-semibold" style={{ color: biasColor }}>
            {labsSummary.bias}
          </span>
          <span className="text-[10px] text-gray-500">
            {labsSummary.bullish} Bullish · {labsSummary.caution} Caution · {labsSummary.bearish} Sell
          </span>
        </div>
        {macroBlocked && (
          <>
            <div className="h-5 w-px bg-gray-200 ml-auto" />
            <span className="text-[10px] font-semibold text-red-700">
              BLOCKED · {Math.round(macroPenalty * 100)}%
            </span>
          </>
        )}
      </div>

      {/* Two-column: Alerts + Sectors */}
      <div className="grid grid-cols-1 lg:grid-cols-2 divide-y lg:divide-y-0 lg:divide-x divide-gray-100">
        {/* Left: Active Alerts */}
        <div className="p-3">
          <div className="text-[10px] text-gray-400 uppercase tracking-wider font-medium mb-1.5">Active Alerts</div>
          {labsAlerts.length > 0 ? (
            <div className="space-y-1">
              {labsAlerts.slice(0, 4).map((alert, i) => (
                <div key={alert.id || i} className="flex items-center justify-between py-1.5 px-2.5 rounded-lg">
                  <div className="flex items-center gap-1.5">
                    <div className={`w-1.5 h-1.5 rounded-full ${
                      (alert.severity === 'CRITICAL' || alert.severity === 'EMERGENCY') ? 'bg-red-500' :
                      alert.severity === 'WARNING' ? 'bg-amber-500' : 'bg-emerald-500'
                    }`} />
                    <span className="text-xs text-gray-700 font-medium">{alertLabel(alert.labName)}</span>
                  </div>
                  <span className="text-[10px] text-gray-400 tabular-nums">{Math.round((alert.labConfidence || 0) * 100)}%</span>
                </div>
              ))}
            </div>
          ) : (
            <div className="flex items-center gap-2 py-1.5 px-2.5 rounded-lg">
              <div className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
              <span className="text-xs text-emerald-700">All systems normal</span>
            </div>
          )}
        </div>

        {/* Right: Sector Momentum */}
        <div className="p-3">
          <div className="text-[10px] text-gray-400 uppercase tracking-wider font-medium mb-1.5">Sector Momentum</div>
          <div className="space-y-1">
            {sectors.slice(0, 6).map((sector) => (
              <div key={sector.name} className="flex items-center gap-2">
                <span className="text-[11px] text-gray-500 w-14 text-right font-medium shrink-0">{sector.name}</span>
                <div className="flex-1 h-2 bg-gray-100 rounded-full overflow-hidden">
                  <div
                    className={`h-full rounded-full ${
                      sector.score >= 70 ? 'bg-emerald-400' :
                      sector.score >= 50 ? 'bg-emerald-300' :
                      sector.score >= 35 ? 'bg-blue-400' : 'bg-orange-400'
                    }`}
                    style={{ width: `${Math.min(sector.score, 100)}%` }}
                  />
                </div>
                <span className="text-[10px] font-semibold text-gray-600 w-7 text-right tabular-nums">{sector.score}%</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

function FundingCompactLine({ symbol }) {
  const [data, setData] = useState(null);
  const API_BASE = process.env.REACT_APP_BACKEND_URL || '';
  useEffect(() => {
    fetch(`${API_BASE}/api/v10/exchange/funding/sentiment?symbol=${symbol}`)
      .then(r => r.json())
      .then(d => { if (d.ok) setData(d.data || d); })
      .catch(() => {});
  }, [symbol, API_BASE]);
  if (!data) return null;
  const avg = data.avgFunding ?? data.funding?.avg;
  const zScore = data.zScore ?? data.funding?.zScore;
  const longPct = data.openInterest?.longPercent ?? data.oi?.longPct ?? 50;
  return (
    <div className="flex items-center gap-3 px-1">
      <div className="flex-1 h-2.5 bg-gray-100 rounded-full overflow-hidden flex">
        <div className="h-full bg-green-400 rounded-l-full" style={{ width: `${longPct}%` }} />
        <div className="h-full bg-red-400 rounded-r-full" style={{ width: `${100 - longPct}%` }} />
      </div>
      <span className="text-[10px] text-gray-500 whitespace-nowrap">
        {avg != null ? `${(avg * 100).toFixed(2)}%` : '—'} 
        {zScore != null && <span className={`ml-1 font-medium ${zScore > 1 ? 'text-green-600' : zScore < -1 ? 'text-red-600' : 'text-gray-500'}`}>Z:{zScore.toFixed(1)}</span>}
      </span>
    </div>
  );
}

function getClosestPrice(prices, ts) {
  if (!prices || prices.length === 0) return 0;
  
  let closest = prices[0];
  let minDiff = Math.abs(prices[0].ts - ts);
  
  for (const p of prices) {
    const diff = Math.abs(p.ts - ts);
    if (diff < minDiff) {
      minDiff = diff;
      closest = p;
    }
  }
  
  return closest.price;
}

// ═══════════════════════════════════════════════════════════════
// SUB-COMPONENTS
// ═══════════════════════════════════════════════════════════════

function FutureForecastCard({ forecast, band, currentPrice, horizon = '1D', metaForecast }) {
  if (!forecast) return null;
  
  // Calculate target time based on horizon
  const horizonMs = {
    '1D': 24 * 60 * 60 * 1000,
    '7D': 7 * 24 * 60 * 60 * 1000,
    '30D': 30 * 24 * 60 * 60 * 1000,
  };
  const targetTime = new Date(forecast.ts + (horizonMs[horizon] || horizonMs['1D']));
  const isUp = forecast.direction === 'UP';
  const isDown = forecast.direction === 'DOWN';
  
  // Horizon label
  const horizonLabel = {
    '1D': '24H',
    '7D': '7 DAY',
    '30D': '30 DAY',
  };
  
  // Block 31: Position Sizing Recommendation
  // Kelly Criterion simplified: f = (p * b - q) / b
  // where p = win rate (confidence), b = reward/risk ratio, q = 1 - p
  const confidence = forecast.confidence;
  const rewardRisk = Math.abs(forecast.expectedMovePct) / 2; // Assume 2:1 R/R
  const kellyFraction = Math.max(0, (confidence * rewardRisk - (1 - confidence)) / rewardRisk);
  const suggestedSize = Math.min(25, Math.round(kellyFraction * 100 * 0.5)); // Half-Kelly, max 25%
  
  // Risk level colors
  const riskColors = {
    'LOW': 'text-emerald-700',
    'MEDIUM': 'text-amber-700',
    'HIGH': 'text-orange-700',
    'EXTREME': 'text-red-700',
  };
  
  // Meta-aware indicator (if confidence was adjusted)
  const isMetaAdjusted = metaForecast?.isMetaAdjusted;
  const rawConfidence = metaForecast?.raw?.confidence;
  const confidenceReduction = rawConfidence ? Math.round((rawConfidence - confidence) * 100) : 0;
  
  return (
    <div className={`prediction-card p-4 animate-slide-up`} data-testid="future-forecast">
      {/* Meta-Aware Header */}
      {isMetaAdjusted && (
        <div className="flex items-center gap-2 mb-3 pb-3 border-b border-gray-200/50">
          <TooltipProvider delayDuration={0}>
            <Tooltip>
              <TooltipTrigger>
                <div className={`text-[10px] font-bold ${riskColors[metaForecast?.riskLevel] || riskColors['MEDIUM']}`}>
                  {metaForecast?.riskLevel} RISK
                </div>
              </TooltipTrigger>
              <TooltipContent className="tooltip-dark">
                <p className="text-xs">Risk level based on market conditions</p>
              </TooltipContent>
            </Tooltip>
          </TooltipProvider>
          <div className="text-[11px] text-gray-500 flex items-center gap-1">
            <Brain className="w-3 h-3" />
            Meta-Brain adjusted: -{confidenceReduction}%
          </div>
          {metaForecast?.action && (
            <div className={`ml-auto text-xs font-bold ${
              metaForecast.action === 'BUY' ? 'text-emerald-600' :
              metaForecast.action === 'SELL' ? 'text-red-500' :
              'text-gray-500'
            }`}>
              {metaForecast.action}
            </div>
          )}
        </div>
      )}
      
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div>
          <div className="text-[10px] text-gray-500 mb-1 uppercase tracking-wide font-medium">{horizonLabel[horizon] || '24H'} FORECAST</div>
          <div className="flex items-center gap-2">
            {isUp && <TrendingUpIcon className="w-5 h-5 text-emerald-600" />}
            {isDown && <TrendingDownIcon className="w-5 h-5 text-red-600" />}
            {!isUp && !isDown && <MinusIcon className="w-5 h-5 text-gray-400" />}
            <span className="metric-value metric-value-lg text-gray-900">
              ${forecast.targetPrice?.toLocaleString()}
            </span>
            <span className={`text-sm font-semibold ${
              isUp ? 'text-emerald-600' : isDown ? 'text-red-600' : 'text-gray-500'
            }`}>
              {forecast.expectedMovePct > 0 ? '+' : ''}{forecast.expectedMovePct?.toFixed(2)}%
            </span>
          </div>
        </div>
        
        <div className="text-right">
          <div className="text-[10px] text-gray-500 mb-1 uppercase tracking-wide font-medium">CONFIDENCE</div>
          <div className="flex items-center gap-1.5 justify-end">
            <div className="metric-value metric-value-lg text-gray-900">
              {(forecast.confidence * 100).toFixed(0)}%
            </div>
            {isMetaAdjusted && rawConfidence && (
              <span className="text-[11px] text-gray-400 line-through">
                {(rawConfidence * 100).toFixed(0)}%
              </span>
            )}
          </div>
        </div>
        
        {band && (
          <TooltipProvider delayDuration={0}>
            <Tooltip>
              <TooltipTrigger className="text-right">
                <div className="text-[10px] text-gray-500 mb-1 uppercase tracking-wide font-medium">BAND</div>
                <div className="text-sm text-gray-600 font-medium">
                  ${band.lower?.toLocaleString()} — ${band.upper?.toLocaleString()}
                </div>
              </TooltipTrigger>
              <TooltipContent className="tooltip-dark">
                <p className="text-xs">Expected price range based on volatility</p>
              </TooltipContent>
            </Tooltip>
          </TooltipProvider>
        )}
        
        {/* Block 31: Position Size Recommendation */}
        <TooltipProvider delayDuration={0}>
          <Tooltip>
            <TooltipTrigger className="text-right" data-testid="position-sizing">
              <div className="text-[10px] text-gray-500 mb-1 uppercase tracking-wide font-medium">POSITION SIZE</div>
              <div className={`metric-value metric-value-md ${
                suggestedSize >= 15 ? 'text-emerald-600' : 
                suggestedSize >= 8 ? 'text-amber-600' : 'text-red-500'
              }`}>
                {suggestedSize}%
              </div>
              <div className="text-[10px] text-gray-400">Kelly-based</div>
            </TooltipTrigger>
            <TooltipContent className="tooltip-dark">
              <p className="text-xs">Recommended position size using Half-Kelly criterion</p>
            </TooltipContent>
          </Tooltip>
        </TooltipProvider>
        
        <div className="text-right">
          <div className="text-[10px] text-gray-500 mb-1 uppercase tracking-wide font-medium">EVALUATE AT</div>
          <div className="text-sm text-gray-600 font-medium">
            {targetTime.toLocaleString()}
          </div>
        </div>
      </div>
      
      {/* Applied Overlays (risk rules that modified the forecast) */}
      {isMetaAdjusted && metaForecast?.appliedOverlays?.length > 0 && (
        <div className="mt-3 pt-3 border-t border-gray-200/30">
          <div className="text-[10px] text-gray-500 mb-2 uppercase tracking-wide font-medium">APPLIED RISK RULES</div>
          <div className="flex flex-wrap gap-2">
            {metaForecast.appliedOverlays.map((overlay, idx) => (
              <TooltipProvider key={idx} delayDuration={0}>
                <Tooltip>
                  <TooltipTrigger>
                    <div className="px-2.5 py-1 bg-white/60 border border-gray-200 rounded-lg text-[10px] text-gray-600 hover:bg-white transition-colors">
                      {overlay.source}: {overlay.id.replace(/_/g, ' ').toLowerCase()}
                    </div>
                  </TooltipTrigger>
                  <TooltipContent className="tooltip-dark">
                    <p className="text-xs">{overlay.reason}</p>
                  </TooltipContent>
                </Tooltip>
              </TooltipProvider>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function DirectionCard({ direction, confidence }) {
  const isUp = direction === 'UP';
  const isDown = direction === 'DOWN';
  
  return (
    <div className="prediction-card p-4 animate-fade-in" data-testid="direction-card">
      <div className="prediction-card-header">
        <div className={`icon-circle ${isUp ? 'icon-circle-green' : isDown ? 'icon-circle-red' : 'icon-circle-gray'}`}>
          {isUp && <TrendingUpIcon className="w-4 h-4" />}
          {isDown && <TrendingDownIcon className="w-4 h-4" />}
          {!isUp && !isDown && <MinusIcon className="w-4 h-4" />}
        </div>
        <div className="prediction-card-title">Direction Bias</div>
      </div>
      <div className="flex items-center gap-3">
        {isUp && <TrendingUpIcon className="w-6 h-6 text-emerald-600" />}
        {isDown && <TrendingDownIcon className="w-6 h-6 text-red-600" />}
        {!isUp && !isDown && <MinusIcon className="w-6 h-6 text-gray-400" />}
        <div>
          <div className={`metric-value metric-value-lg ${
            isUp ? 'text-emerald-600' : isDown ? 'text-red-600' : 'text-gray-500'
          }`}>
            {direction || 'FLAT'}
          </div>
          {confidence !== undefined && (
            <div className="text-sm text-gray-500">
              {(confidence * 100).toFixed(0)}% confident
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

/**
 * Block 20: Model Health Panel
 * Shows comprehensive model performance metrics
 */
function ModelHealthPanel({ metrics }) {
  if (!metrics) return null;
  
  const hasData = metrics.evaluatedCount > 0;
  
  // Color coding for scores
  const getScoreColor = (score) => {
    if (score >= 70) return 'text-green-600';
    if (score >= 50) return 'text-yellow-600';
    return 'text-red-600';
  };
  
  const getScoreBg = (score) => {
    if (score >= 70) return 'bg-green-100';
    if (score >= 50) return 'bg-yellow-100';
    return 'bg-red-100';
  };
  
  return (
    <div className="bg-white rounded-xl border border-gray-200 p-4" data-testid="model-health-panel">
      {/* Header with overall score */}
      <div className="flex items-center justify-between mb-4">
        <div className="text-xs font-medium text-gray-500">MODEL HEALTH ({metrics.horizon})</div>
        {hasData && (
          <div className={`text-xs font-bold ${getScoreBg(metrics.modelScore)} ${getScoreColor(metrics.modelScore)}`}>
            {metrics.modelScore}/100
          </div>
        )}
      </div>
      
      {!hasData ? (
        <div className="text-center py-6">
          <ActivityIcon className="w-8 h-8 text-gray-300 mx-auto mb-2" />
          <div className="text-sm text-gray-400">
            No evaluated forecasts yet.<br/>
            Metrics will appear after 24h.
          </div>
        </div>
      ) : (
        <div className="space-y-4">
          {/* Primary Metrics with progress bars */}
          <div className="grid grid-cols-2 gap-3">
            <div className="rounded-lg p-3">
              <div className="text-xs text-gray-500 mb-1">Accuracy</div>
              <div className={`text-xl font-bold ${getScoreColor(metrics.hitRatePct)}`}>
                {metrics.hitRatePct}%
              </div>
              <div className="h-1.5 bg-gray-200 rounded-full mt-1.5 overflow-hidden">
                <div className={`h-full rounded-full ${metrics.hitRatePct >= 60 ? 'bg-green-400' : metrics.hitRatePct >= 40 ? 'bg-yellow-400' : 'bg-red-400'}`}
                  style={{ width: `${Math.min(metrics.hitRatePct, 100)}%` }} />
              </div>
            </div>
            <div className="rounded-lg p-3">
              <div className="text-xs text-gray-500 mb-1">Direction</div>
              <div className={`text-xl font-bold ${getScoreColor(metrics.directionMatchPct)}`}>
                {metrics.directionMatchPct}%
              </div>
              <div className="h-1.5 bg-gray-200 rounded-full mt-1.5 overflow-hidden">
                <div className={`h-full rounded-full ${metrics.directionMatchPct >= 60 ? 'bg-green-400' : metrics.directionMatchPct >= 40 ? 'bg-yellow-400' : 'bg-red-400'}`}
                  style={{ width: `${Math.min(metrics.directionMatchPct, 100)}%` }} />
              </div>
            </div>
          </div>
          
          {/* Secondary Metrics */}
          <div className="space-y-2">
            <div className="flex justify-between items-center">
              <span className="text-sm text-gray-600">Avg Error</span>
              <span className={`font-medium ${metrics.avgDeviationPct > 5 ? 'text-red-600' : metrics.avgDeviationPct > 2 ? 'text-yellow-600' : 'text-green-600'}`}>
                {metrics.avgDeviationPct}%
              </span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-sm text-gray-600">Calibration</span>
              <span className={`font-medium ${getScoreColor(metrics.calibrationScore || 0)}`}>
                {metrics.calibrationScore || 0}%
              </span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-sm text-gray-400">Samples</span>
              <span className="text-sm text-gray-500">{metrics.evaluatedCount}</span>
            </div>
          </div>
          
          {/* Calibration Info */}
          {metrics.calibrationScore !== undefined && (
            <div className="pt-2 border-t border-gray-100">
              <div className="text-xs text-gray-400">
                Expected accuracy: {metrics.expectedCalibration}% based on avg confidence
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// Legacy MetricsCard for backward compatibility
function MetricsCard({ metrics }) {
  return <ModelHealthPanel metrics={metrics} />;
}

function OutcomesCard({ metrics }) {
  if (!metrics?.breakdown) return null;
  
  const { tp, fp, fn, weak } = metrics.breakdown;
  const total = tp + fp + fn + weak;
  
  if (total === 0) {
    return (
      <div className="bg-white rounded-xl border border-gray-200 p-4" data-testid="outcomes-card">
        <div className="text-xs font-medium text-gray-500 mb-3">OUTCOME BREAKDOWN</div>
        <div className="text-sm text-gray-400 text-center py-4">
          No evaluated forecasts yet.<br/>
          Wait 24h for first outcomes.
        </div>
      </div>
    );
  }
  
  return (
    <div className="bg-white rounded-xl border border-gray-200 p-4" data-testid="outcomes-card">
      <div className="text-xs font-medium text-gray-500 mb-3">OUTCOME BREAKDOWN</div>
      <div className="grid grid-cols-4 gap-2 text-center">
        <div>
          <div className="text-lg font-bold text-green-600">{tp}</div>
          <div className="text-xs text-gray-500">TP</div>
        </div>
        <div>
          <div className="text-lg font-bold text-red-600">{fp}</div>
          <div className="text-xs text-gray-500">FP</div>
        </div>
        <div>
          <div className="text-lg font-bold text-orange-600">{fn}</div>
          <div className="text-xs text-gray-500">FN</div>
        </div>
        <div>
          <div className="text-lg font-bold text-yellow-600">{weak}</div>
          <div className="text-xs text-gray-500">WEAK</div>
        </div>
      </div>
    </div>
  );
}

/**
 * Block 22 & 25: Layer Drivers with Adaptive Weighting
 * Shows layer contributions and their weights
 */
function DriversCard({ drivers, metrics }) {
  if (!drivers) return null;
  
  // Layer config with adaptive weights (Block 22)
  const layers = [
    { 
      key: 'exchange', 
      name: 'Exchange', 
      enabled: true,
      weight: 0.45, // Base weight
      score: drivers.exchange,
      description: 'Order flow, liquidations, OI',
    },
    { 
      key: 'onchain', 
      name: 'Onchain', 
      enabled: false,
      weight: 0.35,
      score: drivers.onchain || 0,
      description: 'Whale movements, exchange flows',
    },
    { 
      key: 'sentiment', 
      name: 'Sentiment', 
      enabled: false,
      weight: 0.20,
      score: drivers.sentiment || 0,
      description: 'Social, news, funding',
    },
  ];
  
  return (
    <div className="bg-white rounded-xl border border-gray-200 p-4" data-testid="drivers-card">
      <div className="flex items-center justify-between mb-3">
        <div className="text-xs font-medium text-gray-500">LAYER DRIVERS</div>
        <div className="text-xs text-gray-400">Block 22 & 25</div>
      </div>
      <div className="space-y-3">
        {layers.map(layer => (
          <div key={layer.key} className={`${!layer.enabled ? 'opacity-50' : ''}`}>
            <div className="flex justify-between items-center">
              <div className="flex items-center gap-2">
                <div className={`w-2 h-2 rounded-full ${
                  layer.enabled 
                    ? layer.score > 0 ? 'bg-green-500' : layer.score < 0 ? 'bg-red-500' : 'bg-gray-400'
                    : 'bg-gray-300'
                }`} />
                <span className="text-sm text-gray-600">{layer.name}</span>
                <span className="text-xs text-gray-400">({(layer.weight * 100).toFixed(0)}%)</span>
              </div>
              {layer.enabled ? (
                <span className={`font-medium ${
                  layer.score > 0 ? 'text-green-600' : layer.score < 0 ? 'text-red-600' : 'text-gray-500'
                }`}>
                  {layer.score > 0 ? '+' : ''}{layer.score}%
                </span>
              ) : (
                <span className="text-gray-400 text-xs">OFF</span>
              )}
            </div>
            {layer.enabled && (
              <div className="mt-1 h-1 bg-gray-100 rounded-full overflow-hidden">
                <div 
                  className={`h-full transition-all ${
                    layer.score > 0 ? 'bg-green-400' : layer.score < 0 ? 'bg-red-400' : 'bg-gray-300'
                  }`}
                  style={{ width: `${Math.min(100, Math.abs(layer.score) + 50)}%` }}
                />
              </div>
            )}
          </div>
        ))}
      </div>
      
      {/* Direction consensus */}
      <div className="mt-4 pt-3 border-t border-gray-100">
        <div className="flex justify-between items-center">
          <span className="text-xs text-gray-500">Direction Bias</span>
          <span className={`text-sm font-bold ${
            drivers.directionBias === 'UP' ? 'text-green-600' :
            drivers.directionBias === 'DOWN' ? 'text-red-600' : 'text-gray-500'
          }`}>
            {drivers.directionBias}
          </span>
        </div>
      </div>
    </div>
  );
}

/**
 * Block 28: Multi-Layer Alignment Panel
 * Shows consensus/divergence between data layers
 */
function AlignmentPanel({ alignment }) {
  if (!alignment) return null;
  
  const consensusConfig = {
    'STRONG_BULL': { color: 'text-green-600', bg: 'bg-green-100', label: 'Strong Bullish', icon: '↑↑' },
    'BULL': { color: 'text-green-500', bg: '', label: 'Bullish', icon: '↑' },
    'MIXED': { color: 'text-yellow-600', bg: 'bg-yellow-50', label: 'Mixed Signals', icon: '↔' },
    'NEUTRAL': { color: 'text-gray-500', bg: '', label: 'Neutral', icon: '—' },
    'BEAR': { color: 'text-red-500', bg: '', label: 'Bearish', icon: '↓' },
    'STRONG_BEAR': { color: 'text-red-600', bg: '', label: 'Strong Bearish', icon: '↓↓' },
  };
  
  const config = consensusConfig[alignment.consensus] || consensusConfig['NEUTRAL'];
  
  // Signal indicator
  const getSignalIcon = (signal) => {
    if (signal > 0) return '▲';
    if (signal < 0) return '▼';
    return '●';
  };
  
  const getSignalColor = (signal) => {
    if (signal > 0) return 'text-green-500';
    if (signal < 0) return 'text-red-500';
    return 'text-gray-400';
  };
  
  return (
    <div className="bg-white rounded-xl border border-gray-200 p-4" data-testid="alignment-panel">
      <div className="flex items-center justify-between mb-3">
        <div className="text-xs font-medium text-gray-500">LAYER ALIGNMENT</div>
        <div className="text-xs text-gray-400">Block 28</div>
      </div>
      
      {/* Consensus Badge */}
      <div className={`${config.bg} rounded-lg p-3 mb-3`}>
        <div className="flex items-center justify-between">
          <div>
            <div className={`text-lg font-bold ${config.color}`}>
              {config.icon} {config.label}
            </div>
            <div className="text-xs text-gray-500 mt-1">
              {alignment.activeLayerCount} layer{alignment.activeLayerCount !== 1 ? 's' : ''} active
            </div>
          </div>
          <div className="text-right">
            <div className="text-2xl font-bold text-gray-700">
              {(alignment.score * 100).toFixed(0)}%
            </div>
            <div className="text-xs text-gray-400">alignment</div>
          </div>
        </div>
      </div>
      
      {/* Layer Signals */}
      <div className="space-y-2">
        <div className="flex justify-between items-center">
          <span className="text-sm text-gray-600">Exchange</span>
          <span className={`font-medium ${getSignalColor(alignment.layerSignals?.exchange)}`}>
            {getSignalIcon(alignment.layerSignals?.exchange)}
          </span>
        </div>
        <div className="flex justify-between items-center opacity-50">
          <span className="text-sm text-gray-400">Onchain</span>
          <span className="text-gray-300">OFF</span>
        </div>
        <div className="flex justify-between items-center opacity-50">
          <span className="text-sm text-gray-400">Sentiment</span>
          <span className="text-gray-300">OFF</span>
        </div>
      </div>
    </div>
  );
}


/**
 * Block 29 & 30: Model Credibility + Capital Efficiency Panel
 * Shows model performance trends and simulated returns
 */
function PerformancePanel({ metrics }) {
  if (!metrics || metrics.evaluatedCount < 3) {
    return (
      <div className="bg-white rounded-xl border border-gray-200 p-4" data-testid="performance-panel">
        <div className="text-xs font-medium text-gray-500 mb-3">PERFORMANCE</div>
        <div className="text-center py-4 text-sm text-gray-400">
          Need more data (3+ forecasts)
        </div>
      </div>
    );
  }
  
  // Block 29: Model Credibility - simulate credibility based on recent performance
  const credibilityScore = Math.round(
    (metrics.directionMatchPct * 0.5 + metrics.hitRatePct * 0.3 + metrics.calibrationScore * 0.2)
  );
  
  // Block 30: Capital Efficiency - simulate equity curve
  // Assume: correct direction = +2%, wrong = -1%, TP = +3%, FP = -2%
  const { tp, fp, fn, weak } = metrics.breakdown;
  const simulatedReturn = (tp * 3) + (fn * 1) + (weak * 0.5) - (fp * 2);
  const maxDrawdown = fp * 2; // Simplified max DD
  const sharpeEstimate = metrics.evaluatedCount > 0 
    ? (simulatedReturn / (metrics.avgDeviationPct + 1)).toFixed(1)
    : 0;
  
  // Credibility trend (mock - would need historical data)
  const trendUp = metrics.directionMatchPct > 60;
  
  return (
    <div className="bg-white rounded-xl border border-gray-200 p-4" data-testid="performance-panel">
      <div className="flex items-center justify-between mb-3">
        <div className="text-xs font-medium text-gray-500">PERFORMANCE</div>
        <div className="text-xs text-gray-400">Block 29 & 30</div>
      </div>
      
      {/* Block 29: Credibility Score */}
      <div className="mb-4">
        <div className="flex justify-between items-center mb-1">
          <span className="text-sm text-gray-600">Model Credibility</span>
          <span className={`text-sm font-bold ${
            credibilityScore >= 60 ? 'text-green-600' : 
            credibilityScore >= 40 ? 'text-yellow-600' : 'text-red-600'
          }`}>
            {credibilityScore}%
            {trendUp ? ' ↑' : ' ↓'}
          </span>
        </div>
        <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
          <div 
            className={`h-full ${
              credibilityScore >= 60 ? 'bg-green-400' : 
              credibilityScore >= 40 ? 'bg-yellow-400' : 'bg-red-400'
            }`}
            style={{ width: `${credibilityScore}%` }}
          />
        </div>
      </div>
      
      {/* Block 30: Capital Efficiency Metrics */}
      <div className="space-y-2 pt-3 border-t border-gray-100">
        <div className="flex justify-between items-center">
          <span className="text-sm text-gray-600">Simulated Return</span>
          <span className={`font-medium ${simulatedReturn >= 0 ? 'text-green-600' : 'text-red-600'}`}>
            {simulatedReturn >= 0 ? '+' : ''}{simulatedReturn.toFixed(1)}%
          </span>
        </div>
        <div className="flex justify-between items-center">
          <span className="text-sm text-gray-600">Max Drawdown</span>
          <span className="font-medium text-red-500">-{maxDrawdown.toFixed(1)}%</span>
        </div>
        <div className="flex justify-between items-center">
          <span className="text-sm text-gray-600">Sharpe Est.</span>
          <span className={`font-medium ${parseFloat(sharpeEstimate) >= 1 ? 'text-green-600' : 'text-yellow-600'}`}>
            {sharpeEstimate}
          </span>
        </div>
      </div>
      
      {/* Mini equity curve visualization */}
      <div className="mt-3 pt-3 border-t border-gray-100">
        <div className="text-xs text-gray-400 mb-2">Equity Curve (simulated)</div>
        <div className="flex items-end gap-1 h-8">
          {[...Array(10)].map((_, i) => {
            const baseHeight = 40;
            const variation = ((i * 7 + tp * 3 - fp * 2) % 20) - 10;
            const height = Math.max(10, baseHeight + variation + (simulatedReturn > 0 ? i * 2 : -i));
            return (
              <div 
                key={i}
                className={`flex-1 rounded-t ${simulatedReturn >= 0 ? 'bg-green-200' : 'bg-red-200'}`}
                style={{ height: `${height}%` }}
              />
            );
          })}
        </div>
      </div>
    </div>
  );
}


/**
 * Block 34: Error Cluster Analysis Panel
 * Shows failure modes and error patterns
 */
function ErrorClusterPanel({ errorClusters }) {
  if (!errorClusters || errorClusters.totalErrors === 0) {
    return (
      <div className="bg-white rounded-xl border border-gray-200 p-4" data-testid="error-cluster-panel">
        <div className="text-xs font-medium text-gray-500 mb-3">ERROR ANALYSIS</div>
        <div className="text-center py-4 text-sm text-gray-400">
          No errors to analyze yet
        </div>
      </div>
    );
  }
  
  const { byDirection, byConfidence, byDeviation, totalErrors, failureRate } = errorClusters;
  
  // Find dominant failure mode
  const dominantMode = (() => {
    if (byDirection.upErrors > byDirection.downErrors * 2) return 'UP predictions fail more';
    if (byDirection.downErrors > byDirection.upErrors * 2) return 'DOWN predictions fail more';
    if (byConfidence.highConfErrors > byConfidence.lowConfErrors) return 'Overconfident';
    if (byDeviation.overshot > byDeviation.undershot * 2) return 'Targets too conservative';
    if (byDeviation.undershot > byDeviation.overshot * 2) return 'Targets too aggressive';
    return 'No clear pattern';
  })();
  
  return (
    <div className="bg-white rounded-xl border border-gray-200 p-4" data-testid="error-cluster-panel">
      <div className="flex items-center justify-between mb-3">
        <div className="text-xs font-medium text-gray-500">ERROR ANALYSIS</div>
        <div className="text-xs text-gray-400">Block 34</div>
      </div>
      
      {/* Failure Rate */}
      <div className="mb-4 p-2 rounded-lg">
        <div className="flex justify-between items-center">
          <span className="text-sm text-red-700">Failure Rate</span>
          <span className="text-lg font-bold text-red-600">{failureRate}%</span>
        </div>
        <div className="text-xs text-red-500 mt-1">{totalErrors} total errors</div>
      </div>
      
      {/* Dominant Failure Mode */}
      <div className="mb-3 p-2 bg-yellow-50 rounded-lg">
        <div className="text-xs text-yellow-600 mb-1">Primary Issue</div>
        <div className="text-sm font-medium text-yellow-800">{dominantMode}</div>
      </div>
      
      {/* Error Breakdown */}
      <div className="space-y-2 text-sm">
        <div className="flex justify-between">
          <span className="text-gray-500">UP errors</span>
          <span className="font-medium">{byDirection.upErrors}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-gray-500">DOWN errors</span>
          <span className="font-medium">{byDirection.downErrors}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-gray-500">Overshot target</span>
          <span className="font-medium">{byDeviation.overshot}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-gray-500">Undershot target</span>
          <span className="font-medium">{byDeviation.undershot}</span>
        </div>
      </div>
    </div>
  );
}


/**
 * Real-Time Overlay Panel (POLISHED)
 * Shows market context: regime, funding, positioning, risk
 */
function OverlayPanel({ overlay }) {
  if (!overlay) {
    return (
      <div className="prediction-card p-4 animate-fade-in" data-testid="overlay-panel">
        <div className="prediction-card-header">
          <div className="icon-circle icon-circle-gray">
            <Gauge className="w-4 h-4" />
          </div>
          <div className="prediction-card-title">Market Context</div>
          <span className="text-[10px] text-gray-400">Real-time</span>
        </div>
        <div className="text-center py-4">
          <Gauge className="w-5 h-5 text-gray-300 mx-auto mb-2 animate-pulse-soft" />
          <div className="text-xs text-gray-400">Loading market data...</div>
        </div>
      </div>
    );
  }
  
  const regimeConfig = {
    'SQUEEZE': { color: 'text-red-600', bg: '', icon: AlertTriangle },
    'VOLATILE': { color: 'text-amber-600', bg: '', icon: Zap },
    'TREND': { color: 'text-blue-600', bg: '', icon: TrendingUpIcon },
    'RANGE': { color: 'text-gray-600', bg: '', icon: MinusIcon },
  };
  
  const config = regimeConfig[overlay.regime] || regimeConfig['RANGE'];
  const RegimeIcon = config.icon;
  
  const riskColors = {
    'LOW': 'text-emerald-600',
    'MEDIUM': 'text-amber-600',
    'HIGH': 'text-red-600',
  };
  
  return (
    <div className="prediction-card p-4 animate-fade-in" data-testid="overlay-panel">
      <div className="prediction-card-header">
        <div className="icon-circle icon-circle-gray">
          <Gauge className="w-4 h-4" />
        </div>
        <div className="prediction-card-title">Market Context</div>
        <span className="text-[10px] text-emerald-600 font-medium">Live</span>
      </div>
      
      {/* Regime Badge */}
      <div className={`${config.bg} border rounded-xl p-3 mb-3`}>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <RegimeIcon className={`w-4 h-4 ${config.color}`} />
            <span className={`text-sm font-bold ${config.color}`}>{overlay.regime}</span>
          </div>
          <TooltipProvider delayDuration={0}>
            <Tooltip>
              <TooltipTrigger className="text-[10px] text-gray-500 bg-white/60 px-2 py-0.5 rounded-full">
                {Math.round(overlay.regimeConfidence * 100)}%
              </TooltipTrigger>
              <TooltipContent className="tooltip-dark">
                <p className="text-xs">Regime detection confidence</p>
              </TooltipContent>
            </Tooltip>
          </TooltipProvider>
        </div>
        <div className="text-xs text-gray-600 mt-1.5">{overlay.summary}</div>
      </div>
      
      {/* Funding State */}
      <div className="space-y-2.5 mb-3">
        <div className="flex justify-between items-center py-1.5 px-2 rounded-lg hover:bg-gray-50 transition-colors">
          <TooltipProvider delayDuration={0}>
            <Tooltip>
              <TooltipTrigger className="text-sm text-gray-600 flex items-center gap-1.5">
                <div className="w-2 h-2 rounded-full bg-gray-300"></div>
                Funding
              </TooltipTrigger>
              <TooltipContent className="tooltip-dark">
                <p className="text-xs">Perpetual futures funding rate</p>
              </TooltipContent>
            </Tooltip>
          </TooltipProvider>
          <span className={`text-sm font-medium ${
            overlay.funding.state === 'EXTREME' ? 'text-red-600' :
            overlay.funding.state === 'ELEVATED' ? 'text-amber-600' : 'text-gray-700'
          }`}>
            {overlay.funding.rate !== null 
              ? `${(overlay.funding.rate * 100).toFixed(4)}%` 
              : 'N/A'}
            {overlay.funding.state !== 'NORMAL' && (
              <span className="text-[10px] ml-1 opacity-70">({overlay.funding.state})</span>
            )}
          </span>
        </div>
        
        {overlay.positioning.longShortRatio !== null && (
          <div className="flex justify-between items-center py-1.5 px-2 rounded-lg hover:bg-gray-50 transition-colors">
            <TooltipProvider delayDuration={0}>
              <Tooltip>
                <TooltipTrigger className="text-sm text-gray-600 flex items-center gap-1.5">
                  <div className={`w-2 h-2 rounded-full ${
                    overlay.positioning.imbalanceDirection === 'LONG_HEAVY' ? 'bg-emerald-400' :
                    overlay.positioning.imbalanceDirection === 'SHORT_HEAVY' ? 'bg-red-400' : 'bg-gray-300'
                  }`}></div>
                  L/S Ratio
                </TooltipTrigger>
                <TooltipContent className="tooltip-dark">
                  <p className="text-xs">Long to Short position ratio</p>
                </TooltipContent>
              </Tooltip>
            </TooltipProvider>
            <span className={`text-sm font-medium ${
              overlay.positioning.imbalanceDirection === 'LONG_HEAVY' ? 'text-emerald-600' :
              overlay.positioning.imbalanceDirection === 'SHORT_HEAVY' ? 'text-red-600' : 'text-gray-700'
            }`}>
              {Math.round(overlay.positioning.longShortRatio)}% Long
            </span>
          </div>
        )}
      </div>
      
      {/* Risk Level */}
      <div className={`rounded-xl p-3 border ${riskColors[overlay.liquidationRisk] || riskColors['LOW']}`}>
        <div className="flex justify-between items-center">
          <span className="text-sm flex items-center gap-1.5">
            <Shield className="w-3.5 h-3.5" />
            Liquidation Risk
          </span>
          <span className="text-sm font-bold">{overlay.liquidationRisk}</span>
        </div>
      </div>
      
      {/* Confidence Modifier */}
      {overlay.confidenceModifier !== 0 && (
        <div className="mt-3 text-xs text-red-600 flex items-center gap-1.5 rounded-lg px-3 py-2">
          <AlertTriangle className="w-3.5 h-3.5" />
          Confidence adjusted: {(overlay.confidenceModifier * 100).toFixed(0)}%
        </div>
      )}
      
      {/* Warnings */}
      {overlay.warnings && overlay.warnings.length > 0 && (
        <div className="mt-3 pt-3 border-t border-gray-100">
          <div className="text-[10px] font-semibold text-red-600 uppercase tracking-wide mb-2 flex items-center gap-1">
            <AlertTriangle className="w-3 h-3" />
            Warnings
          </div>
          {overlay.warnings.map((w, i) => (
            <div key={i} className="text-xs text-red-500 mb-1 pl-4">{w}</div>
          ))}
        </div>
      )}
    </div>
  );
}


/**
 * VERDICT PANEL (POLISHED)
 * Shows the Verdict Engine decision and all horizon candidates
 */
function VerdictPanel({ verdict, candidates }) {
  if (!verdict) {
    return (
      <div className="prediction-card p-4 animate-fade-in" data-testid="verdict-panel">
        <div className="prediction-card-header">
          <div className="icon-circle icon-circle-blue">
            <Brain className="w-4 h-4" />
          </div>
          <div className="prediction-card-title">Verdict Engine</div>
        </div>
        <div className="text-center py-4">
          <Brain className="w-5 h-5 text-gray-300 mx-auto mb-2 animate-pulse-soft" />
          <div className="text-xs text-gray-400">Loading verdict...</div>
        </div>
      </div>
    );
  }
  
  const actionColors = {
    'BUY': 'text-emerald-600',
    'SELL': 'text-red-500',
    'HOLD': 'text-gray-500',
  };
  
  const riskColors = {
    'LOW': 'text-emerald-600',
    'MEDIUM': 'text-amber-600',
    'HIGH': 'text-red-600',
  };
  
  return (
    <div className="prediction-card p-4 animate-fade-in" data-testid="verdict-panel">
      <div className="prediction-card-header">
        <div className="icon-circle icon-circle-blue">
          <Brain className="w-4 h-4" />
        </div>
        <div className="flex-1">
          <div className="prediction-card-title">Verdict Engine</div>
        </div>
        <div className={`text-xs font-bold ${actionColors[verdict.action]}`}>
          {verdict.action}
        </div>
      </div>
      
      {/* Main Verdict Stats */}
      <div className="grid grid-cols-2 gap-3 mb-4">
        <TooltipProvider delayDuration={0}>
          <Tooltip>
            <TooltipTrigger className="rounded-xl p-3 text-left">
              <div className="text-[10px] text-gray-500 mb-1 uppercase tracking-wide">Confidence</div>
              <div className="metric-value metric-value-lg text-gray-900">
                {(verdict.confidence * 100).toFixed(0)}%
              </div>
            </TooltipTrigger>
            <TooltipContent className="tooltip-dark">
              <p className="text-xs">Model's confidence in this prediction</p>
            </TooltipContent>
          </Tooltip>
        </TooltipProvider>
        <TooltipProvider delayDuration={0}>
          <Tooltip>
            <TooltipTrigger className="rounded-xl p-3 text-left">
              <div className="text-[10px] text-gray-500 mb-1 uppercase tracking-wide">Expected Return</div>
              <div className={`metric-value metric-value-lg ${verdict.expectedReturn >= 0 ? 'text-emerald-600' : 'text-red-500'}`}>
                {verdict.expectedReturn >= 0 ? '+' : ''}{(verdict.expectedReturn * 100).toFixed(2)}%
              </div>
            </TooltipTrigger>
            <TooltipContent className="tooltip-dark">
              <p className="text-xs">Predicted price change for this horizon</p>
            </TooltipContent>
          </Tooltip>
        </TooltipProvider>
      </div>
      
      {/* Risk & Position */}
      <div className="flex justify-between items-center mb-3 py-2 px-3 rounded-xl">
        <div className="flex items-center gap-2">
          <span className="text-xs text-gray-500">Risk:</span>
          <span className={`text-[10px] font-semibold ${riskColors[verdict.risk]}`}>
            {verdict.risk}
          </span>
        </div>
        <TooltipProvider delayDuration={0}>
          <Tooltip>
            <TooltipTrigger className="text-xs">
              <span className="text-gray-500">Position: </span>
              <span className="font-semibold text-gray-700">{verdict.positionSizePct?.toFixed(1) || 0}%</span>
            </TooltipTrigger>
            <TooltipContent className="tooltip-dark">
              <p className="text-xs">Recommended position size based on risk</p>
            </TooltipContent>
          </Tooltip>
        </TooltipProvider>
      </div>
      
      {/* Selected Horizon */}
      <div className="mb-3 p-3 rounded-xl">
        <div className="flex justify-between items-center">
          <span className="text-xs text-gray-500 font-medium">Selected Horizon</span>
          <span className="font-bold text-gray-800 metric-value">{verdict.horizon}</span>
        </div>
        <div className="text-[10px] text-gray-500 mt-1 flex items-center gap-1">
          <Brain className="w-3 h-3" />
          Model: {verdict.modelId}
        </div>
      </div>
      
      {/* Applied Rules */}
      {verdict.appliedRules && verdict.appliedRules.length > 0 && (
        <div className="mb-3">
          <div className="text-xs text-gray-500 mb-2">Applied Rules ({verdict.appliedRules.length})</div>
          <div className="space-y-1">
            {verdict.appliedRules.slice(0, 3).map((rule, idx) => (
              <div key={idx} className={`text-xs ${
                rule.severity === 'BLOCK' ? 'text-red-700' :
                rule.severity === 'WARN' ? 'text-yellow-700' :
                'text-gray-600'
              }`}>
                {rule.id}: {rule.message}
              </div>
            ))}
          </div>
        </div>
      )}
      
      {/* Adjustments */}
      {verdict.adjustments && verdict.adjustments.length > 0 && (
        <div className="mb-3">
          <div className="text-xs text-gray-500 mb-2">Adjustments ({verdict.adjustments.length})</div>
          <div className="space-y-1">
            {verdict.adjustments.slice(0, 3).map((adj, idx) => (
              <div key={idx} className="text-xs flex justify-between">
                <span className="text-gray-600">{adj.stage}: {adj.key}</span>
                {adj.deltaConfidence && (
                  <span className={adj.deltaConfidence < 0 ? 'text-red-500' : 'text-green-500'}>
                    {adj.deltaConfidence < 0 ? '' : '+'}{(adj.deltaConfidence * 100).toFixed(1)}%
                  </span>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
      
      {/* Raw vs Adjusted */}
      {verdict.raw && (
        <div className="pt-3 border-t border-gray-100">
          <div className="text-xs text-gray-400 mb-1">Raw → Adjusted</div>
          <div className="flex justify-between text-xs">
            <span className="text-gray-500">
              Conf: <span className="line-through">{(verdict.raw.confidence * 100).toFixed(0)}%</span> → {(verdict.confidence * 100).toFixed(0)}%
            </span>
            <span className="text-gray-500">
              Ret: <span className="line-through">{(verdict.raw.expectedReturn * 100).toFixed(1)}%</span> → {(verdict.expectedReturn * 100).toFixed(1)}%
            </span>
          </div>
        </div>
      )}
      
      {/* Horizon Candidates */}
      {candidates && candidates.length > 0 && (
        <div className="mt-4 pt-3 border-t border-gray-100">
          <div className="text-xs text-gray-500 mb-2">All Candidates</div>
          <div className="space-y-2">
            {candidates.map((cand, idx) => (
              <div 
                key={idx} 
                className={`flex justify-between items-center text-xs p-2 rounded ${
                  cand.isSelected ? 'border border-blue-200' : ''
                }`}
              >
                <div className="flex items-center gap-2">
                  <span className="font-medium">{cand.horizon}</span>
                  <span className={`text-[10px] font-bold ${
                    cand.action === 'BUY' ? 'text-green-700' :
                    cand.action === 'SELL' ? 'text-red-700' :
                    'text-gray-600'
                  }`}>
                    {cand.action}
                  </span>
                </div>
                <div className="flex items-center gap-3">
                  <span className={cand.expectedReturn >= 0 ? 'text-green-600' : 'text-red-600'}>
                    {cand.expectedReturn >= 0 ? '+' : ''}{(cand.expectedReturn * 100).toFixed(1)}%
                  </span>
                  <span className="text-gray-500">
                    {(cand.confidence * 100).toFixed(0)}%
                  </span>
                  {cand.isSelected && (
                    <span className="text-blue-600 font-bold">✓</span>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}




// ═══════════════════════════════════════════════════════════════
// COMPACT VERSIONS FOR HORIZONTAL LAYOUT (POLISHED)
// ═══════════════════════════════════════════════════════════════

/**
 * Model Health Panel - Compact version with modern styling
 */
function ModelHealthPanelCompact({ metrics }) {
  const hasData = metrics?.evaluatedCount > 0;
  
  const getScoreColor = (score) => {
    if (score >= 70) return 'text-emerald-600';
    if (score >= 50) return 'text-amber-600';
    return 'text-red-500';
  };
  
  const getScoreBg = (score) => {
    if (score >= 70) return '';
    if (score >= 50) return '';
    return '';
  };

  const getProgressColor = (score) => {
    if (score >= 70) return 'progress-bar-green';
    if (score >= 50) return 'progress-bar-amber';
    return 'progress-bar-red';
  };
  
  return (
    <div className="prediction-card p-4 animate-fade-in" data-testid="model-health-compact">
      <div className="prediction-card-header">
        <div className="icon-circle icon-circle-green">
          <ActivityIcon className="w-4 h-4" />
        </div>
        <div className="flex-1">
          <div className="prediction-card-title">Model Health</div>
        </div>
        {hasData && (
          <TooltipProvider delayDuration={0}>
            <Tooltip>
              <TooltipTrigger>
                <div className={`text-xs font-bold border ${getScoreBg(metrics.modelScore)}`}>
                  <span className={getScoreColor(metrics.modelScore)}>{metrics.modelScore}/100</span>
                </div>
              </TooltipTrigger>
              <TooltipContent className="tooltip-dark">
                <p className="text-xs">Overall model quality score</p>
              </TooltipContent>
            </Tooltip>
          </TooltipProvider>
        )}
      </div>
      
      {!hasData ? (
        <div className="text-center py-4">
          <ActivityIcon className="w-5 h-5 text-gray-300 mx-auto mb-2" />
          <div className="text-xs text-gray-400">Collecting data...</div>
        </div>
      ) : (
        <div className="space-y-3">
          <div className="grid grid-cols-2 gap-3">
            <TooltipProvider delayDuration={0}>
              <Tooltip>
                <TooltipTrigger className="text-center p-2 rounded-lg hover:bg-gray-50 transition-colors">
                  <div className={`metric-value metric-value-md ${getScoreColor(metrics.directionMatchPct)}`}>
                    {metrics.directionMatchPct}%
                  </div>
                  <div className="text-[10px] text-gray-400 mt-0.5">Direction</div>
                </TooltipTrigger>
                <TooltipContent className="tooltip-dark">
                  <p className="text-xs">How often the model predicts the correct direction</p>
                </TooltipContent>
              </Tooltip>
            </TooltipProvider>
            <TooltipProvider delayDuration={0}>
              <Tooltip>
                <TooltipTrigger className="text-center p-2 rounded-lg hover:bg-gray-50 transition-colors">
                  <div className={`metric-value metric-value-md ${getScoreColor(metrics.hitRatePct)}`}>
                    {metrics.hitRatePct}%
                  </div>
                  <div className="text-[10px] text-gray-400 mt-0.5">Hit Rate</div>
                </TooltipTrigger>
                <TooltipContent className="tooltip-dark">
                  <p className="text-xs">Percentage of forecasts hitting target price</p>
                </TooltipContent>
              </Tooltip>
            </TooltipProvider>
          </div>
          <div className="flex justify-between text-[11px] text-gray-500 px-1">
            <span>Avg Error: <span className="font-medium text-gray-700">{metrics.avgDeviationPct}%</span></span>
            <span>Calibration: <span className="font-medium text-gray-700">{metrics.calibrationScore || 0}%</span></span>
          </div>
        </div>
      )}
    </div>
  );
}

/**
 * Performance Panel - Compact version with animations
 */
function PerformancePanelCompact({ metrics }) {
  if (!metrics || metrics.evaluatedCount < 3) {
    return (
      <div className="prediction-card p-4 animate-fade-in" data-testid="performance-compact">
        <div className="prediction-card-header">
          <div className="icon-circle icon-circle-blue">
            <LineChart className="w-4 h-4" />
          </div>
          <div className="prediction-card-title">Performance</div>
        </div>
        <div className="text-center py-4">
          <LineChart className="w-5 h-5 text-gray-300 mx-auto mb-2" />
          <div className="text-xs text-gray-400">Need 3+ forecasts</div>
        </div>
      </div>
    );
  }
  
  const credibilityScore = Math.round(
    (metrics.directionMatchPct * 0.5 + metrics.hitRatePct * 0.3 + (metrics.calibrationScore || 0) * 0.2)
  );
  
  const { tp, fp, fn, weak } = metrics.breakdown || { tp: 0, fp: 0, fn: 0, weak: 0 };
  const simulatedReturn = (tp * 3) + (fn * 1) + (weak * 0.5) - (fp * 2);
  const maxDrawdown = fp * 2;
  const sharpeEstimate = metrics.evaluatedCount > 0 
    ? (simulatedReturn / (metrics.avgDeviationPct + 1)).toFixed(1)
    : 0;
  
  const trendUp = metrics.directionMatchPct > 60;
  
  const getCredColor = (score) => {
    if (score >= 60) return 'text-emerald-600';
    if (score >= 40) return 'text-amber-600';
    return 'text-red-500';
  };

  const getProgressColor = (score) => {
    if (score >= 60) return 'progress-bar-green';
    if (score >= 40) return 'progress-bar-amber';
    return 'progress-bar-red';
  };
  
  return (
    <div className="prediction-card p-4 animate-fade-in" data-testid="performance-compact">
      <div className="prediction-card-header">
        <div className="icon-circle icon-circle-blue">
          <LineChart className="w-4 h-4" />
        </div>
        <div className="prediction-card-title">Performance</div>
      </div>
      
      {/* Credibility Score with Progress Bar */}
      <div className="mb-3">
        <div className="flex justify-between items-center mb-1.5">
          <TooltipProvider delayDuration={0}>
            <Tooltip>
              <TooltipTrigger className="text-xs text-gray-500 flex items-center gap-1 hover:text-gray-700 transition-colors">
                Credibility
                <Info className="w-3 h-3" />
              </TooltipTrigger>
              <TooltipContent className="tooltip-dark">
                <p className="text-xs">Combined score of direction accuracy, hit rate, and calibration</p>
              </TooltipContent>
            </Tooltip>
          </TooltipProvider>
          <span className={`metric-value text-sm font-bold ${getCredColor(credibilityScore)}`}>
            {credibilityScore}%
            <span className="text-[10px] ml-0.5">{trendUp ? '↑' : '↓'}</span>
          </span>
        </div>
        <div className="progress-bar-container">
          <div 
            className={`progress-bar-fill ${getProgressColor(credibilityScore)}`}
            style={{ width: `${credibilityScore}%` }}
          />
        </div>
      </div>
      
      {/* Stats Row */}
      <div className="flex justify-between text-[11px] mb-3">
        <TooltipProvider delayDuration={0}>
          <Tooltip>
            <TooltipTrigger className={`font-medium ${simulatedReturn >= 0 ? 'text-emerald-600' : 'text-red-500'}`}>
              {simulatedReturn >= 0 ? '+' : ''}{simulatedReturn.toFixed(1)}%
            </TooltipTrigger>
            <TooltipContent className="tooltip-dark">
              <p className="text-xs">Simulated return based on outcomes</p>
            </TooltipContent>
          </Tooltip>
        </TooltipProvider>
        <TooltipProvider delayDuration={0}>
          <Tooltip>
            <TooltipTrigger className="text-red-400 font-medium">
              -{maxDrawdown.toFixed(1)}%
            </TooltipTrigger>
            <TooltipContent className="tooltip-dark">
              <p className="text-xs">Maximum drawdown</p>
            </TooltipContent>
          </Tooltip>
        </TooltipProvider>
        <TooltipProvider delayDuration={0}>
          <Tooltip>
            <TooltipTrigger className={`font-medium ${parseFloat(sharpeEstimate) >= 1 ? 'text-emerald-600' : 'text-amber-600'}`}>
              SR: {sharpeEstimate}
            </TooltipTrigger>
            <TooltipContent className="tooltip-dark">
              <p className="text-xs">Sharpe Ratio estimate</p>
            </TooltipContent>
          </Tooltip>
        </TooltipProvider>
      </div>
      
      {/* Mini Equity Curve with animation */}
      <div className="flex items-end gap-0.5 h-7">
        {[...Array(8)].map((_, i) => {
          const baseHeight = 40;
          const variation = ((i * 7 + tp * 3 - fp * 2) % 20) - 10;
          const height = Math.max(15, baseHeight + variation + (simulatedReturn > 0 ? i * 3 : -i));
          return (
            <div 
              key={i}
              className={`flex-1 rounded-t transition-all duration-500 ${
                simulatedReturn >= 0 
                  ? 'bg-emerald-200' 
                  : 'bg-red-200'
              }`}
              style={{ 
                height: `${height}%`,
                animationDelay: `${i * 50}ms`
              }}
            />
          );
        })}
      </div>
    </div>
  );
}

/**
 * Error Cluster Panel - Compact version with visual improvements
 */
function ErrorClusterPanelCompact({ errorClusters }) {
  if (!errorClusters || errorClusters.totalErrors === 0) {
    return (
      <div className="prediction-card p-4 animate-fade-in" data-testid="error-cluster-compact">
        <div className="prediction-card-header">
          <div className="icon-circle icon-circle-orange">
            <AlertTriangle className="w-4 h-4" />
          </div>
          <div className="prediction-card-title">Error Analysis</div>
        </div>
        <div className="text-center py-4">
          <CheckCircleIcon className="w-5 h-5 text-emerald-400 mx-auto mb-2" />
          <div className="text-xs text-gray-400">No errors detected</div>
        </div>
      </div>
    );
  }
  
  const { byDirection, byDeviation, totalErrors, failureRate } = errorClusters;
  
  const dominantMode = (() => {
    if (byDirection?.upErrors > (byDirection?.downErrors || 0) * 2) return { text: 'UP predictions fail more', icon: TrendingUpIcon };
    if (byDirection?.downErrors > (byDirection?.upErrors || 0) * 2) return { text: 'DOWN predictions fail more', icon: TrendingDownIcon };
    if (byDeviation?.overshot > (byDeviation?.undershot || 0) * 2) return { text: 'Targets too conservative', icon: Target };
    if (byDeviation?.undershot > (byDeviation?.overshot || 0) * 2) return { text: 'Targets too aggressive', icon: Zap };
    return { text: 'Mixed pattern', icon: ActivityIcon };
  })();
  
  return (
    <div className="prediction-card p-4 animate-fade-in" data-testid="error-cluster-compact">
      <div className="prediction-card-header">
        <div className="icon-circle icon-circle-orange">
          <AlertTriangle className="w-4 h-4" />
        </div>
        <div className="prediction-card-title">Error Analysis</div>
      </div>
      
      {/* Failure Rate */}
      <div className="flex items-center justify-between mb-3">
        <div className="metric-value metric-value-md text-red-500">{failureRate}%</div>
        <TooltipProvider delayDuration={0}>
          <Tooltip>
            <TooltipTrigger className="text-[10px] text-gray-400 bg-gray-100 px-2 py-0.5 rounded-full">
              {totalErrors} errors
            </TooltipTrigger>
            <TooltipContent className="tooltip-dark">
              <p className="text-xs">Total number of incorrect forecasts</p>
            </TooltipContent>
          </Tooltip>
        </TooltipProvider>
      </div>
      
      {/* Dominant Mode Badge */}
      <div className="flex items-center gap-2 text-xs text-amber-700 rounded-lg px-3 py-2 mb-3">
        <dominantMode.icon className="w-3.5 h-3.5" />
        <span className="font-medium">{dominantMode.text}</span>
      </div>
      
      {/* Quick Stats Grid */}
      <div className="grid grid-cols-2 gap-2 text-[10px]">
        <div className="flex justify-between text-gray-500 rounded px-2 py-1">
          <span>UP errors</span>
          <span className="font-medium text-gray-700">{byDirection?.upErrors || 0}</span>
        </div>
        <div className="flex justify-between text-gray-500 rounded px-2 py-1">
          <span>DOWN errors</span>
          <span className="font-medium text-gray-700">{byDirection?.downErrors || 0}</span>
        </div>
        <div className="flex justify-between text-gray-500 rounded px-2 py-1">
          <span>Overshot</span>
          <span className="font-medium text-gray-700">{byDeviation?.overshot || 0}</span>
        </div>
        <div className="flex justify-between text-gray-500 rounded px-2 py-1">
          <span>Undershot</span>
          <span className="font-medium text-gray-700">{byDeviation?.undershot || 0}</span>
        </div>
      </div>
    </div>
  );
}

/**
 * Outcomes Card - Compact version with visual polish
 */
function OutcomesCardCompact({ metrics }) {
  const breakdown = metrics?.breakdown || { tp: 0, fp: 0, fn: 0, weak: 0 };
  const { tp, fp, fn, weak } = breakdown;
  const total = tp + fp + fn + weak;
  const successRate = total > 0 ? (tp / total) * 100 : 0;
  
  return (
    <div className="prediction-card p-4 animate-fade-in" data-testid="outcomes-compact">
      <div className="prediction-card-header">
        <div className="icon-circle icon-circle-purple">
          <Target className="w-4 h-4" />
        </div>
        <div className="prediction-card-title">Outcomes</div>
      </div>
      
      {total === 0 ? (
        <div className="text-center py-4">
          <Target className="w-5 h-5 text-gray-300 mx-auto mb-2" />
          <div className="text-xs text-gray-400">Awaiting results...</div>
        </div>
      ) : (
        <>
          <div className="grid grid-cols-4 gap-1.5 text-center mb-3">
            <TooltipProvider delayDuration={0}>
              <Tooltip>
                <TooltipTrigger className="p-1.5 rounded-lg transition-colors">
                  <div className="metric-value metric-value-md text-emerald-600">{tp}</div>
                  <div className="text-[9px] text-emerald-500 font-medium">TP</div>
                </TooltipTrigger>
                <TooltipContent className="tooltip-dark">
                  <p className="text-xs">True Positive - Correct prediction, profit made</p>
                </TooltipContent>
              </Tooltip>
            </TooltipProvider>
            <TooltipProvider delayDuration={0}>
              <Tooltip>
                <TooltipTrigger className="p-1.5 rounded-lg transition-colors">
                  <div className="metric-value metric-value-md text-red-500">{fp}</div>
                  <div className="text-[9px] text-red-400 font-medium">FP</div>
                </TooltipTrigger>
                <TooltipContent className="tooltip-dark">
                  <p className="text-xs">False Positive - Wrong prediction, loss occurred</p>
                </TooltipContent>
              </Tooltip>
            </TooltipProvider>
            <TooltipProvider delayDuration={0}>
              <Tooltip>
                <TooltipTrigger className="p-1.5 rounded-lg transition-colors">
                  <div className="metric-value metric-value-md text-amber-600">{fn}</div>
                  <div className="text-[9px] text-amber-500 font-medium">FN</div>
                </TooltipTrigger>
                <TooltipContent className="tooltip-dark">
                  <p className="text-xs">False Negative - Missed opportunity</p>
                </TooltipContent>
              </Tooltip>
            </TooltipProvider>
            <TooltipProvider delayDuration={0}>
              <Tooltip>
                <TooltipTrigger className="p-1.5 rounded-lg hover:bg-gray-50 transition-colors">
                  <div className="metric-value metric-value-md text-gray-500">{weak}</div>
                  <div className="text-[9px] text-gray-400 font-medium">WEAK</div>
                </TooltipTrigger>
                <TooltipContent className="tooltip-dark">
                  <p className="text-xs">Weak signal - Low confidence prediction</p>
                </TooltipContent>
              </Tooltip>
            </TooltipProvider>
          </div>
          
          {/* Success Rate Bar */}
          <div className="progress-bar-container">
            <div 
              className={`progress-bar-fill ${successRate >= 50 ? 'progress-bar-green' : 'progress-bar-amber'}`}
              style={{ width: `${successRate}%` }}
            />
          </div>
          <div className="text-[10px] text-center mt-1.5">
            <span className={`font-semibold ${successRate >= 50 ? 'text-emerald-600' : 'text-amber-600'}`}>
              {Math.round(successRate)}%
            </span>
            <span className="text-gray-400 ml-1">success rate</span>
          </div>
        </>
      )}
    </div>
  );
}
