/**
 * UnifiedResearchChart — PHASE F4.1
 * 
 * Main chart component for Research UI
 * Combines TradingView base with ChartObjectRenderer
 * 
 * Features:
 * - Candles + Volume
 * - Indicators (EMA, SMA, RSI, MACD, etc.)
 * - TA Objects (patterns, levels, zones)
 * - Hypothesis paths + confidence bands
 * - Fractal projections
 * - Layer toggles
 */

import React, { useEffect, useRef, useState, useMemo, useCallback } from 'react';
import { createChart, CrosshairMode, CandlestickSeries, LineSeries, HistogramSeries } from 'lightweight-charts';
import { ChartObjectRenderer } from './ChartObjectRenderer';

// ═══════════════════════════════════════════════════════════════
// LAYER CONFIG
// ═══════════════════════════════════════════════════════════════

const LAYER_CONFIG = {
  candles: { label: 'Candles', default: true },
  volume: { label: 'Volume', default: true },
  indicators: { label: 'Indicators', default: true },
  patterns: { label: 'Patterns', default: true },
  levels: { label: 'S/R Levels', default: true },
  liquidity: { label: 'Liquidity', default: true },
  hypothesis: { label: 'Hypothesis', default: true },
  fractals: { label: 'Fractals', default: false },
};

// ═══════════════════════════════════════════════════════════════
// COMPONENT
// ═══════════════════════════════════════════════════════════════

export function UnifiedResearchChart({
  // Data from backend
  candles = [],
  volume = [],
  objects = [],
  indicators = [],
  hypothesis = null,
  fractalMatches = [],
  
  // Config
  symbol = 'BTC',
  timeframe = '1D',
  height = 600,
  theme = 'dark',
  
  // Callbacks
  onCrosshairMove = null,
  onSymbolChange = null,
  onTimeframeChange = null,
}) {
  const containerRef = useRef(null);
  const chartRef = useRef(null);
  const candleSeriesRef = useRef(null);
  const volumeSeriesRef = useRef(null);
  const rendererRef = useRef(null);
  
  const [enabledLayers, setEnabledLayers] = useState(() => {
    const initial = {};
    Object.entries(LAYER_CONFIG).forEach(([key, config]) => {
      initial[key] = config.default;
    });
    return initial;
  });
  
  const [tooltipData, setTooltipData] = useState(null);
  const [chartReady, setChartReady] = useState(false);
  
  // Theme palette
  const palette = useMemo(() => {
    return theme === 'dark' ? {
      background: '#0f172a',
      text: 'rgba(241, 245, 249, 0.9)',
      grid: 'rgba(241, 245, 249, 0.06)',
      border: 'rgba(241, 245, 249, 0.12)',
      upColor: '#22c55e',
      downColor: '#ef4444',
      volumeUp: 'rgba(34, 197, 94, 0.35)',
      volumeDown: 'rgba(239, 68, 68, 0.35)',
    } : {
      background: '#ffffff',
      text: 'rgba(15, 23, 42, 0.9)',
      grid: 'rgba(15, 23, 42, 0.06)',
      border: 'rgba(15, 23, 42, 0.12)',
      upColor: '#22c55e',
      downColor: '#ef4444',
      volumeUp: 'rgba(34, 197, 94, 0.35)',
      volumeDown: 'rgba(239, 68, 68, 0.35)',
    };
  }, [theme]);
  
  // ═══════════════════════════════════════════════════════════════
  // CHART INITIALIZATION
  // ═══════════════════════════════════════════════════════════════
  
  useEffect(() => {
    if (!containerRef.current) return;
    
    // Wait for container to have dimensions
    const rect = containerRef.current.getBoundingClientRect();
    if (rect.width === 0) {
      // Retry after layout
      const timer = setTimeout(() => {
        containerRef.current?.dispatchEvent(new Event('resize'));
      }, 100);
      return () => clearTimeout(timer);
    }
    
    const chart = createChart(containerRef.current, {
      width: rect.width,
      height,
      layout: {
        background: { type: 'solid', color: palette.background },
        textColor: palette.text,
        fontFamily: "'Inter', -apple-system, sans-serif",
      },
      grid: {
        vertLines: { color: palette.grid },
        horzLines: { color: palette.grid },
      },
      crosshair: {
        mode: CrosshairMode.Normal,
        vertLine: { color: 'rgba(100, 100, 100, 0.4)', style: 2, width: 1 },
        horzLine: { color: 'rgba(100, 100, 100, 0.4)', style: 2, width: 1 },
      },
      rightPriceScale: {
        borderColor: palette.border,
        scaleMargins: { top: 0.1, bottom: 0.2 },
      },
      timeScale: {
        borderColor: palette.border,
        rightOffset: 20,
        barSpacing: 8,
        timeVisible: true,
        secondsVisible: false,
      },
      handleScroll: { mouseWheel: true, pressedMouseMove: true },
      handleScale: { mouseWheel: true, pinch: true },
    });
    
    // Candlestick series
    const candleSeries = chart.addSeries(CandlestickSeries, {
      upColor: palette.upColor,
      downColor: palette.downColor,
      borderVisible: false,
      wickUpColor: palette.upColor,
      wickDownColor: palette.downColor,
    });
    
    // Volume series
    const volumeSeries = chart.addSeries(HistogramSeries, {
      priceFormat: { type: 'volume' },
      priceScaleId: '',
      scaleMargins: { top: 0.85, bottom: 0 },
    });
    
    // Crosshair handler
    chart.subscribeCrosshairMove((param) => {
      if (!param.time || !param.point) {
        setTooltipData(null);
        return;
      }
      
      const candleData = param.seriesData?.get(candleSeries);
      const volumeData = param.seriesData?.get(volumeSeries);
      
      if (candleData) {
        setTooltipData({
          time: param.time,
          x: param.point.x,
          y: param.point.y,
          open: candleData.open,
          high: candleData.high,
          low: candleData.low,
          close: candleData.close,
          volume: volumeData?.value || 0,
        });
        onCrosshairMove?.({ time: param.time, price: candleData });
      }
    });
    
    chartRef.current = chart;
    candleSeriesRef.current = candleSeries;
    volumeSeriesRef.current = volumeSeries;
    rendererRef.current = new ChartObjectRenderer(chart);
    
    setChartReady(true);
    
    // Resize observer
    const resizeObserver = new ResizeObserver((entries) => {
      // Debounce resize
      window.requestAnimationFrame(() => {
        if (containerRef.current && chartRef.current) {
          const newWidth = containerRef.current.clientWidth;
          if (newWidth > 0) {
            chartRef.current.applyOptions({ width: newWidth });
          }
        }
      });
    });
    resizeObserver.observe(containerRef.current);
    
    return () => {
      resizeObserver.disconnect();
      rendererRef.current?.clearAll();
      chart.remove();
      chartRef.current = null;
      setChartReady(false);
    };
  }, [height, palette]);
  
  // ═══════════════════════════════════════════════════════════════
  // UPDATE CANDLES
  // ═══════════════════════════════════════════════════════════════
  
  useEffect(() => {
    console.log('Candles useEffect:', { 
      chartReady, 
      hasSeries: !!candleSeriesRef.current, 
      candleCount: candles?.length,
      enabledCandles: enabledLayers.candles 
    });
    
    if (!chartReady || !candleSeriesRef.current || !candles?.length || !enabledLayers.candles) return;
    
    // Validate candle data
    const validCandles = candles.filter(c => 
      typeof c.time === 'number' && 
      !isNaN(c.time) && 
      c.time > 0 &&
      typeof c.open === 'number' &&
      typeof c.close === 'number'
    );
    
    console.log('Valid candles:', validCandles.length);
    
    if (validCandles.length === 0) {
      console.warn('No valid candles to display');
      return;
    }
    
    const sorted = [...validCandles].sort((a, b) => a.time - b.time);
    
    try {
      console.log('Setting candle data...', sorted[0], sorted[sorted.length-1]);
      candleSeriesRef.current.setData(sorted);
      
      // Fit content after small delay to ensure rendering
      setTimeout(() => {
        chartRef.current?.timeScale().fitContent();
        // Also auto-scale price axis
        chartRef.current?.priceScale('right')?.applyOptions({
          autoScale: true,
        });
      }, 100);
      
      console.log('Candle data set successfully');
    } catch (e) {
      console.error('Failed to set candle data:', e);
    }
  }, [chartReady, candles, enabledLayers.candles]);
  
  // ═══════════════════════════════════════════════════════════════
  // UPDATE VOLUME
  // ═══════════════════════════════════════════════════════════════
  
  useEffect(() => {
    if (!chartReady || !volumeSeriesRef.current) return;
    
    if (!enabledLayers.volume) {
      volumeSeriesRef.current.setData([]);
      return;
    }
    
    try {
      if (volume?.length) {
        const validVolume = volume.filter(v => 
          typeof v.time === 'number' && !isNaN(v.time) && v.time > 0
        );
        const sorted = [...validVolume].sort((a, b) => a.time - b.time);
        volumeSeriesRef.current.setData(sorted);
      } else if (candles?.length) {
        const volumeData = candles
          .filter(c => typeof c.time === 'number' && !isNaN(c.time) && c.time > 0)
          .map(c => ({
            time: c.time,
            value: c.volume || 0,
            color: c.close >= c.open ? palette.volumeUp : palette.volumeDown,
          }))
          .sort((a, b) => a.time - b.time);
        volumeSeriesRef.current.setData(volumeData);
      }
    } catch (e) {
      console.error('Failed to set volume data:', e);
    }
  }, [chartReady, volume, candles, palette, enabledLayers.volume]);
  
  // ═══════════════════════════════════════════════════════════════
  // UPDATE OBJECTS (Patterns, Levels, Hypothesis, Fractals)
  // ═══════════════════════════════════════════════════════════════
  
  useEffect(() => {
    if (!chartReady || !rendererRef.current) return;
    
    // Clear previous objects
    rendererRef.current.clearAll();
    
    // Filter objects by enabled layers
    const filteredObjects = objects.filter(obj => {
      const category = obj.category;
      const type = obj.type;
      
      // Geometry patterns (triangle, channel, wedge, flag, pennant)
      if (category === 'geometry' && !enabledLayers.patterns) return false;
      // Legacy pattern category
      if (category === 'pattern' && !enabledLayers.patterns) return false;
      
      // S/R levels: resistance_cluster, support_cluster, breakout_zone
      if (category === 'liquidity' && (type === 'resistance_cluster' || type === 'support_cluster' || type === 'breakout_zone') && !enabledLayers.levels) return false;
      // Liquidity zones
      if (category === 'liquidity' && type === 'liquidity_zone' && !enabledLayers.liquidity) return false;
      
      if (category === 'hypothesis' && !enabledLayers.hypothesis) return false;
      if (category === 'fractal' && !enabledLayers.fractals) return false;
      if (category === 'indicator' && !enabledLayers.indicators) return false;
      
      return true;
    });
    
    // Render filtered objects
    rendererRef.current.renderObjects(filteredObjects, {
      sortByPriority: true,
      maxObjects: 100,
    });
    
    // Render indicators separately
    if (enabledLayers.indicators && indicators?.length) {
      indicators.forEach(ind => {
        rendererRef.current.renderObject(ind);
      });
    }
    
  }, [chartReady, objects, indicators, enabledLayers]);
  
  // ═══════════════════════════════════════════════════════════════
  // TOGGLE LAYER
  // ═══════════════════════════════════════════════════════════════
  
  const toggleLayer = useCallback((layerKey) => {
    setEnabledLayers(prev => ({
      ...prev,
      [layerKey]: !prev[layerKey],
    }));
  }, []);
  
  // ═══════════════════════════════════════════════════════════════
  // RENDER
  // ═══════════════════════════════════════════════════════════════
  
  return (
    <div className="unified-research-chart" data-testid="unified-research-chart" style={{ overflow: 'hidden' }}>
      {/* Controls Bar */}
      <div className="flex items-center justify-between px-4 py-2 bg-slate-800/50 border-b border-slate-700">
        {/* Symbol & Timeframe */}
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2">
            <span className="text-lg font-bold text-white">{symbol}</span>
            <span className="text-sm text-slate-400">/USDT</span>
          </div>
          
          <div className="flex items-center gap-1">
            {['1H', '4H', '1D', '1W'].map(tf => (
              <button
                key={tf}
                data-testid={`timeframe-${tf}`}
                onClick={() => onTimeframeChange?.(tf)}
                className={`px-2 py-1 text-xs rounded ${
                  timeframe === tf 
                    ? 'bg-blue-500 text-white' 
                    : 'bg-slate-700 text-slate-300 hover:bg-slate-600'
                }`}
              >
                {tf}
              </button>
            ))}
          </div>
        </div>
        
        {/* Layer Toggles */}
        <div className="flex items-center gap-2">
          {Object.entries(LAYER_CONFIG).map(([key, config]) => (
            <button
              key={key}
              data-testid={`layer-toggle-${key}`}
              onClick={() => toggleLayer(key)}
              className={`px-2 py-1 text-xs rounded transition-colors ${
                enabledLayers[key]
                  ? 'bg-blue-500/20 text-blue-400 border border-blue-500/50'
                  : 'bg-slate-700/50 text-slate-400 border border-slate-600'
              }`}
            >
              {config.label}
            </button>
          ))}
        </div>
      </div>
      
      {/* Chart Container */}
      <div 
        ref={containerRef} 
        className="chart-container w-full"
        style={{ height: `${height}px` }}
      />
      
      {/* Tooltip */}
      {tooltipData && (
        <div 
          className="absolute pointer-events-none bg-slate-800/90 border border-slate-600 rounded-lg p-2 text-xs"
          style={{ 
            left: tooltipData.x + 20, 
            top: tooltipData.y - 60,
            zIndex: 100,
          }}
        >
          <div className="grid grid-cols-2 gap-x-3 gap-y-1">
            <span className="text-slate-400">O:</span>
            <span className="text-white">{tooltipData.open?.toFixed(2)}</span>
            <span className="text-slate-400">H:</span>
            <span className="text-white">{tooltipData.high?.toFixed(2)}</span>
            <span className="text-slate-400">L:</span>
            <span className="text-white">{tooltipData.low?.toFixed(2)}</span>
            <span className="text-slate-400">C:</span>
            <span className="text-white">{tooltipData.close?.toFixed(2)}</span>
            <span className="text-slate-400">V:</span>
            <span className="text-white">{formatVolume(tooltipData.volume)}</span>
          </div>
        </div>
      )}
      
      {/* Hypothesis Summary (if available) */}
      {hypothesis && enabledLayers.hypothesis && (
        <div className="absolute bottom-4 right-4 bg-slate-800/90 border border-slate-600 rounded-lg p-3 text-xs max-w-xs">
          <div className="flex items-center gap-2 mb-2">
            <span className={`w-2 h-2 rounded-full ${
              hypothesis.direction === 'bullish' ? 'bg-green-500' :
              hypothesis.direction === 'bearish' ? 'bg-red-500' : 'bg-slate-400'
            }`} />
            <span className="text-white font-medium capitalize">
              {hypothesis.direction || 'Neutral'}
            </span>
            <span className="text-slate-400">
              {((hypothesis.confidence || 0) * 100).toFixed(0)}% confidence
            </span>
          </div>
          
          {hypothesis.scenarios?.slice(0, 3).map((scenario, i) => {
            const targetPct = scenario.target_pct ?? (
              hypothesis.current_price && scenario.target_price
                ? (scenario.target_price - hypothesis.current_price) / hypothesis.current_price
                : null
            );
            return (
              <div key={i} className="flex items-center justify-between py-1 border-t border-slate-700">
                <span className="text-slate-300 capitalize">{scenario.type}</span>
                <span className={targetPct > 0 ? 'text-green-400' : targetPct < 0 ? 'text-red-400' : 'text-slate-400'}>
                  {targetPct !== null ? `${targetPct > 0 ? '+' : ''}${(targetPct * 100).toFixed(1)}%` : '—'}
                </span>
                <span className="text-slate-400">
                  {(scenario.probability * 100).toFixed(0)}%
                </span>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════
// UTILITIES
// ═══════════════════════════════════════════════════════════════

function formatVolume(vol) {
  if (!vol) return '0';
  if (vol >= 1e9) return (vol / 1e9).toFixed(1) + 'B';
  if (vol >= 1e6) return (vol / 1e6).toFixed(1) + 'M';
  if (vol >= 1e3) return (vol / 1e3).toFixed(1) + 'K';
  return vol.toFixed(0);
}

export default UnifiedResearchChart;
