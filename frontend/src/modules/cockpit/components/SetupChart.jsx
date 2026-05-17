/**
 * SetupChart Component — Advanced Visualization
 * ==============================================
 * Full chart visualization with:
 * - Price candles
 * - Pattern lines (triangles, channels, flags)
 * - Support/Resistance levels
 * - Entry zone (rectangle area)
 * - Invalidation line
 * - Target lines
 * - Bias indicator
 * - Crosshair, zoom, pan
 */

import React, { useEffect, useRef, useCallback, useState } from 'react';
import styled from 'styled-components';
import { createChart, CandlestickSeries, LineSeries } from 'lightweight-charts';

// ============================================
// STYLED COMPONENTS
// ============================================

const ChartWrapper = styled.div`
  position: relative;
  width: 100%;
  height: 100%;
  min-height: 800px;
`;

const ChartContainer = styled.div`
  width: 100%;
  height: 100%;
`;

const BiasOverlay = styled.div`
  position: absolute;
  top: 16px;
  right: 16px;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 20px;
  background: ${({ $direction }) => 
    $direction === 'bullish' ? 'rgba(5, 165, 132, 0.95)' : 
    $direction === 'bearish' ? 'rgba(239, 68, 68, 0.95)' : 
    'rgba(100, 116, 139, 0.95)'};
  color: #ffffff;
  border-radius: 10px;
  font-weight: 600;
  font-size: 15px;
  box-shadow: 0 4px 16px rgba(0,0,0,0.2);
  z-index: 10;
  backdrop-filter: blur(8px);
  
  .arrow {
    font-size: 24px;
    line-height: 1;
  }
  
  .label {
    text-transform: uppercase;
    letter-spacing: 0.5px;
  }
  
  .confidence {
    font-size: 13px;
    opacity: 0.9;
    margin-left: 4px;
    font-weight: 500;
  }
`;

const PatternLabel = styled.div`
  position: absolute;
  top: 16px;
  left: 16px;
  padding: 10px 16px;
  background: rgba(59, 130, 246, 0.95);
  border-radius: 10px;
  font-size: 13px;
  font-weight: 600;
  color: #ffffff;
  box-shadow: 0 4px 16px rgba(59, 130, 246, 0.3);
  z-index: 10;
  backdrop-filter: blur(8px);
  
  .pattern-type {
    text-transform: capitalize;
  }
  
  .pattern-confidence {
    opacity: 0.9;
    font-size: 12px;
    margin-left: 8px;
    font-weight: 500;
  }
`;

const ConfluenceMeter = styled.div`
  position: absolute;
  top: 16px;
  left: 50%;
  transform: translateX(-50%);
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 16px;
  background: rgba(255, 255, 255, 0.95);
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  font-size: 12px;
  font-weight: 600;
  color: #0f172a;
  box-shadow: 0 4px 12px rgba(0,0,0,0.08);
  z-index: 10;
  
  .label {
    color: #64748b;
    text-transform: uppercase;
    letter-spacing: 0.3px;
  }
  
  .value {
    font-size: 16px;
    color: ${({ $score }) => 
      $score >= 70 ? '#05A584' : 
      $score >= 50 ? '#f59e0b' : '#ef4444'};
  }
  
  .bar {
    width: 60px;
    height: 6px;
    background: #e2e8f0;
    border-radius: 3px;
    overflow: hidden;
    
    .fill {
      height: 100%;
      border-radius: 3px;
      background: ${({ $score }) => 
        $score >= 70 ? '#05A584' : 
        $score >= 50 ? '#f59e0b' : '#ef4444'};
      width: ${({ $score }) => Math.min($score, 100)}%;
      transition: width 0.3s ease;
    }
  }
`;

const LegendOverlay = styled.div`
  position: absolute;
  bottom: 16px;
  left: 16px;
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  padding: 10px 14px;
  background: rgba(255, 255, 255, 0.95);
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  font-size: 11px;
  z-index: 10;
`;

const LegendItem = styled.div`
  display: flex;
  align-items: center;
  gap: 6px;
  
  .color {
    width: 16px;
    height: 3px;
    border-radius: 2px;
    background: ${({ $color }) => $color};
  }
  
  .color.dashed {
    background: repeating-linear-gradient(
      90deg,
      ${({ $color }) => $color} 0px,
      ${({ $color }) => $color} 4px,
      transparent 4px,
      transparent 8px
    );
  }
  
  .label {
    color: #64748b;
    font-weight: 500;
  }
`;

// ============================================
// COLORS
// ============================================

const COLORS = {
  bullish: '#05A584',
  bearish: '#ef4444',
  neutral: '#64748b',
  support: '#05A584',
  resistance: '#ef4444',
  fib: '#8b5cf6',
  liquidity: '#f59e0b',
  pattern: '#3b82f6',
  entry: '#22c55e',
  entryZone: 'rgba(34, 197, 94, 0.15)',
  invalidation: '#ef4444',
  target: '#3b82f6',
  targetLight: 'rgba(59, 130, 246, 0.6)',
};

// ============================================
// COMPONENT
// ============================================

const SetupChart = ({ 
  candles = [], 
  setup = null,
  showPatterns = true,
  showLevels = true,
  showStructure = false,
  showIndicators = false,
  showTargets = true,
  chartType = 'candles',
  height = 900,
}) => {
  const chartRef = useRef(null);
  const chartInstanceRef = useRef(null);
  const seriesRef = useRef({});
  const [chartReady, setChartReady] = useState(false);

  // Parse timestamp to Unix seconds
  const parseTime = useCallback((ts) => {
    if (typeof ts === 'number') {
      return ts > 1e12 ? Math.floor(ts / 1000) : ts;
    }
    if (typeof ts === 'string') {
      try {
        return Math.floor(new Date(ts).getTime() / 1000);
      } catch {
        return 0;
      }
    }
    return 0;
  }, []);

  // Get time range from candles
  const getTimeRange = useCallback(() => {
    if (candles.length === 0) return { start: 0, end: 0 };
    const times = candles.map(c => parseTime(c.timestamp || c.time)).filter(t => t > 0);
    return {
      start: Math.min(...times),
      end: Math.max(...times),
    };
  }, [candles, parseTime]);

  // Initialize chart
  useEffect(() => {
    if (!chartRef.current) return;
    
    // Cleanup previous
    if (chartInstanceRef.current) {
      chartInstanceRef.current.remove();
      chartInstanceRef.current = null;
      seriesRef.current = {};
    }

    const rect = chartRef.current.getBoundingClientRect();
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
        vertLine: { 
          color: '#475569', 
          width: 1, 
          style: 2,
          labelBackgroundColor: '#475569',
        },
        horzLine: { 
          color: '#475569', 
          width: 1, 
          style: 2,
          labelBackgroundColor: '#475569',
        },
      },
      rightPriceScale: {
        borderColor: '#e2e8f0',
        scaleMargins: { top: 0.08, bottom: 0.08 },
      },
      timeScale: {
        borderColor: '#e2e8f0',
        timeVisible: true,
        secondsVisible: false,
        rightOffset: 5,
        barSpacing: 8,
        minBarSpacing: 2,
      },
      handleScroll: {
        mouseWheel: true,
        pressedMouseMove: true,
        horzTouchDrag: true,
        vertTouchDrag: false,
      },
      handleScale: {
        axisPressedMouseMove: true,
        mouseWheel: true,
        pinch: true,
      },
    });

    chartInstanceRef.current = chart;

    // Add price series based on chartType
    let priceSeries;
    if (chartType === 'line') {
      priceSeries = chart.addSeries(LineSeries, {
        color: COLORS.bullish,
        lineWidth: 2,
        crosshairMarkerVisible: true,
        crosshairMarkerRadius: 4,
      });
    } else {
      priceSeries = chart.addSeries(CandlestickSeries, {
        upColor: COLORS.bullish,
        downColor: COLORS.bearish,
        borderUpColor: COLORS.bullish,
        borderDownColor: COLORS.bearish,
        wickUpColor: COLORS.bullish,
        wickDownColor: COLORS.bearish,
      });
    }
    seriesRef.current.candles = priceSeries;

    // Set candle data
    if (candles.length > 0) {
      const seen = new Set();
      const mapped = candles
        .map(c => ({
          time: parseTime(c.timestamp || c.time),
          open: c.open || c.o,
          high: c.high || c.h,
          low: c.low || c.l,
          close: c.close || c.c,
          value: c.close || c.c, // For line chart
        }))
        .filter(c => c.time > 0)
        .sort((a, b) => a.time - b.time)
        .filter(c => {
          if (seen.has(c.time)) return false;
          seen.add(c.time);
          return true;
        });

      priceSeries.setData(mapped);
      chart.timeScale().fitContent();
      setChartReady(true);
    }

    // Resize observer
    const ro = new ResizeObserver(() => {
      if (chartRef.current && chartInstanceRef.current) {
        const w = chartRef.current.clientWidth;
        const h = chartRef.current.clientHeight;
        if (w > 0 && h > 0) {
          chartInstanceRef.current.applyOptions({ width: w, height: h });
        }
      }
    });
    ro.observe(chartRef.current);

    return () => {
      ro.disconnect();
      if (chartInstanceRef.current) {
        chartInstanceRef.current.remove();
        chartInstanceRef.current = null;
        seriesRef.current = {};
        setChartReady(false);
      }
    };
  }, [candles, height, parseTime, chartType]);

  // ============================================
  // DRAW PATTERN LINES
  // ============================================
  useEffect(() => {
    const chart = chartInstanceRef.current;
    const candleSeries = seriesRef.current.candles;
    
    if (!chart || !candleSeries || !setup || !showPatterns) return;
    
    // Remove old pattern series
    if (seriesRef.current.patternLines) {
      seriesRef.current.patternLines.forEach(series => {
        try { chart.removeSeries(series); } catch {}
      });
    }
    seriesRef.current.patternLines = [];

    const patterns = setup.patterns || [];
    const timeRange = getTimeRange();
    
    if (timeRange.start === 0 || timeRange.end === 0) return;
    
    patterns.forEach((pattern, patternIndex) => {
      const points = pattern.points || [];
      if (points.length < 2) return;
      
      // Group points by type (highs and lows for triangles)
      const highPoints = points.filter(p => p.type === 'high' || p.type?.includes('top') || p.type?.includes('high'));
      const lowPoints = points.filter(p => p.type === 'low' || p.type?.includes('bottom') || p.type?.includes('low'));
      
      // Draw high trendline
      if (highPoints.length >= 2) {
        const seen = new Set();
        const lineData = highPoints
          .map(p => ({ time: parseTime(p.time), value: p.price }))
          .filter(p => p.time > 0)
          .sort((a, b) => a.time - b.time)
          .filter(p => {
            if (seen.has(p.time)) return false;
            seen.add(p.time);
            return true;
          });
        
        if (lineData.length >= 2) {
          // Extend line to current time (only if not duplicate)
          const slope = (lineData[lineData.length-1].value - lineData[0].value) / 
                       (lineData[lineData.length-1].time - lineData[0].time);
          const extendedTime = timeRange.end + 86400; // Add 1 day to avoid duplicate
          const extendedValue = lineData[lineData.length-1].value + 
                               slope * (extendedTime - lineData[lineData.length-1].time);
          
          if (!seen.has(extendedTime)) {
            lineData.push({ time: extendedTime, value: extendedValue });
          }
          
          const series = chart.addSeries(LineSeries, {
            color: COLORS.pattern,
            lineWidth: 2,
            lineStyle: 0,
            crosshairMarkerVisible: false,
            priceLineVisible: false,
            lastValueVisible: false,
          });
          series.setData(lineData);
          seriesRef.current.patternLines.push(series);
        }
      }
      
      // Draw low trendline
      if (lowPoints.length >= 2) {
        const seenLow = new Set();
        const lineData = lowPoints
          .map(p => ({ time: parseTime(p.time), value: p.price }))
          .filter(p => p.time > 0)
          .sort((a, b) => a.time - b.time)
          .filter(p => {
            if (seenLow.has(p.time)) return false;
            seenLow.add(p.time);
            return true;
          });
        
        if (lineData.length >= 2) {
          // Extend line (only if not duplicate)
          const slope = (lineData[lineData.length-1].value - lineData[0].value) / 
                       (lineData[lineData.length-1].time - lineData[0].time);
          const extendedTime = timeRange.end + 86400;
          const extendedValue = lineData[lineData.length-1].value + 
                               slope * (extendedTime - lineData[lineData.length-1].time);
          
          if (!seenLow.has(extendedTime)) {
            lineData.push({ time: extendedTime, value: extendedValue });
          }
          
          const series = chart.addSeries(LineSeries, {
            color: COLORS.pattern,
            lineWidth: 2,
            lineStyle: 0,
            crosshairMarkerVisible: false,
            priceLineVisible: false,
            lastValueVisible: false,
          });
          series.setData(lineData);
          seriesRef.current.patternLines.push(series);
        }
      }
      
      // For channel patterns, draw both lines from start to end points
      if (pattern.type?.includes('channel')) {
        const startHigh = points.find(p => p.type === 'high_start');
        const endHigh = points.find(p => p.type === 'high_end');
        const startLow = points.find(p => p.type === 'low_start');
        const endLow = points.find(p => p.type === 'low_end');
        
        if (startHigh && endHigh) {
          const t1 = parseTime(startHigh.time);
          const t2 = parseTime(endHigh.time);
          // Only draw if times are different and valid
          if (t1 > 0 && t2 > 0 && t1 !== t2) {
            const series = chart.addSeries(LineSeries, {
              color: COLORS.resistance,
              lineWidth: 2,
              crosshairMarkerVisible: false,
              priceLineVisible: false,
              lastValueVisible: false,
            });
            series.setData([
              { time: t1, value: startHigh.price },
              { time: t2, value: endHigh.price },
            ].sort((a, b) => a.time - b.time));
            seriesRef.current.patternLines.push(series);
          }
        }
        
        if (startLow && endLow) {
          const t1 = parseTime(startLow.time);
          const t2 = parseTime(endLow.time);
          // Only draw if times are different and valid
          if (t1 > 0 && t2 > 0 && t1 !== t2) {
            const series = chart.addSeries(LineSeries, {
              color: COLORS.support,
              lineWidth: 2,
              crosshairMarkerVisible: false,
              priceLineVisible: false,
              lastValueVisible: false,
            });
            series.setData([
              { time: t1, value: startLow.price },
              { time: t2, value: endLow.price },
            ].sort((a, b) => a.time - b.time));
            seriesRef.current.patternLines.push(series);
          }
        }
      }
    });
  }, [setup, showPatterns, candles, parseTime, getTimeRange]);

  // ============================================
  // DRAW LEVELS (Support/Resistance)
  // ============================================
  useEffect(() => {
    const chart = chartInstanceRef.current;
    const candleSeries = seriesRef.current.candles;
    
    if (!chart || !candleSeries || !setup || !showLevels) return;

    // Remove old level lines
    if (seriesRef.current.levelLines) {
      seriesRef.current.levelLines.forEach(line => {
        try { candleSeries.removePriceLine(line); } catch {}
      });
    }
    seriesRef.current.levelLines = [];

    const levels = setup.levels || [];
    
    // Draw support/resistance levels
    levels.slice(0, 8).forEach((level) => {
      const isSupport = level.type === 'support';
      const isFib = level.type?.includes('fib');
      const isLiquidity = level.type?.includes('liquidity');
      
      let color = COLORS.neutral;
      let lineStyle = 0; // solid
      let lineWidth = 1;
      
      if (isSupport) {
        color = COLORS.support;
        lineWidth = level.strength > 0.7 ? 2 : 1;
      } else if (level.type === 'resistance') {
        color = COLORS.resistance;
        lineWidth = level.strength > 0.7 ? 2 : 1;
      } else if (isFib) {
        color = COLORS.fib;
        lineStyle = 2; // dashed
      } else if (isLiquidity) {
        color = COLORS.liquidity;
        lineStyle = 1; // dotted
      }
      
      const line = candleSeries.createPriceLine({
        price: level.price,
        color: color,
        lineWidth: lineWidth,
        lineStyle: lineStyle,
        axisLabelVisible: true,
        title: '',
      });
      seriesRef.current.levelLines.push(line);
    });

    // ============================================
    // DRAW ENTRY ZONE
    // ============================================
    if (setup.entry_zone) {
      // Entry zone low line
      const entryLow = candleSeries.createPriceLine({
        price: setup.entry_zone.low,
        color: COLORS.entry,
        lineWidth: 2,
        lineStyle: 2,
        axisLabelVisible: true,
        title: 'ENTRY',
      });
      seriesRef.current.levelLines.push(entryLow);
      
      // Entry zone high line
      const entryHigh = candleSeries.createPriceLine({
        price: setup.entry_zone.high,
        color: COLORS.entry,
        lineWidth: 2,
        lineStyle: 2,
        axisLabelVisible: false,
        title: '',
      });
      seriesRef.current.levelLines.push(entryHigh);
    }

    // ============================================
    // DRAW INVALIDATION
    // ============================================
    if (setup.invalidation) {
      const invLine = candleSeries.createPriceLine({
        price: setup.invalidation,
        color: COLORS.invalidation,
        lineWidth: 2,
        lineStyle: 0,
        axisLabelVisible: true,
        title: 'STOP',
      });
      seriesRef.current.levelLines.push(invLine);
    }

    // ============================================
    // DRAW TARGETS
    // ============================================
    if (showTargets) {
      (setup.targets || []).slice(0, 3).forEach((target, i) => {
        const tLine = candleSeries.createPriceLine({
          price: target,
          color: COLORS.target,
          lineWidth: i === 0 ? 2 : 1,
          lineStyle: 2, // dashed
          axisLabelVisible: true,
          title: `TP${i + 1}`,
        });
        seriesRef.current.levelLines.push(tLine);
      });
    }

  }, [setup, showLevels, showTargets, candles]);

  // ============================================
  // DRAW STRUCTURE MARKERS
  // ============================================
  useEffect(() => {
    const chart = chartInstanceRef.current;
    const candleSeries = seriesRef.current.candles;
    
    if (!chart || !candleSeries || !setup || !showStructure) return;

    // Note: setMarkers may not be available in newer lightweight-charts versions
    // Use series markers if available, otherwise skip
    const structure = setup.structure || [];
    
    try {
      // Try to use markers if the method exists
      if (typeof candleSeries.setMarkers === 'function') {
        const markers = structure.map(point => {
          const time = parseTime(point.time);
          const isBullish = ['HH', 'HL'].includes(point.type);
          
          return {
            time: time,
            position: isBullish ? 'aboveBar' : 'belowBar',
            color: isBullish ? COLORS.bullish : COLORS.bearish,
            shape: isBullish ? 'arrowUp' : 'arrowDown',
            text: point.type,
          };
        }).filter(m => m.time > 0);

        if (markers.length > 0) {
          candleSeries.setMarkers(markers.sort((a, b) => a.time - b.time));
        } else {
          candleSeries.setMarkers([]);
        }
      }
    } catch (err) {
      console.log('Structure markers not supported in this chart version');
    }

  }, [setup, showStructure, candles, parseTime]);

  // Get display data
  const topPattern = setup?.patterns?.[0];
  const direction = setup?.direction || 'neutral';
  const confidence = Math.round((setup?.confidence || 0) * 100);
  const confluenceScore = Math.round((setup?.confluence_score || 0) * 100);

  // Calculate legend items
  const showLegend = setup && (showLevels || showPatterns);

  return (
    <ChartWrapper style={{ height }}>
      <ChartContainer ref={chartRef} data-testid="setup-chart" />
      
      {/* Pattern Label */}
      {topPattern && showPatterns && (
        <PatternLabel data-testid="pattern-label">
          <span className="pattern-type">
            {topPattern.type?.replace(/_/g, ' ') || 'Pattern'}
          </span>
          <span className="pattern-confidence">
            {Math.round((topPattern.confidence || 0) * 100)}%
          </span>
        </PatternLabel>
      )}
      
      {/* Confluence Meter */}
      {setup && confluenceScore > 0 && (
        <ConfluenceMeter $score={confluenceScore} data-testid="confluence-meter">
          <span className="label">Confluence</span>
          <span className="value">{confluenceScore}%</span>
          <div className="bar">
            <div className="fill" />
          </div>
        </ConfluenceMeter>
      )}
      
      {/* Bias Overlay */}
      {setup && (
        <BiasOverlay $direction={direction} data-testid="bias-overlay">
          <span className="arrow">
            {direction === 'bullish' ? '↑' : direction === 'bearish' ? '↓' : '→'}
          </span>
          <span className="label">{direction}</span>
          <span className="confidence">{confidence}%</span>
        </BiasOverlay>
      )}
      
      {/* Legend */}
      {showLegend && (
        <LegendOverlay data-testid="chart-legend">
          <LegendItem $color={COLORS.support}>
            <div className="color" />
            <span className="label">Support</span>
          </LegendItem>
          <LegendItem $color={COLORS.resistance}>
            <div className="color" />
            <span className="label">Resistance</span>
          </LegendItem>
          <LegendItem $color={COLORS.pattern}>
            <div className="color" />
            <span className="label">Pattern</span>
          </LegendItem>
          <LegendItem $color={COLORS.entry}>
            <div className="color dashed" />
            <span className="label">Entry</span>
          </LegendItem>
          <LegendItem $color={COLORS.invalidation}>
            <div className="color" />
            <span className="label">Stop</span>
          </LegendItem>
          <LegendItem $color={COLORS.target}>
            <div className="color dashed" />
            <span className="label">Target</span>
          </LegendItem>
        </LegendOverlay>
      )}
    </ChartWrapper>
  );
};

export default SetupChart;
