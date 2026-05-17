/**
 * SentimentForecastChart V2 — BLOCK P1.1 + P2 UI
 * ================================================
 * 
 * Displays sentiment-based price forecast using lightweight-charts.
 * NOW USES /api/market/chart/sentiment-v2 with:
 * - URI multipliers
 * - Calibration modifiers
 * - SafeMode visualization
 * - Confidence bands
 * - Adjustment markers
 * - P2: Signal Breakdown component
 * - P2.2: Mini Equity toggle
 * 
 * Replaces the old /api/sentiment/aggregate endpoint.
 */

import React, { useEffect, useRef, useState } from 'react';
import { createTvChart, TV_CANDLE_OPTIONS, setSeriesMarkers } from './tvChartPreset';
import { RefreshCwIcon, BarChart3Icon, TrendingUpIcon, TrendingDownIcon, MinusIcon, ShieldAlert, AlertTriangle, Activity } from 'lucide-react';
import SentimentSignalBreakdown from '../sentiment/SentimentSignalBreakdown';
import SentimentMiniEquityChart from '../sentiment/SentimentMiniEquityChart';

const API_URL = process.env.REACT_APP_BACKEND_URL || '';

function windowKeyToHorizon(windowKey) {
  if (windowKey === '24H' || windowKey === '1D') return '24H';
  if (windowKey === '30D') return '30D';
  return '7D';
}

export default function SentimentForecastChart({
  symbol,
  windowKey,
  height = 360,
  viewMode = 'candle',
}) {
  const containerRef = useRef(null);
  const chartRef = useRef(null);
  const candleSeriesRef = useRef(null);
  const closeLineSeriesRef = useRef(null);
  const targetPriceLineRef = useRef(null);

  const [data, setData] = useState(null);
  const [showVolume, setShowVolume] = useState(false);
  const [chartMode, setChartMode] = useState('price'); // 'price' | 'equity'
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const horizon = windowKeyToHorizon(windowKey);

  // Fetch chart data from V2 API
  useEffect(() => {
    let alive = true;
    setLoading(true);
    setError(null);

    fetch(`${API_URL}/api/market/chart/sentiment-v2?symbol=${symbol}&horizon=${horizon}`)
      .then(r => r.json())
      .then(res => {
        if (!alive) return;
        if (res.ok) {
          setData(res);
        } else {
          setError(res.error || 'Failed to load chart data');
          setData(null);
        }
      })
      .catch(err => {
        if (!alive) return;
        console.error('[SentimentForecastChartV2] Error:', err);
        setError(err.message);
        setData(null);
      })
      .finally(() => {
        if (alive) setLoading(false);
      });

    return () => {
      alive = false;
    };
  }, [symbol, horizon]);

  // Check if we have valid data
  const hasData = data && data.chart && data.chart.candles && data.chart.candles.length > 0;

  // Initialize chart
  useEffect(() => {
    if (!containerRef.current) return;

    // Clean previous chart
    if (chartRef.current) {
      chartRef.current.remove();
      chartRef.current = null;
    }

    const chart = createTvChart(containerRef.current);
    chart.applyOptions({
      width: containerRef.current.clientWidth,
      height,
    });
    chartRef.current = chart;

    // Add candlestick series
    const candleSeries = chart.addCandlestickSeries(TV_CANDLE_OPTIONS);
    candleSeriesRef.current = candleSeries;

    // Add close-price line series (for line viewMode)
    const closeLineSeries = chart.addLineSeries({
      color: '#2563eb',
      lineWidth: 2,
      crosshairMarkerVisible: true,
      lastValueVisible: false,
      priceLineVisible: false,
      visible: false,
    });
    closeLineSeriesRef.current = closeLineSeries;

    // Resize handler
    const handleResize = () => {
      if (!containerRef.current || !chartRef.current) return;
      chartRef.current.applyOptions({
        width: containerRef.current.clientWidth,
        height,
      });
      chartRef.current.timeScale().fitContent();
    };

    window.addEventListener('resize', handleResize);
    handleResize();

    return () => {
      window.removeEventListener('resize', handleResize);
      if (chartRef.current) {
        chartRef.current.remove();
        chartRef.current = null;
      }
    };
  }, [height, hasData]);

  // Update chart data
  useEffect(() => {
    if (!candleSeriesRef.current || !chartRef.current || !data) return;

    const { chart: chartData, forecast, meta, reliability } = data;

    // Set candles
    const isLine = viewMode === 'line';
    if (isLine) {
      candleSeriesRef.current.setData([]);
      if (closeLineSeriesRef.current) {
        closeLineSeriesRef.current.setData(chartData.candles.map(c => ({ time: c.time, value: c.close })));
        closeLineSeriesRef.current.applyOptions({ visible: true });
      }
    } else {
      candleSeriesRef.current.setData(chartData.candles);
      if (closeLineSeriesRef.current) {
        closeLineSeriesRef.current.setData([]);
        closeLineSeriesRef.current.applyOptions({ visible: false });
      }
    }

    // SafeMode visual - no projection line (removed for cleaner chart)

    // Target price line — remove old one first to prevent duplicates
    if (targetPriceLineRef.current) {
      try {
        candleSeriesRef.current.removePriceLine(targetPriceLineRef.current);
      } catch (e) { /* already removed */ }
      targetPriceLineRef.current = null;
    }

    // Target price line
    const formattedTarget = forecast.target.toFixed(2).replace(/\B(?=(\d{3})+(?!\d))/g, ',');
    const targetColor = meta.safeMode 
      ? 'rgba(156, 163, 175, 0.6)'
      : forecast.direction === 'LONG' 
        ? 'rgba(34, 197, 94, 0.6)' 
        : forecast.direction === 'SHORT' 
          ? 'rgba(239, 68, 68, 0.6)' 
          : 'rgba(100, 116, 139, 0.5)';

    targetPriceLineRef.current = candleSeriesRef.current.createPriceLine({
      price: forecast.target,
      color: targetColor,
      lineStyle: 2,
      lineWidth: 1,
      axisLabelVisible: true,
      title: `Target $${formattedTarget}`,
    });

    // Add markers for adjustments
    if (chartData.markers && chartData.markers.length > 0) {
      const markers = chartData.markers.map(m => ({
        time: m.time,
        position: 'aboveBar',
        color: m.type === 'SAFE_MODE' ? '#f59e0b' : '#6366f1',
        shape: 'circle',
        text: m.text,
      }));
      setSeriesMarkers(candleSeriesRef.current, markers);
    }

    // Fit content
    chartRef.current.timeScale().fitContent();
    const barSpacing = horizon === '24H' ? 12 : horizon === '7D' ? 8 : 6;
    chartRef.current.timeScale().applyOptions({ barSpacing });

  }, [data, horizon, viewMode]);

  const getDirectionIcon = () => {
    if (!data) return <MinusIcon className="w-4 h-4 text-gray-400" />;
    if (data.meta.safeMode) return <ShieldAlert className="w-4 h-4 text-amber-500" />;
    if (data.forecast.direction === 'LONG') return <TrendingUpIcon className="w-4 h-4 text-emerald-500" />;
    if (data.forecast.direction === 'SHORT') return <TrendingDownIcon className="w-4 h-4 text-red-500" />;
    return <MinusIcon className="w-4 h-4 text-gray-400" />;
  };

  const getDirectionColor = () => {
    if (!data) return 'text-gray-500';
    if (data.meta.safeMode) return 'text-amber-600';
    if (data.forecast.direction === 'LONG') return 'text-emerald-600';
    if (data.forecast.direction === 'SHORT') return 'text-red-600';
    return 'text-gray-500';
  };

  // Loading state
  if (loading) {
    return (
      <div 
        className="bg-white rounded-xl border border-gray-200 overflow-hidden"
        data-testid="sentiment-forecast-loading"
      >
        <div className="p-4 border-b border-gray-100 flex items-center justify-between">
          <span className="text-sm font-medium text-gray-600">Sentiment</span>
        </div>
        <div style={{ height }} className="flex items-center justify-center">
          <div className="text-sm text-gray-400">Loading...</div>
        </div>
      </div>
    );
  }

  // Error state
  if (error || !hasData) {
    return (
      <div 
        className="bg-white rounded-xl border border-gray-200 overflow-hidden"
        data-testid="sentiment-forecast-error"
      >
        <div className="p-4 border-b border-gray-100 flex items-center justify-between">
          <span className="text-sm font-medium text-gray-600">Sentiment</span>
        </div>
        <div style={{ height }} className="flex items-center justify-center">
          <div className="text-sm text-gray-400">{error || 'No sentiment data available'}</div>
        </div>
      </div>
    );
  }

  const { meta, reliability, forecast } = data;

  return (
    <div 
      className="bg-white rounded-xl border border-gray-200 overflow-hidden"
      data-testid="sentiment-forecast-chart-v2"
    >
      {/* Header — single row, unified style */}
      <div className="px-4 py-3 border-b border-gray-100 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <span className="text-sm font-medium text-gray-600" data-testid="sentiment-chart-title">Sentiment</span>
          {!meta.safeMode && forecast.direction === 'LONG'
            ? <TrendingUpIcon className="w-4 h-4 text-emerald-600" />
            : !meta.safeMode && forecast.direction === 'SHORT'
              ? <TrendingDownIcon className="w-4 h-4 text-red-600" />
              : <MinusIcon className="w-4 h-4 text-gray-400" />
          }
          <span
            className={`text-sm font-bold ${
              !meta.safeMode && forecast.direction === 'LONG'
                ? 'text-emerald-600'
                : !meta.safeMode && forecast.direction === 'SHORT'
                  ? 'text-red-600'
                  : 'text-gray-500'
            }`}
            data-testid="sentiment-chart-stance"
          >
            {!meta.safeMode && forecast.direction === 'LONG' ? 'Bullish'
              : !meta.safeMode && forecast.direction === 'SHORT' ? 'Bearish'
              : 'HOLD'}
          </span>
          <span className="text-sm font-medium text-gray-500" data-testid="sentiment-chart-score">
            {(reliability.rawConfidence * 100).toFixed(0)}%
          </span>
        </div>
        <div className="flex items-center gap-3">
          {/* Price/Equity toggle */}
          <div className="flex items-center bg-gray-100 rounded-lg p-0.5">
            <button
              onClick={() => setChartMode('price')}
              className={`flex items-center gap-1 px-2 py-1 rounded text-xs transition-colors ${
                chartMode === 'price' ? 'bg-white text-gray-700 shadow-sm' : 'text-gray-500 hover:text-gray-700'
              }`}
            >
              <BarChart3Icon className="w-3 h-3" />
              Price
            </button>
            <button
              onClick={() => setChartMode('equity')}
              className={`flex items-center gap-1 px-2 py-1 rounded text-xs transition-colors ${
                chartMode === 'equity' ? 'bg-white text-gray-700 shadow-sm' : 'text-gray-500 hover:text-gray-700'
              }`}
            >
              <Activity className="w-3 h-3" />
              Equity
            </button>
          </div>
        </div>
      </div>

      {/* Chart or Equity */}
      {chartMode === 'price' ? (
        <div ref={containerRef} style={{ height }} />
      ) : (
        <SentimentMiniEquityChart symbol={symbol} period="90d" height={height} />
      )}

      {/* P2: Signal Breakdown */}
      {data.explain && (
        <div className="border-t border-gray-100">
          <SentimentSignalBreakdown explain={data.explain} />
        </div>
      )}

      {/* Footer */}
      <div className="px-4 py-2 border-t border-gray-100 flex items-center justify-between text-xs text-gray-400">
        <span>
          Based on {horizon} sentiment • Confidence: {(reliability.finalConfidence * 100).toFixed(0)}%
        </span>
        <span>
          Window: {horizon} • Current: ${forecast.entry.toLocaleString()}
        </span>
      </div>
    </div>
  );
}
