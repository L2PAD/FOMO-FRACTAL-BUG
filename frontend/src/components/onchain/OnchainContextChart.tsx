import React, { useEffect, useRef } from 'react';
import { createChart, IChartApi, ISeriesApi, LineData, UTCTimestamp } from 'lightweight-charts';
import { OnchainChartDataPoint } from './onchainApi';

interface OnchainContextChartProps {
  series: OnchainChartDataPoint[];
  loading?: boolean;
}

export function OnchainContextChart({ series, loading }: OnchainContextChartProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const scoreSeriesRef = useRef<ISeriesApi<'Line'> | null>(null);
  const confSeriesRef = useRef<ISeriesApi<'Line'> | null>(null);

  useEffect(() => {
    if (!containerRef.current) return;

    // Create chart
    const chart = createChart(containerRef.current, {
      width: containerRef.current.clientWidth,
      height: 180,
      layout: {
        background: { color: '#ffffff' },
        textColor: '#64748b',
        fontFamily: 'Inter, system-ui, sans-serif',
      },
      grid: {
        vertLines: { color: '#f1f5f9' },
        horzLines: { color: '#f1f5f9' },
      },
      rightPriceScale: {
        borderColor: '#e2e8f0',
        scaleMargins: { top: 0.1, bottom: 0.1 },
      },
      timeScale: {
        borderColor: '#e2e8f0',
        timeVisible: true,
        secondsVisible: false,
      },
      crosshair: {
        vertLine: { color: '#94a3b8', width: 1, style: 2 },
        horzLine: { color: '#94a3b8', width: 1, style: 2 },
      },
      localization: {
        timeFormatter: (time: number) => {
          return new Date(time * 1000).toLocaleDateString('en-US', {
            month: 'short',
            day: 'numeric',
          });
        },
      },
    });

    // Score line (main)
    const scoreSeries = chart.addLineSeries({
      color: '#3b82f6',
      lineWidth: 2,
      priceLineVisible: false,
      lastValueVisible: true,
      title: 'Score',
    });

    // Confidence line (secondary)
    const confSeries = chart.addLineSeries({
      color: '#94a3b8',
      lineWidth: 1,
      lineStyle: 2,
      priceLineVisible: false,
      lastValueVisible: false,
      title: 'Conf',
    });

    chartRef.current = chart;
    scoreSeriesRef.current = scoreSeries;
    confSeriesRef.current = confSeries;

    // Handle resize
    const handleResize = () => {
      if (containerRef.current && chartRef.current) {
        chartRef.current.applyOptions({ width: containerRef.current.clientWidth });
      }
    };

    window.addEventListener('resize', handleResize);

    return () => {
      window.removeEventListener('resize', handleResize);
      chart.remove();
    };
  }, []);

  // Update data
  useEffect(() => {
    if (!scoreSeriesRef.current || !confSeriesRef.current || series.length === 0) return;

    const scoreData: LineData[] = series.map(point => ({
      time: Math.floor(point.t / 1000) as UTCTimestamp,
      value: point.score,
    }));

    const confData: LineData[] = series.map(point => ({
      time: Math.floor(point.t / 1000) as UTCTimestamp,
      value: point.confidence,
    }));

    scoreSeriesRef.current.setData(scoreData);
    confSeriesRef.current.setData(confData);

    if (chartRef.current) {
      chartRef.current.timeScale().fitContent();
    }
  }, [series]);

  if (loading) {
    return (
      <div className="bg-white rounded-xl border border-slate-200 p-4">
        <div className="h-[180px] bg-slate-50 rounded animate-pulse flex items-center justify-center">
          <span className="text-sm text-slate-400">Loading chart...</span>
        </div>
      </div>
    );
  }

  if (series.length === 0) {
    return (
      <div className="bg-white rounded-xl border border-slate-200 p-4">
        <div className="h-[180px] bg-slate-50 rounded flex items-center justify-center">
          <span className="text-sm text-slate-400">No historical data available</span>
        </div>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
      <div className="px-4 py-3 border-b border-slate-100 flex items-center justify-between">
        <span className="text-sm font-semibold text-slate-800">On-Chain Score (30d)</span>
        <div className="flex items-center gap-3 text-xs">
          <div className="flex items-center gap-1">
            <span className="w-3 h-0.5 bg-blue-500 rounded" />
            <span className="text-slate-500">Score</span>
          </div>
          <div className="flex items-center gap-1">
            <span className="w-3 h-0.5 bg-slate-400 rounded" style={{ borderStyle: 'dashed' }} />
            <span className="text-slate-500">Confidence</span>
          </div>
        </div>
      </div>
      <div className="p-2">
        <div ref={containerRef} />
      </div>
    </div>
  );
}
