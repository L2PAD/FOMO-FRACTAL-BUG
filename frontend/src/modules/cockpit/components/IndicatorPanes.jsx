/**
 * IndicatorPanes Component
 * ========================
 * Renders separate indicator panes below the main chart.
 * 
 * Supports:
 * - RSI (with overbought/oversold zones)
 * - MACD (with signal line and histogram)
 * - Stochastic (with %K and %D)
 * - OBV (volume confirmation)
 * - ATR (volatility)
 * - ADX (trend strength)
 * - Volume (colored bars)
 */

import React, { useEffect, useRef, useCallback } from 'react';
import styled from 'styled-components';
import { createChart, LineSeries, HistogramSeries } from 'lightweight-charts';

// ============================================
// STYLED COMPONENTS
// ============================================

const PanesContainer = styled.div`
  display: flex;
  flex-direction: column;
  gap: 4px;
  width: 100%;
  margin-top: 8px;
`;

const PaneWrapper = styled.div`
  background: #ffffff;
  border: 1px solid #eef1f5;
  border-radius: 8px;
  overflow: hidden;
`;

const PaneHeader = styled.div`
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 6px 12px;
  background: #f8fafc;
  border-bottom: 1px solid #eef1f5;
  
  .title {
    font-size: 11px;
    font-weight: 600;
    color: #64748b;
    text-transform: uppercase;
    letter-spacing: 0.5px;
  }
  
  .value {
    font-size: 12px;
    font-weight: 600;
    color: #0f172a;
  }
`;

const ChartContainer = styled.div`
  width: 100%;
  height: ${({ $height }) => $height || 80}px;
`;

// ============================================
// COLORS
// ============================================

const COLORS = {
  rsi: '#3b82f6',
  rsi_overbought: 'rgba(239, 68, 68, 0.1)',
  rsi_oversold: 'rgba(34, 197, 94, 0.1)',
  macd: '#22c55e',
  macd_signal: '#ef4444',
  macd_histogram_pos: 'rgba(34, 197, 94, 0.6)',
  macd_histogram_neg: 'rgba(239, 68, 68, 0.6)',
  stoch_k: '#3b82f6',
  stoch_d: '#ef4444',
  obv: '#22c55e',
  atr: '#f59e0b',
  adx: '#8b5cf6',
  volume_up: '#22c55e',
  volume_down: '#ef4444',
  zone_line: 'rgba(100, 116, 139, 0.3)',
};

// ============================================
// SINGLE PANE COMPONENT
// ============================================

const IndicatorPane = ({ 
  indicator, 
  height = 80,
  showZones = true 
}) => {
  const chartRef = useRef(null);
  const chartInstanceRef = useRef(null);
  
  const parseTime = useCallback((ts) => {
    if (typeof ts === 'number') {
      return ts > 1e12 ? Math.floor(ts / 1000) : ts;
    }
    return 0;
  }, []);
  
  useEffect(() => {
    if (!chartRef.current || !indicator?.data?.length) return;
    
    // Cleanup previous
    if (chartInstanceRef.current) {
      chartInstanceRef.current.remove();
      chartInstanceRef.current = null;
    }
    
    const chart = createChart(chartRef.current, {
      width: chartRef.current.clientWidth,
      height: height,
      layout: {
        background: { type: 'solid', color: '#ffffff' },
        textColor: '#94a3b8',
        fontFamily: "'Gilroy', -apple-system, BlinkMacSystemFont, sans-serif",
        fontSize: 10,
      },
      grid: {
        vertLines: { visible: false },
        horzLines: { color: '#f1f5f9' },
      },
      rightPriceScale: {
        borderVisible: false,
        scaleMargins: { top: 0.1, bottom: 0.1 },
      },
      timeScale: {
        visible: false,
        borderVisible: false,
      },
      crosshair: {
        horzLine: { visible: false },
        vertLine: { visible: false },
      },
      handleScroll: false,
      handleScale: false,
    });
    
    chartInstanceRef.current = chart;
    
    // Get main data
    const mainData = indicator.data
      .map(d => ({ time: parseTime(d.time), value: d.value }))
      .filter(d => d.time > 0 && d.value !== null && d.value !== undefined)
      .sort((a, b) => a.time - b.time);
    
    // Deduplicate
    const seen = new Set();
    const dedupedData = mainData.filter(d => {
      if (seen.has(d.time)) return false;
      seen.add(d.time);
      return true;
    });
    
    // Add main line
    if (indicator.style === 'histogram') {
      // Volume histogram
      const histogramData = indicator.data
        .map(d => ({ 
          time: parseTime(d.time), 
          value: d.value,
          color: d.color || COLORS.volume_up
        }))
        .filter(d => d.time > 0)
        .sort((a, b) => a.time - b.time);
      
      const seenHist = new Set();
      const dedupedHist = histogramData.filter(d => {
        if (seenHist.has(d.time)) return false;
        seenHist.add(d.time);
        return true;
      });
      
      const series = chart.addSeries(HistogramSeries, {
        color: indicator.color || COLORS.volume_up,
        priceLineVisible: false,
        lastValueVisible: false,
      });
      series.setData(dedupedHist);
    } else {
      // Line indicator
      // For RSI: color based on current value
      let lineColor = indicator.color || COLORS.rsi;
      if (indicator.id === 'rsi' && dedupedData.length > 0) {
        const lastValue = dedupedData[dedupedData.length - 1].value;
        if (lastValue < 35) lineColor = '#22c55e';  // Oversold = green
        else if (lastValue > 65) lineColor = '#ef4444';  // Overbought = red
        else lineColor = '#64748b';  // Neutral = gray
      }
      
      // For MACD: color based on value (positive = green, negative = red)
      if (indicator.id === 'macd' && dedupedData.length > 0) {
        const lastValue = dedupedData[dedupedData.length - 1].value;
        if (lastValue > 0) lineColor = '#22c55e';  // Positive = green
        else if (lastValue < 0) lineColor = '#ef4444';  // Negative = red
        else lineColor = '#64748b';  // Zero = neutral
      }
      
      const series = chart.addSeries(LineSeries, {
        color: lineColor,
        lineWidth: indicator.line_width || 2,
        priceLineVisible: false,
        lastValueVisible: true,
        crosshairMarkerVisible: false,
      });
      series.setData(dedupedData);
      
      // Add overbought/oversold zones (RSI only)
      if (showZones && indicator.id === 'rsi') {
        if (indicator.overbought !== null && indicator.overbought !== undefined) {
          series.createPriceLine({
            price: indicator.overbought,
            color: COLORS.zone_line,
            lineWidth: 1,
            lineStyle: 2,
            axisLabelVisible: false,
          });
        }
        
        if (indicator.oversold !== null && indicator.oversold !== undefined) {
          series.createPriceLine({
            price: indicator.oversold,
            color: COLORS.zone_line,
            lineWidth: 1,
            lineStyle: 2,
            axisLabelVisible: false,
          });
        }
      }
      
      // Zero line for MACD
      if (showZones && indicator.id === 'macd') {
        series.createPriceLine({
          price: 0,
          color: COLORS.zone_line,
          lineWidth: 1,
          lineStyle: 2,
          axisLabelVisible: false,
        });
      }
    }
    
    // NOTE: Extra lines (signal, histogram) NOT rendered for clean view
    // MACD shows single analytical line only
    
    chart.timeScale().fitContent();
    
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
      if (chartInstanceRef.current) {
        chartInstanceRef.current.remove();
        chartInstanceRef.current = null;
      }
    };
  }, [indicator, height, parseTime, showZones]);
  
  if (!indicator?.data?.length) return null;
  
  // Get last value for header
  const lastValue = indicator.data[indicator.data.length - 1]?.value;
  const formattedValue = lastValue !== null && lastValue !== undefined
    ? indicator.id === 'volume' 
      ? (lastValue / 1e6).toFixed(2) + 'M'
      : lastValue.toFixed(2)
    : '-';
  
  return (
    <PaneWrapper>
      <PaneHeader>
        <span className="title">{indicator.name}</span>
        <span className="value">{formattedValue}</span>
      </PaneHeader>
      <ChartContainer ref={chartRef} $height={height} />
    </PaneWrapper>
  );
};

// ============================================
// MAIN COMPONENT
// ============================================

const IndicatorPanes = ({
  indicators = { overlays: [], panes: [] },
  visiblePanes = ['rsi', 'macd', 'volume'], // Default visible panes
  paneHeight = 80,
}) => {
  const panes = indicators.panes || [];
  
  // Filter to only visible panes
  const visibleIndicators = panes.filter(p => 
    visiblePanes.includes(p.id) || visiblePanes.includes('all')
  );
  
  if (visibleIndicators.length === 0) {
    return null;
  }
  
  return (
    <PanesContainer data-testid="indicator-panes">
      {visibleIndicators.map(indicator => (
        <IndicatorPane
          key={indicator.id}
          indicator={indicator}
          height={paneHeight}
        />
      ))}
    </PanesContainer>
  );
};

export default IndicatorPanes;
