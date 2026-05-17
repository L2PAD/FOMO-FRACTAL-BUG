/**
 * FlowSeriesChart — Phase E0
 * ============================
 * TradingView-style flow chart using lightweight-charts.
 * Shows In/Out/Net as histogram bars with crosshair tooltip.
 *
 * Modes:
 *   - Net: single histogram (green/red)
 *   - In/Out: dual histograms overlaid
 *   - Cumulative: running sum of net
 */

import React, { useRef, useEffect, useState, useMemo } from 'react';
import { createChart, CrosshairMode, HistogramSeries } from 'lightweight-charts';

export interface FlowBarPoint {
  ts: number;   // unix ms
  inUsd: number;
  outUsd: number;
  netUsd: number;
  transfers?: number;
  uniqueWallets?: number;
}

type MetricMode = 'net' | 'inout' | 'cumulative';

interface Props {
  points: FlowBarPoint[];
  height?: number;
  metricMode?: MetricMode;
  onMetricModeChange?: (mode: MetricMode) => void;
  stale?: boolean;
  window?: string;
}

const MODES: { key: MetricMode; label: string }[] = [
  { key: 'net', label: 'Net Flow' },
  { key: 'inout', label: 'In / Out' },
  { key: 'cumulative', label: 'Cumulative' },
];

function fmtUsd(n: number): string {
  const abs = Math.abs(n);
  const sign = n < 0 ? '-' : '';
  if (abs >= 1e6) return `${sign}$${(abs / 1e6).toFixed(2)}M`;
  if (abs >= 1e3) return `${sign}$${(abs / 1e3).toFixed(1)}K`;
  return `${sign}$${abs.toFixed(0)}`;
}

export function FlowSeriesChart({
  points,
  height = 220,
  metricMode: externalMode,
  onMetricModeChange,
  stale,
  window: win,
}: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<any>(null);
  const seriesRefs = useRef<any[]>([]);
  const [internalMode, setInternalMode] = useState<MetricMode>('net');
  const [tooltip, setTooltip] = useState<{
    x: number; y: number; time: number;
    inUsd: number; outUsd: number; netUsd: number;
    transfers?: number;
  } | null>(null);

  const mode = externalMode ?? internalMode;
  const setMode = (m: MetricMode) => {
    setInternalMode(m);
    onMetricModeChange?.(m);
  };

  // Compute chart data based on mode
  const chartData = useMemo(() => {
    if (!points.length) return { primary: [], secondary: [] };

    const sorted = [...points].sort((a, b) => a.ts - b.ts);

    if (mode === 'net') {
      return {
        primary: sorted.map(p => ({
          time: Math.floor(p.ts / 1000) as any,
          value: p.netUsd,
          color: p.netUsd >= 0 ? 'rgba(34, 197, 94, 0.85)' : 'rgba(239, 68, 68, 0.85)',
        })),
        secondary: [],
      };
    }

    if (mode === 'inout') {
      return {
        primary: sorted.map(p => ({
          time: Math.floor(p.ts / 1000) as any,
          value: p.inUsd,
          color: 'rgba(34, 197, 94, 0.7)',
        })),
        secondary: sorted.map(p => ({
          time: Math.floor(p.ts / 1000) as any,
          value: -p.outUsd,
          color: 'rgba(239, 68, 68, 0.7)',
        })),
      };
    }

    // Cumulative
    let cum = 0;
    return {
      primary: sorted.map(p => {
        cum += p.netUsd;
        return {
          time: Math.floor(p.ts / 1000) as any,
          value: cum,
          color: cum >= 0 ? 'rgba(34, 197, 94, 0.85)' : 'rgba(239, 68, 68, 0.85)',
        };
      }),
      secondary: [],
    };
  }, [points, mode]);

  // Map of time → original point (for tooltip)
  const pointMap = useMemo(() => {
    const m = new Map<number, FlowBarPoint>();
    for (const p of points) {
      m.set(Math.floor(p.ts / 1000), p);
    }
    return m;
  }, [points]);

  // Create/update chart
  useEffect(() => {
    if (!containerRef.current) return;

    // Cleanup previous
    if (chartRef.current) {
      chartRef.current.remove();
      chartRef.current = null;
      seriesRefs.current = [];
    }

    if (chartData.primary.length === 0) return;

    const chart = createChart(containerRef.current, {
      height,
      layout: {
        background: { type: 'solid' as any, color: '#ffffff' },
        textColor: 'rgba(15, 23, 42, 0.6)',
        fontFamily: "'Inter', -apple-system, sans-serif",
        fontSize: 11,
      },
      grid: {
        vertLines: { color: 'rgba(15, 23, 42, 0.04)' },
        horzLines: { color: 'rgba(15, 23, 42, 0.04)' },
      },
      crosshair: {
        mode: CrosshairMode.Normal,
        vertLine: { color: 'rgba(100, 100, 100, 0.3)', style: 2, width: 1, labelVisible: false },
        horzLine: { color: 'rgba(100, 100, 100, 0.3)', style: 2, width: 1 },
      },
      rightPriceScale: {
        borderColor: 'rgba(15, 23, 42, 0.08)',
        scaleMargins: { top: 0.1, bottom: 0.05 },
      },
      timeScale: {
        borderColor: 'rgba(15, 23, 42, 0.08)',
        rightOffset: 3,
        barSpacing: Math.max(6, Math.min(30, 800 / chartData.primary.length)),
        fixLeftEdge: true,
        fixRightEdge: true,
        timeVisible: true,
        secondsVisible: false,
      },
      handleScroll: { mouseWheel: false, pressedMouseMove: true, horzTouchDrag: true, vertTouchDrag: false },
      handleScale: { mouseWheel: false, pinch: false },
      localization: {
        locale: 'en-US',  // Force valid locale to avoid en-US@posix issues
      },
    });

    // Primary histogram
    const primarySeries = chart.addSeries(HistogramSeries, {
      priceFormat: { type: 'custom' as any, formatter: fmtUsd },
      priceScaleId: 'right',
    });
    primarySeries.setData(chartData.primary);
    seriesRefs.current.push(primarySeries);

    // Secondary histogram (for In/Out mode)
    if (chartData.secondary.length > 0) {
      const secondarySeries = chart.addSeries(HistogramSeries, {
        priceFormat: { type: 'custom' as any, formatter: fmtUsd },
        priceScaleId: 'right',
      });
      secondarySeries.setData(chartData.secondary);
      seriesRefs.current.push(secondarySeries);
    }

    chart.timeScale().fitContent();

    // Crosshair → tooltip
    chart.subscribeCrosshairMove((param: any) => {
      if (!param.time || !param.point) {
        setTooltip(null);
        return;
      }
      const original = pointMap.get(param.time as number);
      if (original) {
        setTooltip({
          x: param.point.x,
          y: param.point.y,
          time: original.ts,
          inUsd: original.inUsd,
          outUsd: original.outUsd,
          netUsd: original.netUsd,
          transfers: original.transfers,
        });
      }
    });

    chartRef.current = chart;

    return () => {
      chart.remove();
      chartRef.current = null;
      seriesRefs.current = [];
    };
  }, [chartData, height, pointMap]);

  // Handle resize
  useEffect(() => {
    if (!containerRef.current || !chartRef.current) return;
    const obs = new ResizeObserver(() => {
      if (containerRef.current && chartRef.current) {
        chartRef.current.applyOptions({ width: containerRef.current.clientWidth });
      }
    });
    obs.observe(containerRef.current);
    return () => obs.disconnect();
  }, [chartData]);

  if (points.length === 0) {
    return (
      <div className="flex flex-col items-center py-12 text-gray-400" data-testid="flow-chart-empty">
        <p className="text-xs">No bucket data yet</p>
        <p className="text-[10px] mt-1 text-gray-300">Data populates after series job runs</p>
      </div>
    );
  }

  return (
    <div className="relative" data-testid="flow-series-chart">
      {/* Mode toggle */}
      <div className="flex items-center gap-0.5 bg-gray-100 p-0.5 rounded-lg w-fit mb-3">
        {MODES.map(m => (
          <button
            key={m.key}
            onClick={() => setMode(m.key)}
            className={`px-2.5 py-1 rounded-md text-[11px] font-medium transition-all ${
              mode === m.key ? 'bg-white text-gray-900' : 'text-gray-500 hover:text-gray-700'
            }`}
            data-testid={`flow-chart-mode-${m.key}`}
          >
            {m.label}
          </button>
        ))}
      </div>

      {/* Chart container */}
      <div ref={containerRef} className="w-full rounded-lg overflow-hidden" />

      {/* Tooltip */}
      {tooltip && (
        <div
          className="absolute pointer-events-none z-20 bg-gray-900 text-white text-[10px] px-2.5 py-1.5 rounded-lg"
          style={{
            left: Math.min(tooltip.x, (containerRef.current?.clientWidth || 600) - 160),
            top: Math.max(tooltip.y - 70, 40),
          }}
          data-testid="flow-chart-tooltip"
        >
          <p className="font-medium mb-0.5">
            {(() => {
              try {
                return new Date(tooltip.time).toLocaleDateString('en-US', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
              } catch {
                // Fallback for invalid locale (e.g., en-US@posix)
                return new Date(tooltip.time).toISOString().slice(0, 16).replace('T', ' ');
              }
            })()}
          </p>
          <div className="grid grid-cols-2 gap-x-3 gap-y-0.5">
            <span className="text-emerald-300">In:</span><span className="text-right tabular-nums">{fmtUsd(tooltip.inUsd)}</span>
            <span className="text-red-300">Out:</span><span className="text-right tabular-nums">{fmtUsd(tooltip.outUsd)}</span>
            <span className="text-gray-300">Net:</span>
            <span className={`text-right tabular-nums ${tooltip.netUsd >= 0 ? 'text-emerald-300' : 'text-red-300'}`}>
              {fmtUsd(tooltip.netUsd)}
            </span>
            {tooltip.transfers != null && (
              <>
                <span className="text-gray-400">Tx:</span><span className="text-right tabular-nums">{tooltip.transfers}</span>
              </>
            )}
          </div>
        </div>
      )}

      {/* Legend */}
      <div className="flex items-center gap-4 mt-1.5 text-[10px] text-gray-400">
        {mode === 'inout' ? (
          <>
            <span className="flex items-center gap-1"><span className="w-2 h-2 bg-emerald-500 rounded-sm" /> Inflow</span>
            <span className="flex items-center gap-1"><span className="w-2 h-2 bg-red-500 rounded-sm" /> Outflow</span>
          </>
        ) : mode === 'cumulative' ? (
          <span className="flex items-center gap-1"><span className="w-2 h-2 bg-emerald-500 rounded-sm" /> Cumulative Net</span>
        ) : (
          <span className="flex items-center gap-1"><span className="w-2 h-2 bg-emerald-500 rounded-sm" /> Net Flow</span>
        )}
        <span className="ml-auto">{points.length} buckets</span>
        {stale && <span className="text-amber-500">Stale</span>}
      </div>
    </div>
  );
}

export default FlowSeriesChart;
