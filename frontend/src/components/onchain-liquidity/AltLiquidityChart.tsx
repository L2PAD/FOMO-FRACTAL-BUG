/**
 * Alt Liquidity Chart
 * ====================
 * 
 * PHASE 3: LiquidityScore chart with confidence band
 */

import React, { useMemo } from 'react';
import { BarChart3 } from 'lucide-react';
import type { LiquiditySeriesPoint } from './types';
import { scoreColor } from './ui';

interface Props {
  points: LiquiditySeriesPoint[];
  height?: number;
}

function clamp(n: number, a: number, b: number) {
  return Math.max(a, Math.min(b, n));
}

export function AltLiquidityChart({ points, height = 180 }: Props) {
  const w = 600;
  const h = height;
  const padding = { top: 20, right: 10, bottom: 30, left: 40 };
  const innerW = w - padding.left - padding.right;
  const innerH = h - padding.top - padding.bottom;

  const data = useMemo(() => {
    if (!points?.length) return null;

    const xs = points.map(p => p.t);
    const minX = Math.min(...xs);
    const maxX = Math.max(...xs);
    const minY = 0;
    const maxY = 100;

    const toX = (t: number) => {
      if (maxX === minX) return padding.left;
      return padding.left + ((t - minX) / (maxX - minX)) * innerW;
    };
    
    const toY = (v: number) => {
      const vv = clamp(v, minY, maxY);
      return padding.top + innerH - ((vv - minY) / (maxY - minY)) * innerH;
    };

    // Main score line
    const scorePath = points
      .map((p, i) => `${i === 0 ? 'M' : 'L'} ${toX(p.t).toFixed(1)} ${toY(p.score).toFixed(1)}`)
      .join(' ');

    // Confidence band (±10 points based on confidence)
    const bandTop = points
      .map((p, i) => {
        const upper = Math.min(100, p.score + (p.confidence * 15));
        return `${i === 0 ? 'M' : 'L'} ${toX(p.t).toFixed(1)} ${toY(upper).toFixed(1)}`;
      })
      .join(' ');
    
    const bandBottom = points
      .slice()
      .reverse()
      .map((p, i) => {
        const lower = Math.max(0, p.score - (p.confidence * 15));
        return `L ${toX(p.t).toFixed(1)} ${toY(lower).toFixed(1)}`;
      })
      .join(' ');
    
    const bandPath = `${bandTop} ${bandBottom} Z`;

    // Get latest score for color
    const latestScore = points[points.length - 1]?.score ?? 50;

    // Y-axis grid lines
    const yGridLines = [0, 25, 50, 75, 100].map(v => ({
      y: toY(v),
      label: v.toString(),
    }));

    // X-axis dates
    const startDate = new Date(minX);
    const endDate = new Date(maxX);

    return { 
      scorePath, 
      bandPath, 
      latestScore,
      yGridLines,
      startDate,
      endDate,
      toX,
      toY,
    };
  }, [points, innerW, innerH]);

  if (!points?.length || !data) {
    return (
      <div className="rounded-xl border border-white/10 bg-white/5 backdrop-blur-sm p-5">
        <div className="flex items-center gap-2 text-gray-500">
          <BarChart3 className="w-5 h-5" />
          <span>No chart data available</span>
        </div>
      </div>
    );
  }

  return (
    <div className="rounded-xl border border-white/10 bg-white/5 backdrop-blur-sm p-5">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <BarChart3 className="w-5 h-5 text-blue-400" />
          <span className="text-sm font-medium text-gray-300">Score History (30d)</span>
        </div>
        <div className="text-xs text-gray-500">
          {data.startDate.toLocaleDateString()} → {data.endDate.toLocaleDateString()}
        </div>
      </div>

      {/* Chart */}
      <svg 
        width="100%" 
        viewBox={`0 0 ${w} ${h}`} 
        className="overflow-visible"
        data-testid="liquidity-chart"
      >
        {/* Grid lines */}
        {data.yGridLines.map((line, i) => (
          <g key={i}>
            <line
              x1={padding.left}
              y1={line.y}
              x2={w - padding.right}
              y2={line.y}
              stroke="rgba(255,255,255,0.1)"
              strokeDasharray="4"
            />
            <text
              x={padding.left - 8}
              y={line.y + 4}
              textAnchor="end"
              fill="rgba(255,255,255,0.4)"
              fontSize="10"
            >
              {line.label}
            </text>
          </g>
        ))}

        {/* Reference lines */}
        <line
          x1={padding.left}
          y1={data.toY(70)}
          x2={w - padding.right}
          y2={data.toY(70)}
          stroke="rgba(34,197,94,0.3)"
          strokeDasharray="8"
        />
        <line
          x1={padding.left}
          y1={data.toY(40)}
          x2={w - padding.right}
          y2={data.toY(40)}
          stroke="rgba(239,68,68,0.3)"
          strokeDasharray="8"
        />

        {/* Confidence band */}
        <path 
          d={data.bandPath} 
          fill={`${scoreColor(data.latestScore)}15`}
          stroke="none" 
        />

        {/* Score line */}
        <path 
          d={data.scorePath} 
          fill="none" 
          stroke={scoreColor(data.latestScore)}
          strokeWidth="2.5"
          strokeLinecap="round"
          strokeLinejoin="round"
        />

        {/* Latest point marker */}
        {points.length > 0 && (
          <circle
            cx={data.toX(points[points.length - 1].t)}
            cy={data.toY(points[points.length - 1].score)}
            r="4"
            fill={scoreColor(data.latestScore)}
            stroke="white"
            strokeWidth="2"
          />
        )}
      </svg>

      {/* Legend */}
      <div className="flex items-center justify-center gap-6 mt-4 text-xs text-gray-500">
        <div className="flex items-center gap-2">
          <div className="w-3 h-0.5 bg-green-500/50" style={{ borderStyle: 'dashed' }} />
          <span>Bullish zone (70+)</span>
        </div>
        <div className="flex items-center gap-2">
          <div className="w-3 h-0.5 bg-red-500/50" style={{ borderStyle: 'dashed' }} />
          <span>Bearish zone (&lt;40)</span>
        </div>
      </div>
    </div>
  );
}
