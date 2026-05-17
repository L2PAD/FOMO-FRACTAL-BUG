/**
 * MiniFlowChart Component
 * ========================
 * 
 * PHASE 4.2: Lightweight SVG mini chart for flow history
 * Shows DEX+CEX+Whale net flow as dots
 */

import React from 'react';

interface FlowPoint {
  ts?: string;
  dexNetUsd?: number;
  cexNetUsd?: number;
  whaleNetUsd?: number;
}

interface MiniFlowChartProps {
  data: FlowPoint[];
  height?: number;
}

export function MiniFlowChart({ data, height = 80 }: MiniFlowChartProps) {
  if (!data || data.length < 2) {
    return (
      <div className="flex items-center justify-center h-20 text-gray-400 text-sm">
        No series data
      </div>
    );
  }

  const series = data.map((x) =>
    (x.dexNetUsd || 0) + (x.cexNetUsd || 0) + (x.whaleNetUsd || 0)
  );

  const max = Math.max(...series.map(Math.abs)) || 1;
  const width = data.length;

  // Calculate line path
  const points = series.map((v, i) => {
    const x = (i / (data.length - 1)) * 100;
    const y = 50 - (v / max) * 40;
    return `${x},${y}`;
  }).join(' ');

  return (
    <div className="relative w-full" style={{ height }}>
      <svg 
        viewBox={`0 0 100 100`} 
        className="w-full h-full"
        preserveAspectRatio="none"
      >
        {/* Zero line */}
        <line 
          x1="0" y1="50" x2="100" y2="50" 
          stroke="rgba(156,163,175,0.3)" 
          strokeWidth="0.5"
          strokeDasharray="2,2"
        />
        
        {/* Gradient fill */}
        <defs>
          <linearGradient id="flowGradientPos" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="rgba(34,197,94,0.3)" />
            <stop offset="100%" stopColor="rgba(34,197,94,0)" />
          </linearGradient>
          <linearGradient id="flowGradientNeg" x1="0" y1="1" x2="0" y2="0">
            <stop offset="0%" stopColor="rgba(239,68,68,0.3)" />
            <stop offset="100%" stopColor="rgba(239,68,68,0)" />
          </linearGradient>
        </defs>
        
        {/* Line */}
        <polyline
          points={points}
          fill="none"
          stroke="url(#flowLineGradient)"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
          vectorEffect="non-scaling-stroke"
        />
        
        {/* Dots */}
        {series.map((v, i) => {
          const x = (i / (data.length - 1)) * 100;
          const y = 50 - (v / max) * 40;
          const color = v >= 0 ? 'rgb(34,197,94)' : 'rgb(239,68,68)';
          
          return (
            <circle
              key={i}
              cx={x}
              cy={y}
              r={i === series.length - 1 ? 3 : 1.5}
              fill={color}
              opacity={i === series.length - 1 ? 1 : 0.6}
            />
          );
        })}
        
        {/* Dynamic line gradient */}
        <defs>
          <linearGradient id="flowLineGradient" x1="0" y1="0" x2="1" y2="0">
            {series.map((v, i) => (
              <stop
                key={i}
                offset={`${(i / (series.length - 1)) * 100}%`}
                stopColor={v >= 0 ? 'rgb(34,197,94)' : 'rgb(239,68,68)'}
              />
            ))}
          </linearGradient>
        </defs>
      </svg>
      
      {/* Legend */}
      <div className="absolute bottom-0 left-0 right-0 flex justify-between text-xs text-gray-400 px-1">
        <span>{data.length} points</span>
        <span className={series[series.length - 1] >= 0 ? 'text-green-500' : 'text-red-500'}>
          {formatCompact(series[series.length - 1])}
        </span>
      </div>
    </div>
  );
}

function formatCompact(n: number): string {
  const abs = Math.abs(n);
  const sign = n >= 0 ? '+' : '-';
  if (abs >= 1e6) return `${sign}$${(abs / 1e6).toFixed(1)}M`;
  if (abs >= 1e3) return `${sign}$${(abs / 1e3).toFixed(0)}K`;
  return `${sign}$${abs.toFixed(0)}`;
}

export default MiniFlowChart;
