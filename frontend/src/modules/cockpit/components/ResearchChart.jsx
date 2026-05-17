/**
 * ResearchChart — Technical Analysis Chart (PURE RENDER_PLAN RENDERER)
 * ====================================================================
 * 
 * CRITICAL: This chart renders ONLY from render_plan.
 * NO legacy sources (setupData.*, baseLayer, indicator_result).
 * 
 * render_plan structure (from backend):
 * - structure: { swings, bos, choch }
 * - levels: [{ price, type, strength }]
 * - liquidity: { bsl, ssl, sweeps }
 * - indicators: { overlays, panes }
 * - execution: { status, direction, entries, stop, targets }
 * 
 * Layer priority (Z-INDEX):
 * - EXECUTION (100) → pattern geometry (90) → structure (80) → levels → candles
 */

import React, { useEffect, useRef, useMemo, useState, useCallback } from 'react';
import styled, { keyframes, css } from 'styled-components';
import { createChart, CandlestickSeries, LineSeries, createSeriesMarkers } from 'lightweight-charts';
import { MarketMechanicsRenderer } from '../../../components/chart-engine/MarketMechanicsLayer';
import { renderNarrative } from '../../../components/chart-engine/narrative';
import PatternOverlay from './PatternOverlay';
import FibonacciOverlay from './FibonacciOverlay';
import ExecutionRenderer from './ExecutionRenderer';
import { renderPatternGeometry } from './PatternGeometryRenderer';
import { renderExecutionLayer } from './ExecutionVisualLayer';
import SetupOverlay from './SetupOverlay';
import PatternSVGOverlay, { PatternLegend } from './PatternSVGOverlay';
import InsightPanel from './InsightPanel';
// V4 Pattern Renderer
import { renderPattern, clearPattern } from '../../../chart/renderers/patternRenderer';
// Zoom preferences
import { useChartPreferences } from '../../../hooks/useChartPreferences';

// Timeframe transition animation
const fadeIn = keyframes`
  from {
    opacity: 0;
    transform: scale(0.98);
  }
  to {
    opacity: 1;
    transform: scale(1);
  }
`;

const slideIn = keyframes`
  from {
    opacity: 0;
    transform: translateX(-8px);
  }
  to {
    opacity: 1;
    transform: translateX(0);
  }
`;

const ChartWrapper = styled.div`
  position: relative;
  width: 100%;
  background: #ffffff;
  border-radius: 12px;
  border: 1px solid #e2e8f0;
  overflow: hidden;
  font-family: 'Gilroy', 'Inter', -apple-system, sans-serif;
  
  /* Timeframe transition animation */
  ${({ $isTransitioning }) => $isTransitioning && css`
    animation: ${fadeIn} 0.3s ease-out;
  `}
`;

const ChartContainer = styled.div`
  width: 100%;
  height: ${({ $height }) => $height || 400}px;
`;

// Pivot point markers — small, minimal, secondary layer
const PivotMarkersContainer = styled.div`
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  pointer-events: none;
  overflow: hidden;
`;

const PivotMarker = styled.div`
  position: absolute;
  display: flex;
  flex-direction: column;
  align-items: center;
  transform: translateX(-50%);
  font-family: 'Gilroy', 'Inter', -apple-system, sans-serif;
`;

const PivotDot = styled.div`
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: ${({ $color }) => $color};
  border: 1px solid white;
  box-shadow: 0 1px 2px rgba(0,0,0,0.2);
`;

const PivotLabel = styled.span`
  font-size: 9px;
  font-weight: 700;
  color: ${({ $color }) => $color};
  text-shadow: 0 0 2px white, 0 0 2px white;
  margin-top: ${({ $kind }) => $kind === 'high' ? '-16px' : '2px'};
`;

const BiasOverlay = styled.div`
  position: absolute;
  top: 12px;
  left: 200px;
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 14px;
  background: ${({ $direction }) => 
    $direction === 'bullish' ? '#05A584' : 
    $direction === 'bearish' ? '#ef4444' : 
    '#64748b'};
  color: #ffffff;
  border-radius: 8px;
  font-weight: 700;
  font-size: 13px;
  font-family: 'Gilroy', 'Inter', -apple-system, sans-serif;
  box-shadow: 0 2px 8px rgba(0,0,0,0.15);
  z-index: 10;
  
  .arrow { font-size: 14px; }
  .confidence { font-size: 12px; opacity: 0.9; }
`;

const PatternLabel = styled.div`
  position: absolute;
  top: 12px;
  left: 12px;
  padding: 8px 12px;
  background: rgba(59, 130, 246, 0.95);
  border-radius: 8px;
  font-size: 12px;
  font-weight: 700;
  font-family: 'Gilroy', 'Inter', -apple-system, sans-serif;
  color: #ffffff;
  box-shadow: 0 2px 8px rgba(59, 130, 246, 0.3);
  z-index: 10;
  text-transform: capitalize;
  
  .confidence { margin-left: 8px; opacity: 0.85; }
`;

// NEW: Primary Insight Overlay - the MAIN output on chart
const PrimaryInsightOverlay = styled.div`
  position: absolute;
  top: 16px;
  right: 16px;
  width: 220px;
  padding: 16px;
  background: rgba(15, 23, 42, 0.95);
  backdrop-filter: blur(8px);
  border-radius: 12px;
  border: 1px solid rgba(255, 255, 255, 0.1);
  font-family: 'Gilroy', 'Inter', -apple-system, sans-serif;
  color: #ffffff;
  z-index: 15;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.3);
`;

const InsightTitle = styled.div`
  font-size: 16px;
  font-weight: 800;
  color: #ffffff;
  margin-bottom: 6px;
  display: flex;
  align-items: center;
  gap: 8px;
`;

const InsightDirection = styled.span`
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  border-radius: 6px;
  background: ${props => {
    if (props.$direction === 'bullish') return 'rgba(5, 165, 132, 0.2)';
    if (props.$direction === 'bearish') return 'rgba(239, 68, 68, 0.2)';
    return 'rgba(100, 116, 139, 0.2)';
  }};
  color: ${props => {
    if (props.$direction === 'bullish') return '#05A584';
    if (props.$direction === 'bearish') return '#ef4444';
    return '#94a3b8';
  }};
  font-size: 14px;
`;

const InsightSummary = styled.div`
  font-size: 12px;
  color: #94a3b8;
  line-height: 1.4;
  margin-bottom: 12px;
`;

const InsightMeta = styled.div`
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding-top: 10px;
  border-top: 1px solid rgba(255, 255, 255, 0.1);
`;

const InsightConfidence = styled.div`
  font-size: 20px;
  font-weight: 800;
  color: ${props => {
    if (props.$value >= 70) return '#05A584';
    if (props.$value >= 50) return '#f59e0b';
    return '#94a3b8';
  }};
`;

const InsightLabel = styled.span`
  font-size: 10px;
  font-weight: 600;
  color: #64748b;
  text-transform: uppercase;
  letter-spacing: 0.5px;
`;

// ═══════════════════════════════════════════════════════════════
// HELPER FUNCTIONS — Calculate indicators from candles
// ═══════════════════════════════════════════════════════════════

/**
 * Calculate Exponential Moving Average
 * @param {Array} candles - Array of candle objects with close price
 * @param {number} period - EMA period (e.g., 20, 50, 200)
 * @returns {Array} Array of {time, value} objects
 */
function calculateEMA(candles, period) {
  if (!candles?.length || period < 1) return [];
  
  const k = 2 / (period + 1);
  const ema = [];
  let prev = candles[0].close;
  
  candles.forEach((c, i) => {
    if (i < period - 1) {
      // Use SMA for first period-1 values
      const slice = candles.slice(0, i + 1);
      const sma = slice.reduce((sum, x) => sum + x.close, 0) / slice.length;
      ema.push({ time: c.time, value: sma });
      prev = sma;
    } else {
      const val = c.close * k + prev * (1 - k);
      ema.push({ time: c.time, value: val });
      prev = val;
    }
  });
  
  return ema;
}

/**
 * Normalize price to 0-100 scale for rendering
 */
function normalize(price, candles) {
  if (!candles?.length) return 0;
  const all = candles.flatMap(c => [c.high, c.low]);
  const min = Math.min(...all);
  const max = Math.max(...all);
  if (max === min) return 50;
  return ((price - min) / (max - min)) * 100;
}

const COLORS = {
  bullish: '#05A584',
  bearish: '#ef4444',
  support: '#05A584',
  resistance: '#ef4444',
  trigger: '#8b5cf6',
  invalidation: '#f59e0b',
  target: '#3b82f6',
  patternUpper: '#3b82f6',
  patternLower: '#3b82f6',
  trendlineBullish: '#22c55e',
  trendlineBearish: '#f97316',
  channelUpper: '#a78bfa',
  channelLower: '#a78bfa',
  // Structure visualization colors
  pivotHH: '#16a34a',    // Strong green - higher high
  pivotHL: '#4ade80',    // Light green - higher low
  pivotLH: '#f97316',    // Orange - lower high
  pivotLL: '#ef4444',    // Red - lower low
  pivotDefault: '#94a3b8',
  bosUp: '#22c55e',
  bosDown: '#ef4444',
  chochUp: '#22c55e',
  chochDown: '#ef4444',
  // EXECUTION OVERLAY colors
  entryLong: 'rgba(34, 197, 94, 0.25)',     // Green zone for long
  entryShort: 'rgba(239, 68, 68, 0.25)',    // Red zone for short
  stopLoss: '#ef4444',                       // Red line
  targetPrimary: '#22c55e',                  // Green line
  targetSecondary: '#34d399',                // Light green
};

// renderPatternGeometry is imported from './PatternGeometryRenderer'

const ResearchChart = ({
  candles = [],
  // PRIMARY SOURCE: render_plan from backend (single source of truth)
  renderPlan = null,
  // V4 RENDER CONTRACT — for clean TA pattern formations
  data = null,
  // TA MODE — controls layer visibility (Auto/Classic/Smart/Minimal)
  mode = 'auto',
  // TRADE SETUP OVERLAY — Entry/Stop/TP visualization (NEW!)
  tradeSetupOverlay = null,
  // Legacy props (for backward compatibility, will be deprecated)
  pattern = null,
  levels = [],
  setup = null,
  structure = null,
  baseLayer = null,
  structureVisualization = null,
  tradeSetup = null,
  poi = null,
  liquidity = null,
  chochValidation = null,
  displacement = null,
  execution = null,
  chainMap = [],
  chartType = 'candles',
  height = 450, // Comfortable chart height
  showLevels = true,
  showPattern = true,
  showBaseLayer = true,
  showStructure = true,
  showTargets = true,
  showExecutionOverlay = true,
  showMarketMechanics = true,
  showPOI = true,
  showLiquidity = true,
  showSweeps = true,
  showCHOCH = true,
  showNarrative = true,
  decision = null,
  indicatorOverlays = [],
  patternV2 = null,
  // Pattern Geometry - NORMALIZED geometry contract for rendering
  patternGeometry = null,
  fibonacci = null,
  chartStructure = null,
  showFibonacciOverlay = true,
  showPatternOverlay = true,
  // PATTERN VIEW MODE — for isolated pattern display
  patternViewMode = false,
  patternWindow = null,
  // TIMEFRAME — for proper zoom calculation
  timeframe = '4H',
  symbol = 'BTC',
}) => {
  const chartRef = useRef(null);
  const chartInstanceRef = useRef(null);
  const mmRendererRef = useRef(null);
  const narrativeRef = useRef(null);
  
  // CRITICAL: Track if this is the first load to prevent auto-zoom reset
  // После первой загрузки НЕ вызываем fitContent при обновлении данных
  const isFirstLoadRef = useRef(true);
  const userHasZoomedRef = useRef(false);
  
  // Track candles identity for smart updates
  const prevCandlesRef = useRef(null);
  const candlesSeriesRef = useRef(null);
  
  // Timeframe transition animation state
  const [isTransitioning, setIsTransitioning] = useState(false);
  const prevTimeframeRef = useRef(timeframe);
  
  // Chart zoom preferences (P1: save/load user zoom)
  const { 
    getZoomForTimeframe, 
    saveZoomForTimeframe, 
    saveVisibleRange 
  } = useChartPreferences(symbol);
  
  // Trigger animation on timeframe change
  useEffect(() => {
    if (prevTimeframeRef.current !== timeframe) {
      setIsTransitioning(true);
      const timer = setTimeout(() => setIsTransitioning(false), 300);
      prevTimeframeRef.current = timeframe;
      
      // Reset first load flag on timeframe change to apply proper zoom
      isFirstLoadRef.current = true;
      userHasZoomedRef.current = false;
      
      return () => clearTimeout(timer);
    }
  }, [timeframe]);
  
  // Save visible range when user scrolls/zooms
  const handleVisibleRangeChange = useCallback((range) => {
    if (userHasZoomedRef.current && range?.from && range?.to) {
      saveVisibleRange(timeframe, range.from, range.to);
    }
  }, [timeframe, saveVisibleRange]);

  // ═══════════════════════════════════════════════════════════════
  // MODE-BASED LAYER VISIBILITY — Auto/Classic/Smart/Minimal
  // ═══════════════════════════════════════════════════════════════
  const modeShow = useMemo(() => {
    const base = {
      structure: true,
      levels: true,
      liquidity: true,
      indicators: true,
      patterns: true,
      poi: true,
      sweeps: true,
    };
    
    switch (mode) {
      case 'minimal':
        return {
          ...base,
          structure: false,
          liquidity: false,
          indicators: false,
          patterns: false,
          poi: false,
          sweeps: false,
        };
      
      case 'classic':
        return {
          ...base,
          liquidity: false,
          poi: false,
          sweeps: false,
        };
      
      case 'smart':
        return {
          ...base,
          structure: false,
          indicators: false,
          patterns: false,
        };
      
      case 'auto':
      default:
        return base;
    }
  }, [mode]);

  // ═══════════════════════════════════════════════════════════════
  // EXTRACT DATA FROM RENDER_PLAN (PRIMARY) OR LEGACY PROPS (FALLBACK)
  // ═══════════════════════════════════════════════════════════════
  const rpStructure = useMemo(() => renderPlan?.structure || null, [renderPlan]);
  const rpLevels = useMemo(() => renderPlan?.levels || levels, [renderPlan, levels]);
  const rpExecution = useMemo(() => renderPlan?.execution || execution, [renderPlan, execution]);
  const rpLiquidity = useMemo(() => renderPlan?.liquidity || liquidity, [renderPlan, liquidity]);
  const rpIndicators = useMemo(() => renderPlan?.indicators || {}, [renderPlan]);
  
  // Compute EMAs from candles if render_plan doesn't provide indicator data
  const computedEMA20 = useMemo(() => {
    if (rpIndicators?.overlays?.find(o => o.id === 'ema_20')?.data?.length) {
      return rpIndicators.overlays.find(o => o.id === 'ema_20').data;
    }
    return calculateEMA(candles, 20);
  }, [candles, rpIndicators]);
  
  const computedEMA50 = useMemo(() => {
    if (rpIndicators?.overlays?.find(o => o.id === 'ema_50')?.data?.length) {
      return rpIndicators.overlays.find(o => o.id === 'ema_50').data;
    }
    return calculateEMA(candles, 50);
  }, [candles, rpIndicators]);

  // DEBUG: Log data sources
  console.log('[ResearchChart] Data sources:', {
    candlesCount: candles.length,
    hasRenderPlan: !!renderPlan,
    structureSwings: rpStructure?.swings?.length || 0,
    levelsCount: rpLevels?.length || 0,
    executionStatus: rpExecution?.status,
    ema20Points: computedEMA20?.length || 0,
    ema50Points: computedEMA50?.length || 0,
  });

  // State for chart instance (needed for SVG overlay coordinate conversion)
  const [chartInstance, setChartInstance] = useState(null);
  const [priceSeriesInstance, setPriceSeriesInstance] = useState(null);

  useEffect(() => {
    if (!chartRef.current || candles.length === 0) return;

    // Check if candles actually changed (symbol/timeframe change)
    const candlesKey = candles.length > 0 ? `${candles[0]?.time}-${candles[candles.length-1]?.time}-${candles.length}` : '';
    const prevCandlesKey = prevCandlesRef.current;
    
    // If chart exists and candles didn't change fundamentally, don't recreate
    if (chartInstanceRef.current && candlesKey === prevCandlesKey) {
      console.log('[ResearchChart] Skipping chart recreate - candles unchanged');
      return;
    }
    
    prevCandlesRef.current = candlesKey;

    // Reset first load flag when candles change (timeframe switch)
    isFirstLoadRef.current = true;
    userHasZoomedRef.current = false;

    // Cleanup previous Market Mechanics renderer FIRST
    if (mmRendererRef.current) {
      mmRendererRef.current.clear();
      mmRendererRef.current = null;
    }

    // Cleanup chart
    if (chartInstanceRef.current) {
      try {
        chartInstanceRef.current.remove();
      } catch (e) {
        // Chart may already be disposed
      }
      chartInstanceRef.current = null;
    }

    const rect = chartRef.current.getBoundingClientRect();
    
    // Create chart
    const chart = createChart(chartRef.current, {
      width: rect.width,
      height: height,
      layout: {
        background: { type: 'solid', color: '#ffffff' },
        textColor: '#64748b',
        fontFamily: "'Gilroy', -apple-system, BlinkMacSystemFont, sans-serif",
        fontSize: 11,
      },
      grid: {
        vertLines: { color: '#f1f5f9' },
        horzLines: { color: '#f1f5f9' },
      },
      crosshair: {
        mode: 1,
        vertLine: { color: '#94a3b8', style: 2, width: 1 },
        horzLine: { color: '#94a3b8', style: 2, width: 1 },
      },
      rightPriceScale: {
        borderColor: '#e2e8f0',
        scaleMargins: { top: 0.1, bottom: 0.1 },
      },
      timeScale: {
        borderColor: '#e2e8f0',
        timeVisible: true,
        secondsVisible: false,
        rightOffset: 80,
        // Enable drag/scroll for chart navigation
        handleScroll: {
          mouseWheel: true,
          pressedMouseMove: true,
          horzTouchDrag: true,
          vertTouchDrag: false,
        },
        handleScale: {
          mouseWheel: true,
          pinch: true,
          axisPressedMouseMove: true,
        },
      },
    });

    chartInstanceRef.current = chart;
    
    // Save chart instance in state for SVG overlay
    setChartInstance(chart);

    // 1. Add price series (candles/line)
    let priceSeries;
    if (chartType === 'line') {
      priceSeries = chart.addSeries(LineSeries, {
        color: COLORS.bullish,
        lineWidth: 2,
        lastValueVisible: true,
        priceLineVisible: true,
        priceLineWidth: 1,
        priceLineStyle: 2,
      });
    } else {
      priceSeries = chart.addSeries(CandlestickSeries, {
        upColor: COLORS.bullish,
        downColor: COLORS.bearish,
        borderUpColor: COLORS.bullish,
        borderDownColor: COLORS.bearish,
        wickUpColor: COLORS.bullish,
        wickDownColor: COLORS.bearish,
        lastValueVisible: true,
        priceLineVisible: true,
        priceLineWidth: 1,
        priceLineStyle: 2,
      });
    }
    
    // Save priceSeries for SVG overlay coordinate conversion
    setPriceSeriesInstance(priceSeries);

    // Format and set candle data
    const seen = new Set();
    const mapped = candles
      .map(c => ({
        time: c.time,
        open: c.open,
        high: c.high,
        low: c.low,
        close: c.close,
        value: c.close,
      }))
      .filter(c => c.time > 0)
      .sort((a, b) => a.time - b.time)
      .filter(c => {
        if (seen.has(c.time)) return false;
        seen.add(c.time);
        return true;
      });

    priceSeries.setData(mapped);

    // ═══════════════════════════════════════════════════════════════
    // INDICATOR OVERLAYS (EMA, BB, VWAP) — NEW!
    // ═══════════════════════════════════════════════════════════════
    if (indicatorOverlays && indicatorOverlays.length > 0) {
      indicatorOverlays.forEach(indicator => {
        if (!indicator?.data?.length) return;
        
        // Parse and deduplicate data
        const overlayData = indicator.data
          .map(d => ({
            time: d.time > 1e12 ? Math.floor(d.time / 1000) : d.time,
            value: d.value
          }))
          .filter(d => d.time > 0 && d.value !== null && d.value !== undefined)
          .sort((a, b) => a.time - b.time);
        
        const seenOverlay = new Set();
        const dedupedOverlay = overlayData.filter(d => {
          if (seenOverlay.has(d.time)) return false;
          seenOverlay.add(d.time);
          return true;
        });
        
        if (dedupedOverlay.length > 0) {
          // Main line
          const lineSeries = chart.addSeries(LineSeries, {
            color: indicator.color || '#3b82f6',
            lineWidth: indicator.line_width || 1,
            lineStyle: 0,
            priceLineVisible: false,
            lastValueVisible: false,
            crosshairMarkerVisible: false,
          });
          lineSeries.setData(dedupedOverlay);
          
          // Extra lines (BB upper/lower)
          if (indicator.extra_lines) {
            indicator.extra_lines.forEach(extraLine => {
              if (!extraLine?.data?.length) return;
              
              const extraData = extraLine.data
                .map(d => ({
                  time: d.time > 1e12 ? Math.floor(d.time / 1000) : d.time,
                  value: d.value
                }))
                .filter(d => d.time > 0 && d.value !== null)
                .sort((a, b) => a.time - b.time);
              
              const seenExtra = new Set();
              const dedupedExtra = extraData.filter(d => {
                if (seenExtra.has(d.time)) return false;
                seenExtra.add(d.time);
                return true;
              });
              
              if (dedupedExtra.length > 0) {
                const extraSeries = chart.addSeries(LineSeries, {
                  color: extraLine.color || '#8b5cf6',
                  lineWidth: 1,
                  lineStyle: extraLine.style === 'dashed' ? 2 : 0,
                  priceLineVisible: false,
                  lastValueVisible: false,
                  crosshairMarkerVisible: false,
                });
                extraSeries.setData(dedupedExtra);
              }
            });
          }
        }
      });
    }

    // ═══════════════════════════════════════════════════════════════
    // PRICE ACTION STRUCTURE — Foundation Layer (ALWAYS ON TOP)
    // ═══════════════════════════════════════════════════════════════
    // Swings → Legs → HH/HL/LH/LL → BOS/CHOCH
    // This IS technical analysis. Chart = structure.
    
    // Use render_plan structure if available, else fallback to chartStructure
    const effectiveStructure = rpStructure || chartStructure;
    
    if (effectiveStructure) {
      // STRUCTURE = SUBDUED (secondary to candles — 50% opacity)
      // Candles are the PRIMARY visual element
      const STRUCT_COLORS = {
        bullishLeg: 'rgba(34, 197, 94, 0.5)',   // Green 50% opacity
        bearishLeg: 'rgba(239, 68, 68, 0.5)',   // Red 50% opacity
        HH: 'rgba(22, 163, 74, 0.7)', HL: 'rgba(74, 222, 128, 0.7)',
        LH: 'rgba(249, 115, 22, 0.7)', LL: 'rgba(220, 38, 38, 0.7)',
        BOS_bull: 'rgba(34, 197, 94, 0.6)', BOS_bear: 'rgba(239, 68, 68, 0.6)',
        CHOCH_bull: 'rgba(59, 130, 246, 0.6)', CHOCH_bear: 'rgba(249, 115, 22, 0.6)',
      };

      // ═══════════════════════════════════════════════════════════════
      // 1. BUILD LEGS FROM SWINGS (CRITICAL FIX!)
      // ═══════════════════════════════════════════════════════════════
      // If legs not provided, build them automatically from swings
      let swings = effectiveStructure.swings || effectiveStructure.labels || [];
      let legs = effectiveStructure.legs || [];
      
      // Sort swings by time FIRST (critical for proper leg building)
      swings = [...swings].sort((a, b) => {
        const timeA = a.time > 1e12 ? Math.floor(a.time / 1000) : a.time;
        const timeB = b.time > 1e12 ? Math.floor(b.time / 1000) : b.time;
        return timeA - timeB;
      });
      
      // AUTO-BUILD LEGS: Connect consecutive swings with lines
      if (legs.length === 0 && swings.length >= 2) {
        console.log('[ResearchChart] Building legs from swings:', swings.length);
        for (let i = 0; i < swings.length - 1; i++) {
          const from = swings[i];
          const to = swings[i + 1];
          if (!from || !to) continue;
          
          // Determine leg type: bullish (going up) or bearish (going down)
          const fromPrice = from.price || from.value;
          const toPrice = to.price || to.value;
          const legType = toPrice > fromPrice ? 'bullish_leg' : 'bearish_leg';
          
          legs.push({
            from: { time: from.time, price: fromPrice },
            to: { time: to.time, price: toPrice },
            type: legType,
          });
        }
      }
      
      // Render structure legs (lines between swings)
      legs.forEach(leg => {
        if (!leg.from?.time || !leg.to?.time) return;
        const fromTime = leg.from.time > 1e12 ? Math.floor(leg.from.time / 1000) : leg.from.time;
        const toTime = leg.to.time > 1e12 ? Math.floor(leg.to.time / 1000) : leg.to.time;
        const fromPrice = leg.from.price || leg.from.value;
        const toPrice = leg.to.price || leg.to.value;
        const color = leg.type === 'bullish_leg' ? STRUCT_COLORS.bullishLeg : STRUCT_COLORS.bearishLeg;

        // Ensure data is sorted by time (lightweight-charts requirement)
        const legData = [
          { time: fromTime, value: fromPrice },
          { time: toTime, value: toPrice },
        ].sort((a, b) => a.time - b.time);

        // Skip if times are same or invalid
        if (legData[0].time === legData[1].time || legData[0].time <= 0 || legData[1].time <= 0) {
          console.warn('[ResearchChart] Skipping leg with invalid times:', legData);
          return;
        }

        try {
          const legSeries = chart.addSeries(LineSeries, {
            color: color,
            lineWidth: 1.5, // THINNER: subdued structure (was 3)
            lineStyle: 0, // Solid
            priceLineVisible: false,
            lastValueVisible: false,
            crosshairMarkerVisible: false,
          });
          legSeries.setData(legData);
          console.log('[ResearchChart] Leg rendered:', legData);
        } catch (e) {
          console.warn('[ResearchChart] Leg render failed:', e.message);
        }
      });

      // 2. HH/HL/LH/LL LABELS + BOS/CHOCH — native markers on price series
      const structMarkers = [];
      const breakTimes = new Set();

      // Get breaks from structure (bos, choch) or fallback breaks array
      const breaks = effectiveStructure.breaks || [];
      
      // Add BOS from render_plan structure
      if (effectiveStructure.bos && effectiveStructure.bos.time) {
        breaks.push({
          time: effectiveStructure.bos.time,
          level: effectiveStructure.bos.price,
          type: 'BOS',
          direction: effectiveStructure.bos.direction,
        });
      }
      
      // Add CHOCH from render_plan structure
      if (effectiveStructure.choch && effectiveStructure.choch.time) {
        breaks.push({
          time: effectiveStructure.choch.time,
          level: effectiveStructure.choch.price,
          type: 'CHOCH',
          direction: effectiveStructure.choch.direction,
        });
      }

      // BOS/CHOCH breaks — horizontal level + marker
      breaks.forEach(brk => {
        if (!brk.time) return;
        const brkTime = brk.time > 1e12 ? Math.floor(brk.time / 1000) : brk.time;
        breakTimes.add(brkTime);

        const isBullish = brk.direction === 'bullish';
        const isCHOCH = brk.type === 'CHOCH' || brk.type === 'choch';
        const color = isCHOCH
          ? (isBullish ? STRUCT_COLORS.CHOCH_bull : STRUCT_COLORS.CHOCH_bear)
          : (isBullish ? STRUCT_COLORS.BOS_bull : STRUCT_COLORS.BOS_bear);
        const labelText = `${brk.type?.toUpperCase()} ${isBullish ? '↑' : '↓'}`;

        structMarkers.push({
          time: brkTime,
          position: isBullish ? 'aboveBar' : 'belowBar',
          color: color,
          shape: isBullish ? 'arrowUp' : 'arrowDown',
          text: labelText,
        });

        // Horizontal break level line — SUBDUED
        if (brk.level) {
          try {
            const levelSeries = chart.addSeries(LineSeries, {
              color: color,
              lineWidth: 1, // THINNER (was 2)
              lineStyle: 2, // dashed
              priceLineVisible: false,
              lastValueVisible: true,
              crosshairMarkerVisible: false,
            });

            // Extend the break level from the break point to the right edge
            const lastCandleTime = mapped.length > 0 ? mapped[mapped.length - 1].time : brkTime;
            levelSeries.setData([
              { time: brkTime, value: brk.level },
              { time: lastCandleTime, value: brk.level },
            ]);
          } catch (e) {
            console.warn('[ResearchChart] Break level render failed:', e);
          }
        }
      });

      // 3. SWING LABELS (HH/HL/LH/LL) — from swings array
      swings.forEach(swing => {
        if (!swing.time) return;
        const swingTime = swing.time > 1e12 ? Math.floor(swing.time / 1000) : swing.time;
        if (breakTimes.has(swingTime)) return; // BOS/CHOCH takes priority

        const label = swing.type || swing.label || 'H';
        const isHigh = label.includes('H') && !label.includes('L');
        const colorMap = {
          HH: STRUCT_COLORS.HH, HL: STRUCT_COLORS.HL,
          LH: STRUCT_COLORS.LH, LL: STRUCT_COLORS.LL,
          H: '#94a3b8', L: '#94a3b8',
        };

        structMarkers.push({
          time: swingTime,
          position: isHigh ? 'aboveBar' : 'belowBar',
          color: colorMap[label] || '#94a3b8',
          shape: 'circle',
          text: label,
        });
      });

      // Sort markers by time (required by lightweight-charts)
      structMarkers.sort((a, b) => a.time - b.time);
      if (structMarkers.length > 0) {
        createSeriesMarkers(priceSeries, structMarkers);
      }
    }

    // ═══════════════════════════════════════════════════════════════
    // MARKET MECHANICS LAYER (POI, Liquidity, Sweeps, CHOCH, Displacement)
    // ═══════════════════════════════════════════════════════════════
    if (showMarketMechanics && (poi || liquidity || chochValidation || displacement)) {
      // Clean up previous renderer
      if (mmRendererRef.current) {
        mmRendererRef.current.clear();
      }
      
      // Create new renderer
      const mmRenderer = new MarketMechanicsRenderer(chart, priceSeries);
      mmRenderer.render(
        { poi, liquidity, chochValidation, displacement, candles: mapped },
        { 
          showPOI, 
          showLiquidity, 
          showSweeps, 
          showCHOCH,
          maxPOIZones: 5,       // Show more POI zones
          maxLiquidityLines: 6, // Show more liquidity lines
          maxSweeps: 3,         // Show sweeps
        }
      );
      mmRendererRef.current = mmRenderer;
    }

    // ═══════════════════════════════════════════════════════════════
    // NARRATIVE LAYER — Market Story
    // ═══════════════════════════════════════════════════════════════
    if (showNarrative && (liquidity || displacement || chochValidation || poi)) {
      try {
        const narrativeData = {
          liquidity,
          displacement,
          chochValidation,
          poi,
          decision,
          tradeSetup,
        };
        
        narrativeRef.current = renderNarrative(chart, priceSeries, narrativeData, candles);
        
        // Log narrative summary for debugging
        if (narrativeRef.current?.summary) {
          console.log('[Narrative]', narrativeRef.current.summary.chain);
        }
      } catch (e) {
        console.warn('Narrative render failed:', e);
      }
    }

    // 2. RENDER STRUCTURE MARKERS (LEGACY — only if no chartStructure)
    // NOTE: Disabled when chartStructure is present (new engine handles it)
    if (showStructure && structureVisualization && !showMarketMechanics && !chartStructure) {
      const markers = [];
      const eventTimes = new Set();

      // Events (CHOCH/BOS) take priority over pivot labels
      (structureVisualization.events || []).forEach(event => {
        eventTimes.add(event.time);
        const isUp = event.direction === 'up';
        markers.push({
          time: event.time,
          position: isUp ? 'aboveBar' : 'belowBar',
          color: isUp ? COLORS.chochUp : COLORS.chochDown,
          shape: isUp ? 'arrowUp' : 'arrowDown',
          text: event.label,
        });
      });

      // Pivot points — skip if pattern overlay is shown (to avoid duplication)
      // Also skip if event already placed at same time
      const hasPatternRenderContract = !!data?.pattern_render_contract;
      if (!hasPatternRenderContract) {
        (structureVisualization.pivot_points || []).forEach(pivot => {
          if (eventTimes.has(pivot.time)) return;
          const isHigh = pivot.kind === 'high';
          const colorMap = { HH: COLORS.pivotHH, HL: COLORS.pivotHL, LH: COLORS.pivotLH, LL: COLORS.pivotLL };
          markers.push({
            time: pivot.time,
            position: isHigh ? 'aboveBar' : 'belowBar',
            color: colorMap[pivot.label] || COLORS.pivotDefault,
            shape: 'circle',
            text: pivot.label,
          });
        });
      }

      // lightweight-charts requires markers sorted by time
      markers.sort((a, b) => a.time - b.time);
      if (markers.length > 0) {
        createSeriesMarkers(priceSeries, markers);
      }
    }

    // 3. RENDER PATTERN GEOMETRY (channel/triangle lines)
    // RULE: Render EXACTLY 2 points per line, no broken segments
    console.log('[ResearchChart] Pattern render check:', {
      showPattern,
      hasPattern: !!pattern,
      hasPoints: !!pattern?.points,
      patternType: pattern?.type,
    });
    
    if (showPattern && pattern?.points) {
      const { upper, lower, mid } = pattern.points;
      const patternType = (pattern.type || '').toLowerCase();
      const isRange = patternType.includes('range');
      
      console.log('[ResearchChart] Rendering pattern lines:', {
        hasUpper: !!upper,
        hasLower: !!lower,
        upperLength: upper?.length,
        lowerLength: lower?.length,
        isRange,
      });
      
      // Helper to parse point (handles both array [time, value] and object {time, value})
      const parsePoint = (pt) => {
        if (Array.isArray(pt)) {
          return {
            time: typeof pt[0] === 'number' ? pt[0] : parseInt(pt[0]),
            value: typeof pt[1] === 'number' ? pt[1] : parseFloat(pt[1]),
          };
        } else if (pt && typeof pt === 'object') {
          return {
            time: typeof pt.time === 'number' ? pt.time : parseInt(pt.time),
            value: typeof pt.value === 'number' ? pt.value : parseFloat(pt.value),
          };
        }
        return null;
      };
      
      // FOR RANGE PATTERNS: Use price lines (horizontal across entire chart)
      // This is the correct way to render range boundaries
      if (isRange && pattern.is_active) {
        const upperPrice = parsePoint(upper?.[0])?.value;
        const lowerPrice = parsePoint(lower?.[0])?.value;
        const midPrice = mid ? parsePoint(mid[0])?.value : null;
        
        console.log('[ResearchChart] Range pattern - creating price lines:', {
          upperPrice,
          lowerPrice,
          midPrice,
        });
        
        // Upper boundary (resistance)
        if (upperPrice && upperPrice > 0) {
          priceSeries.createPriceLine({
            price: upperPrice,
            color: '#ef4444',  // Red for resistance
            lineWidth: 2,
            lineStyle: 0, // Solid
            axisLabelVisible: true,
            title: 'RANGE HIGH',
          });
        }
        
        // Lower boundary (support)
        if (lowerPrice && lowerPrice > 0) {
          priceSeries.createPriceLine({
            price: lowerPrice,
            color: '#22c55e',  // Green for support
            lineWidth: 2,
            lineStyle: 0, // Solid
            axisLabelVisible: true,
            title: 'RANGE LOW',
          });
        }
        
        // Mid line (optional, dashed)
        if (midPrice && midPrice > 0) {
          priceSeries.createPriceLine({
            price: midPrice,
            color: '#9ca3af',  // Gray
            lineWidth: 1,
            lineStyle: 2, // Dashed
            axisLabelVisible: false,
            title: '',
          });
        }
      } else {
        // FOR NON-RANGE PATTERNS: Use line series as before
        // Upper trendline - EXACTLY 2 points
        if (upper && upper.length >= 2) {
          const upperSeries = chart.addSeries(LineSeries, {
            color: COLORS.patternUpper,
            lineWidth: 3,
            lineStyle: 0,
            priceLineVisible: false,
            lastValueVisible: false,
            crosshairMarkerVisible: false,
          });
          
          const p1 = parsePoint(upper[0]);
          const p2 = parsePoint(upper[upper.length > 1 ? 1 : 0]);
          
          if (p1 && p2 && p1.time > 0 && p2.time > 0 && p1.value > 0 && p2.value > 0) {
            const upperData = [p1, p2].sort((a, b) => a.time - b.time);
            upperSeries.setData(upperData);
          }
        }
        
        // Lower trendline - EXACTLY 2 points
        if (lower && lower.length >= 2) {
          const lowerSeries = chart.addSeries(LineSeries, {
            color: COLORS.patternLower,
            lineWidth: 3,
            lineStyle: 0,
            priceLineVisible: false,
            lastValueVisible: false,
            crosshairMarkerVisible: false,
          });
          
          const p1 = parsePoint(lower[0]);
          const p2 = parsePoint(lower[lower.length > 1 ? 1 : 0]);
          
          if (p1 && p2 && p1.time > 0 && p2.time > 0 && p1.value > 0 && p2.value > 0) {
            const lowerData = [p1, p2].sort((a, b) => a.time - b.time);
            lowerSeries.setData(lowerData);
          }
        }
      }
    }

    // ═══════════════════════════════════════════════════════════════
    // PATTERN V2 GEOMETRY — Production Pattern Lines
    // Skip if SVG overlay is active (to avoid duplication)
    // ═══════════════════════════════════════════════════════════════
    if (patternV2?.primary_pattern?.lines?.length > 0 && !hasPatternOverlay) {
      const primary = patternV2.primary_pattern;
      const patternColor = primary.direction_bias === 'bullish' ? '#22c55e' : 
                          primary.direction_bias === 'bearish' ? '#ef4444' : '#8b5cf6';
      
      // Helper to parse time
      const parseTime = (t) => t > 1e12 ? Math.floor(t / 1000) : t;
      
      primary.lines.forEach((line, idx) => {
        if (!line.points || line.points.length < 2) return;
        
        // Build line data
        const lineData = line.points
          .map(pt => ({
            time: parseTime(pt.time),
            value: pt.value
          }))
          .filter(pt => pt.time > 0 && pt.value > 0)
          .sort((a, b) => a.time - b.time);
        
        // Deduplicate by time
        const seen = new Set();
        const dedupedLine = lineData.filter(pt => {
          if (seen.has(pt.time)) return false;
          seen.add(pt.time);
          return true;
        });
        
        if (dedupedLine.length >= 2) {
          const lineSeries = chart.addSeries(LineSeries, {
            color: line.name === 'neckline' ? '#f59e0b' : patternColor,
            lineWidth: line.name === 'neckline' ? 2 : 2,
            lineStyle: line.name === 'neckline' ? 2 : 0, // dashed for neckline
            priceLineVisible: false,
            lastValueVisible: false,
            crosshairMarkerVisible: false,
          });
          lineSeries.setData(dedupedLine);
        }
      });
      
      // Add breakout level as dashed line
      if (primary.breakout_level && mapped.length > 0) {
        const lastTime = mapped[mapped.length - 1].time;
        const firstTime = mapped[Math.max(0, mapped.length - 50)].time;
        
        const breakoutSeries = chart.addSeries(LineSeries, {
          color: patternColor,
          lineWidth: 1,
          lineStyle: 2, // dashed
          priceLineVisible: false,
          lastValueVisible: true,
          crosshairMarkerVisible: false,
        });
        breakoutSeries.setData([
          { time: firstTime, value: primary.breakout_level },
          { time: lastTime, value: primary.breakout_level },
        ]);
      }
    }

    // ═══════════════════════════════════════════════════════════════
    // FIBONACCI LEVELS — Retracement & Extension Lines
    // Skip if pattern overlay is active (to avoid visual clutter)
    // ═══════════════════════════════════════════════════════════════
    const hasPatternOverlay = !!data?.pattern_render_contract;
    if (fibonacci?.fib_levels_for_chart?.length > 0 && mapped.length > 0 && !hasPatternOverlay) {
      const parseTime = (t) => t > 1e12 ? Math.floor(t / 1000) : t;
      const lastTime = mapped[mapped.length - 1].time;
      
      // Get fib set time range
      const fibSet = fibonacci.fib_set;
      const startTime = fibSet ? Math.min(parseTime(fibSet.swing_high.time), parseTime(fibSet.swing_low.time)) : mapped[0].time;
      
      // Render retracement levels
      fibonacci.fib_levels_for_chart
        .filter(lvl => lvl.type === 'retracement')
        .forEach(level => {
          const color = level.is_key ? '#f59e0b' : 'rgba(148, 163, 184, 0.5)';
          const lineWidth = level.is_key ? 1 : 1;
          const lineStyle = level.is_key ? 0 : 2; // solid for key, dashed for others
          
          const fibSeries = chart.addSeries(LineSeries, {
            color: color,
            lineWidth: lineWidth,
            lineStyle: lineStyle,
            priceLineVisible: false,
            lastValueVisible: level.is_key,
            crosshairMarkerVisible: false,
          });
          
          fibSeries.setData([
            { time: startTime, value: level.price },
            { time: lastTime, value: level.price },
          ]);
        });
      
      // Render key extension levels only
      fibonacci.fib_levels_for_chart
        .filter(lvl => lvl.type === 'extension' && lvl.is_key)
        .forEach(level => {
          const fibExtSeries = chart.addSeries(LineSeries, {
            color: '#8b5cf6',
            lineWidth: 1,
            lineStyle: 1, // dotted
            priceLineVisible: false,
            lastValueVisible: true,
            crosshairMarkerVisible: false,
          });
          
          fibExtSeries.setData([
            { time: startTime, value: level.price },
            { time: lastTime, value: level.price },
          ]);
        });
    }

    // 3. RENDER BASE LAYER — ALWAYS visible (trendlines + channels from StructureEngineV2)
    if (showBaseLayer && baseLayer) {
      const parsePoint = (pt) => {
        if (!pt) return null;
        return {
          time: typeof pt.time === 'number' ? pt.time : parseInt(pt.time),
          value: typeof pt.value === 'number' ? pt.value : parseFloat(pt.value),
        };
      };

      // Render trendlines — DISABLED, now using active_trendlines from structure_visualization
      // Old base_layer trendlines were not structure-aware
      // (baseLayer.trendlines || []).forEach(...)

      // Render channels
      (baseLayer.channels || []).forEach((ch, idx) => {
        const upperStart = parsePoint(ch.upper?.start);
        const upperEnd = parsePoint(ch.upper?.end);
        const lowerStart = parsePoint(ch.lower?.start);
        const lowerEnd = parsePoint(ch.lower?.end);

        if (upperStart && upperEnd && upperStart.time > 0 && upperEnd.time > 0 && upperStart.value > 0 && upperEnd.value > 0) {
          const chUpperSeries = chart.addSeries(LineSeries, {
            color: COLORS.channelUpper,
            lineWidth: 1,
            lineStyle: 2,
            priceLineVisible: false,
            lastValueVisible: false,
            crosshairMarkerVisible: false,
          });
          chUpperSeries.setData([upperStart, upperEnd].sort((a, b) => a.time - b.time));
        }

        if (lowerStart && lowerEnd && lowerStart.time > 0 && lowerEnd.time > 0 && lowerStart.value > 0 && lowerEnd.value > 0) {
          const chLowerSeries = chart.addSeries(LineSeries, {
            color: COLORS.channelLower,
            lineWidth: 1,
            lineStyle: 2,
            priceLineVisible: false,
            lastValueVisible: false,
            crosshairMarkerVisible: false,
          });
          chLowerSeries.setData([lowerStart, lowerEnd].sort((a, b) => a.time - b.time));
        }
      });
    }

    // 4. RENDER LEVELS FROM RENDER_PLAN (max 5, ranked by strength)
    // Prioritize render_plan.levels over baseLayer for clean visualization
    if (showLevels && levels && levels.length > 0) {
      console.log('[ResearchChart] Rendering levels from render_plan:', levels.length);
      const priceRange = mapped.length > 0 ? Math.max(...mapped.map(c => c.high)) - Math.min(...mapped.map(c => c.low)) : 0;
      const threshold = priceRange * 0.015; // 1.5% distance threshold
      const drawnPrices = [];
      
      levels.slice(0, 5).forEach(level => {
        // Skip if too close to existing level
        const tooClose = drawnPrices.some(p => Math.abs(p - level.price) < threshold);
        if (tooClose) return;
        drawnPrices.push(level.price);
        
        const isSupport = level.type === 'support';
        const strength = level.strength || 0.5;
        const lineWidth = strength >= 0.7 ? 2 : 1;
        
        priceSeries.createPriceLine({
          price: level.price,
          color: isSupport ? 'rgba(34, 197, 94, 0.7)' : 'rgba(239, 68, 68, 0.7)',
          lineWidth: lineWidth,
          lineStyle: 1, // dashed
          axisLabelVisible: true,
          title: isSupport ? 'S' : 'R',
        });
      });
    } else if (showBaseLayer && baseLayer) {
      // Fallback: use baseLayer if no render_plan levels
      const priceRange = mapped.length > 0 ? Math.max(...mapped.map(c => c.high)) - Math.min(...mapped.map(c => c.low)) : 0;
      const threshold = priceRange * 0.02;
      const drawnBasePrices = [];

      (baseLayer.supports || []).forEach(level => {
        const tooClose = drawnBasePrices.some(p => Math.abs(p - level.price) < threshold);
        if (tooClose) return;
        drawnBasePrices.push(level.price);
        priceSeries.createPriceLine({
          price: level.price,
          color: 'rgba(34, 197, 94, 0.6)',
          lineWidth: 1,
          lineStyle: 1,
          axisLabelVisible: true,
          title: 'Support',
        });
      });

      (baseLayer.resistances || []).forEach(level => {
        const tooClose = drawnBasePrices.some(p => Math.abs(p - level.price) < threshold);
        if (tooClose) return;
        drawnBasePrices.push(level.price);
        priceSeries.createPriceLine({
          price: level.price,
          color: 'rgba(239, 68, 68, 0.6)',
          lineWidth: 1,
          lineStyle: 1,
          axisLabelVisible: true,
          title: 'Resistance',
        });
      });
    }

    // 5. RENDER TARGETS (secondary, thin lines)
    // Skip if pattern overlay is active (to avoid duplication)
    const hasPatternRenderContract = !!data?.pattern_render_contract;
    if (showTargets && setup && !hasPatternRenderContract) {
      const targetLines = [];
      
      if (setup.trigger) {
        targetLines.push({ price: setup.trigger, color: COLORS.trigger, label: 'Trigger' });
      }
      if (setup.invalidation) {
        targetLines.push({ price: setup.invalidation, color: COLORS.invalidation, label: 'Invalidation' });
      }
      // targets is array of {price, label} objects
      if (setup.targets?.[0]?.price) {
        targetLines.push({ price: setup.targets[0].price, color: COLORS.target, label: setup.targets[0].label || 'T1' });
      }
      if (setup.targets?.[1]?.price) {
        targetLines.push({ price: setup.targets[1].price, color: COLORS.target, label: setup.targets[1].label || 'T2' });
      }
      
      targetLines.forEach(line => {
        priceSeries.createPriceLine({
          price: line.price,
          color: line.color,
          lineWidth: 1,
          lineStyle: 1, // Dotted (less prominent than pattern)
          axisLabelVisible: true,
          title: line.label,
        });
      });
    }

    // =========================================================
    // 4.5 PATTERN GEOMETRY — NOW RENDERED VIA SVG OVERLAY
    // =========================================================
    // Pattern visualization (polylines, shapes) is now handled by
    // PatternSVGOverlay component which renders SVG elements on top
    // of the chart canvas. This approach:
    // - Supports true polylines (P1 → Valley → P2)
    // - Works with chart zoom/pan via coordinate conversion
    // - Not limited by lightweight-charts capabilities
    //
    // Old priceLine/markers approach removed as it couldn't render
    // proper geometric shapes.
    
    if (data?.pattern_render_contract) {
      console.log('[ResearchChart] Pattern detected:', data.pattern_render_contract.type, 
                  '- rendered via SVG overlay');
    }

    // =========================================================
    // 5. EXECUTION OVERLAY — Entry Zone, Stop Loss, Targets
    // =========================================================
    // Only render if valid setup exists
    const primarySetup = tradeSetup?.primary;
    if (showExecutionOverlay && primarySetup && primarySetup.valid) {
      const { direction, entry_zone, stop_loss, target_1, target_2 } = primarySetup;
      const isShort = direction === 'short';
      
      // === ENTRY ZONE (most prominent) ===
      if (entry_zone && entry_zone.length === 2) {
        // Entry high line
        priceSeries.createPriceLine({
          price: entry_zone[1],
          color: isShort ? '#ef4444' : '#22c55e',
          lineWidth: 2,
          lineStyle: 0, // Solid
          axisLabelVisible: true,
          title: 'ENTRY ↓',
        });
        
        // Entry low line
        priceSeries.createPriceLine({
          price: entry_zone[0],
          color: isShort ? '#ef4444' : '#22c55e',
          lineWidth: 2,
          lineStyle: 0,
          axisLabelVisible: false,
          title: '',
        });
      }
      
      // === STOP LOSS (critical level) ===
      if (stop_loss) {
        priceSeries.createPriceLine({
          price: stop_loss,
          color: COLORS.stopLoss,
          lineWidth: 2,
          lineStyle: 2, // Dashed
          axisLabelVisible: true,
          title: 'STOP',
        });
      }
      
      // === TARGET 1 (primary target) ===
      if (target_1) {
        priceSeries.createPriceLine({
          price: target_1,
          color: COLORS.targetPrimary,
          lineWidth: 2,
          lineStyle: 0, // Solid
          axisLabelVisible: true,
          title: 'TP1',
        });
      }
      
      // === TARGET 2 (secondary target, optional) ===
      if (target_2) {
        priceSeries.createPriceLine({
          price: target_2,
          color: COLORS.targetSecondary,
          lineWidth: 1,
          lineStyle: 1, // Dotted
          axisLabelVisible: true,
          title: 'TP2',
        });
      }
    }
    
    // =========================================================
    // 5b. NEW: EXECUTION from per-TF pipeline
    // =========================================================
    if (showExecutionOverlay && execution?.valid) {
      const { direction: execDir, entries = [], stop, targets = [] } = execution;
      const isShort = execDir === 'short';
      
      // Render entries (E1, E2, E3)
      entries.forEach((entry, idx) => {
        if (entry?.price) {
          priceSeries.createPriceLine({
            price: entry.price,
            color: isShort ? '#ef4444' : '#22c55e',
            lineWidth: 2,
            lineStyle: entry.type === 'aggressive' ? 2 : 0,
            axisLabelVisible: true,
            title: `E${idx + 1}`,
          });
        }
      });
      
      // Render STOP
      if (stop?.price) {
        priceSeries.createPriceLine({
          price: stop.price,
          color: COLORS.stopLoss,
          lineWidth: 2,
          lineStyle: 2,
          axisLabelVisible: true,
          title: 'STOP',
        });
      }
      
      // Render targets (TP1, TP2, TP3)
      targets.forEach((target, idx) => {
        if (target?.price) {
          priceSeries.createPriceLine({
            price: target.price,
            color: idx === 0 ? COLORS.targetPrimary : COLORS.targetSecondary,
            lineWidth: idx === 0 ? 2 : 1,
            lineStyle: idx === 0 ? 0 : 1,
            axisLabelVisible: true,
            title: `TP${idx + 1}`,
          });
        }
      });
    }
    
    // =========================================================
    // PATTERN ZOOM — Center chart on pattern window when in Pattern View mode
    // =========================================================
    if (patternViewMode && patternWindow && patternWindow.start && patternWindow.end) {
      console.log('[ResearchChart] Pattern View mode: zooming to pattern window', patternWindow);
      
      // Add padding to window (10% on each side)
      const windowDuration = patternWindow.end - patternWindow.start;
      const padding = windowDuration * 0.15;
      
      const from = patternWindow.start - padding;
      const to = patternWindow.end + padding;
      
      chart.timeScale().setVisibleRange({
        from: from,
        to: to,
      });
    } else {
      // Check if we have a range pattern - if so, zoom to show it
      const patternType = (pattern?.type || '').toLowerCase();
      const isRangePattern = patternType.includes('range') && pattern?.is_active;
      
      if (mapped.length > 0 && isFirstLoadRef.current) {
        // Calculate bar duration for padding calculations
        const barDuration = mapped.length > 1 ? mapped[1].time - mapped[0].time : 86400;
        
        // ═══════════════════════════════════════════════════════════════
        // P1: CHECK FOR SAVED USER ZOOM PREFERENCES FIRST
        // ═══════════════════════════════════════════════════════════════
        const tf = (timeframe || '4H').toUpperCase();
        const savedZoom = getZoomForTimeframe(tf);
        
        // If user has saved visible range for this timeframe, use it
        if (savedZoom?.visibleRange?.from && savedZoom?.visibleRange?.to) {
          console.log('[ResearchChart] Using saved zoom for', tf, savedZoom.visibleRange);
          chart.timeScale().setVisibleRange({
            from: savedZoom.visibleRange.from,
            to: savedZoom.visibleRange.to,
          });
        } else {
          // ═══════════════════════════════════════════════════════════════
          // DEFAULT ZOOM STRATEGY BASED ON TIMEFRAME
          // ═══════════════════════════════════════════════════════════════
          const longTimeframes = ['7D', '30D', '180D', '1Y'];
          const isLongTimeframe = longTimeframes.includes(tf);
          
          console.log('[ResearchChart] Timeframe:', tf, 'isLong:', isLongTimeframe, 'candles:', mapped.length);
          
          if (isLongTimeframe || savedZoom?.fitContent) {
            console.log('[ResearchChart] Long TF (' + tf + '): fitContent for full pattern view');
            chart.timeScale().fitContent();
          } else if (tf === '1D') {
            const visibleBars = savedZoom?.visibleBars || 90;
            const startIdx = Math.max(0, mapped.length - Math.min(visibleBars, mapped.length));
            const fromTime = mapped[startIdx].time;
            const toTime = mapped[mapped.length - 1].time;
            const paddedTo = toTime + barDuration * 10;
            
            console.log('[ResearchChart] 1D: Zooming to last', visibleBars, 'candles');
            chart.timeScale().setVisibleRange({
              from: fromTime,
              to: paddedTo,
            });
          } else {
            const visibleBars = savedZoom?.visibleBars || 60;
            const startIdx = Math.max(0, mapped.length - Math.min(visibleBars, mapped.length));
            const fromTime = mapped[startIdx].time;
            const toTime = mapped[mapped.length - 1].time;
            const paddedTo = toTime + barDuration * 10;
            
            console.log('[ResearchChart] Short TF (' + tf + '): Zooming to last', visibleBars, 'candles');
            chart.timeScale().setVisibleRange({
              from: fromTime,
              to: paddedTo,
            });
          }
        }
        
        isFirstLoadRef.current = false;
      } else if (isFirstLoadRef.current) {
        // ONLY fit content on FIRST LOAD
        chart.timeScale().fitContent();
        isFirstLoadRef.current = false;
      }
      
      // Track user zoom/scroll and save preferences (P1)
      chart.timeScale().subscribeVisibleTimeRangeChange((range) => {
        userHasZoomedRef.current = true;
        handleVisibleRangeChange(range);
      });
    }
    // CRITICAL: Не вызываем fitContent() при последующих обновлениях данных!
    // Пользователь может растянуть график для детального просмотра

    // Resize observer
    const ro = new ResizeObserver(() => {
      if (chartRef.current && chartInstanceRef.current) {
        const w = chartRef.current.clientWidth;
        if (w > 0) {
          chartInstanceRef.current.applyOptions({ width: w });
        }
      }
    });
    ro.observe(chartRef.current);

    return () => {
      ro.disconnect();
      // Cleanup Market Mechanics first
      if (mmRendererRef.current) {
        mmRendererRef.current.clear();
        mmRendererRef.current = null;
      }
      // Then cleanup chart
      if (chartInstanceRef.current) {
        try {
          chartInstanceRef.current.remove();
        } catch (e) {
          // Chart may already be disposed
        }
        chartInstanceRef.current = null;
      }
    };
  // REDUCED dependencies - only recreate chart when candles or core settings change
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [candles, chartType, height, timeframe]);

  const direction = pattern?.direction || setup?.direction || 'neutral';
  const confidence = pattern?.total_score || pattern?.confidence || setup?.confidence || 0;
  const confPercent = Math.round(confidence * 100);
  
  // Format pattern name
  const formatPatternName = (type) => {
    if (!type) return 'Analyzing...';
    return type.split('_').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' ');
  };
  
  // Get direction arrow
  const getArrow = (dir) => {
    if (dir === 'bullish') return '↑';
    if (dir === 'bearish') return '↓';
    return '→';
  };
  
  // Get insight summary based on pattern and direction
  const getInsightSummary = () => {
    const patternType = pattern?.type?.toLowerCase() || '';
    
    if (patternType.includes('triangle')) {
      if (direction === 'bullish') return 'Compression structure with bullish bias. Watch for breakout above resistance.';
      if (direction === 'bearish') return 'Compression structure with bearish bias. Watch for breakdown below support.';
      return 'Symmetrical compression. Breakout direction uncertain.';
    }
    if (patternType.includes('wedge')) {
      if (direction === 'bullish') return 'Falling wedge detected. Bullish reversal likely.';
      if (direction === 'bearish') return 'Rising wedge detected. Bearish reversal likely.';
      return 'Wedge pattern forming.';
    }
    if (patternType.includes('channel')) {
      return 'Trending channel structure detected.';
    }
    if (patternType.includes('range')) {
      return 'Horizontal range. Trade the boundaries.';
    }
    if (patternType.includes('head') || patternType.includes('shoulder')) {
      if (direction === 'bullish') return 'Inverse H&S. Bullish reversal pattern.';
      return 'Head & Shoulders. Bearish reversal pattern.';
    }
    return 'Pattern detected. Analyzing structure.';
  };

  // Structure-first insight when no pattern
  const getStructureInsight = () => {
    if (!structure) return null;
    const regime = structure.regime || structure.trend || 'unknown';
    const bias = structure.bias || 'neutral';
    return {
      title: regime.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase()),
      summary: `Market structure: ${regime}. Bias: ${bias}. No dominant pattern detected.`,
    };
  };

  // Determine chart state for proper rendering
  const chartState = candles.length === 0 ? 'no_data' : 'ready';

  return (
    <ChartWrapper $isTransitioning={isTransitioning}>
      <ChartContainer ref={chartRef} $height={height} />
      
      {/* ═══════════════════════════════════════════════════════════════
          SVG PATTERN OVERLAY — True geometry rendering (polylines, shapes)
          Uses chart coordinate conversion for accurate positioning
          ═══════════════════════════════════════════════════════════════ */}
      {/* ═══════════════════════════════════════════════════════════════
          SVG PATTERN OVERLAY — Uses ta_layers as source of truth
          Priority: active_range → strict pattern → loose → structure
          ═══════════════════════════════════════════════════════════════ */}
      {showPatternOverlay && chartInstance && priceSeriesInstance && (
        <PatternOverlayWithLegend
          chartInstance={chartInstance}
          priceSeriesInstance={priceSeriesInstance}
          data={data}
        />
      )}
      
      {/* EXECUTION LAYER — Overlay badge only, NOT blocking */}
      <ExecutionRenderer 
        execution={execution} 
        showOverlay={false}
        chartState={chartState}
      />
      {/* Pattern V2 Overlay — NOW RENDERED BELOW CHART, disabled here */}
      {/* REMOVED: Pattern cards are shown below chart in ResearchViewNew */}
      {/* Fibonacci Overlay — DISABLED on chart, shown in panel below chart */}
      {/* showFibonacciOverlay is now handled in ResearchViewNew bottom panels */}
      {/* TRADE SETUP OVERLAY — Entry/Stop/TP visualization (NEW!) */}
      <SetupOverlay candles={candles} setup={tradeSetupOverlay} />
    </ChartWrapper>
  );
};

// ═══════════════════════════════════════════════════════════════
// Pattern Overlay with Legend — общий hover state + click-to-select
// ═══════════════════════════════════════════════════════════════
const PatternOverlayWithLegend = ({ chartInstance, priceSeriesInstance, data }) => {
  const [hoveredIndex, setHoveredIndex] = React.useState(null);
  const [selectedIndex, setSelectedIndex] = React.useState(null);
  
  // Click handler — toggle selection
  const handlePatternClick = React.useCallback((idx) => {
    setSelectedIndex(prev => prev === idx ? null : idx);
  }, []);
  
  // Close insight panel
  const handleCloseInsight = React.useCallback(() => {
    setSelectedIndex(null);
  }, []);
  
  // Get selected pattern from render_stack
  const selectedPattern = selectedIndex !== null && data?.render_stack?.[selectedIndex]
    ? data.render_stack[selectedIndex]
    : null;
  
  return (
    <>
      <PatternSVGOverlay 
        chart={chartInstance} 
        priceSeries={priceSeriesInstance}
        renderContract={data?.pattern_render_contract}
        data={data}
        renderStack={data?.render_stack}
        externalHoveredIndex={hoveredIndex}
        externalSetHoveredIndex={setHoveredIndex}
        selectedIndex={selectedIndex}
        onPatternClick={handlePatternClick}
        lifecycle={data?.lifecycle}
      />
      {/* InsightPanel — appears when a pattern is CLICKED */}
      {selectedPattern && (
        <InsightPanel
          pattern={selectedPattern}
          interpretation={data?.interpretation}
          watchLevels={data?.watch_levels}
          lifecycle={data?.lifecycle}
          onClose={handleCloseInsight}
        />
      )}
      {/* Pattern Legend — NOW RENDERED BELOW CHART in ResearchViewNew */}
      {/* Removed to clean up chart visual space */}
    </>
  );
};

export default ResearchChart;
