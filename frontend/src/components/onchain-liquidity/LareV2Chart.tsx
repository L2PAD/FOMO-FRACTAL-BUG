/**
 * LARE v2 Chart
 * ==============
 * 
 * PHASE 3: Score history with regime zones
 * - Green zone: >65 (Risk On)
 * - Red zone: <35 (Risk Off)  
 * - Timeframe filtering: 1D/7D/30D
 */

import React, { useMemo } from 'react';
import type { LareV2SeriesPoint } from './useLareV2';

interface Props {
  series: LareV2SeriesPoint[];
  range?: '1d' | '7d' | '30d';
}

export function LareV2Chart({ series, range = '30d' }: Props) {
  // Chart dimensions
  const width = 100;
  const height = 60;
  const padding = { top: 2, right: 2, bottom: 2, left: 2 };

  const chartWidth = width - padding.left - padding.right;
  const chartHeight = height - padding.top - padding.bottom;

  // Filter series by range
  const filteredSeries = useMemo(() => {
    if (!series || series.length === 0) return [];
    
    const now = Date.now();
    const rangeMs = range === '1d' ? 24 * 60 * 60 * 1000 :
                   range === '7d' ? 7 * 24 * 60 * 60 * 1000 :
                   30 * 24 * 60 * 60 * 1000;
    
    const cutoff = now - rangeMs;
    return series.filter(p => p.t >= cutoff);
  }, [series, range]);

  // Calculate path
  const path = useMemo(() => {
    if (!filteredSeries || filteredSeries.length < 2) return '';

    const minT = filteredSeries[0].t;
    const maxT = filteredSeries[filteredSeries.length - 1].t;
    const timeRange = maxT - minT || 1;

    const points = filteredSeries.map((p, i) => {
      const x = padding.left + ((p.t - minT) / timeRange) * chartWidth;
      const y = padding.top + (1 - p.score / 100) * chartHeight;
      return `${i === 0 ? 'M' : 'L'} ${x} ${y}`;
    });

    return points.join(' ');
  }, [filteredSeries, chartWidth, chartHeight]);

  // No data — don't render
  if (!filteredSeries || filteredSeries.length === 0) {
    return null;
  }

  // Score line color
  const currentScore = filteredSeries[filteredSeries.length - 1].score;
  const lineColor = currentScore >= 65 ? '#4ade80' : 
                    currentScore >= 55 ? '#a3e635' : 
                    currentScore >= 45 ? '#fbbf24' : 
                    currentScore >= 35 ? '#fb923c' : '#f87171';

  return (
    <div className="rounded-xl border border-white/10 bg-white/[0.03] p-4" data-testid="lare-v2-chart">
      <div className="relative" style={{ height: '140px' }}>
        {/* Background zones — лёгкая заливка */}
        <div className="absolute inset-0 flex flex-col rounded-lg overflow-hidden">
          <div className="h-[35%] bg-green-500/[0.08]" />
          <div className="h-[30%] bg-transparent" />
          <div className="h-[35%] bg-red-500/[0.08]" />
        </div>

        {/* Threshold lines — 65 и 35 */}
        <div 
          className="absolute left-0 right-0 border-t border-dashed border-green-500/40" 
          style={{ top: '35%' }} 
        />
        <div 
          className="absolute left-0 right-0 border-t border-dashed border-red-500/40" 
          style={{ top: '65%' }} 
        />

        {/* SVG Chart */}
        <svg 
          viewBox={`0 0 ${width} ${height}`} 
          className="absolute inset-0 w-full h-full"
          preserveAspectRatio="none"
        >
          <path
            d={path}
            fill="none"
            stroke={lineColor}
            strokeWidth="1"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>

        {/* Zone labels — контрастнее */}
        <div className="absolute right-2 top-2 text-xs font-medium text-green-400/70">65</div>
        <div className="absolute right-2 bottom-2 text-xs font-medium text-red-400/70">35</div>
      </div>
    </div>
  );
}
