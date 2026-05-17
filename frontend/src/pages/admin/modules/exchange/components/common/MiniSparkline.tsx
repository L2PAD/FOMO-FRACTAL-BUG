/**
 * Mini Sparkline Component
 * =========================
 * 
 * BLOCK E6: SVG sparkline for trends (PSI, Equity)
 */

import React from 'react';

interface MiniSparklineProps {
  points: number[];
  width?: number;
  height?: number;
  color?: string;
}

export default function MiniSparkline({ 
  points, 
  width = 140, 
  height = 36,
  color = 'rgba(59, 130, 246, 0.8)',
}: MiniSparklineProps) {
  const safe = (points ?? []).filter((x) => Number.isFinite(x));
  
  if (safe.length < 2) {
    return (
      <div 
        style={{ width, height }} 
        className="bg-gray-100 rounded-lg flex items-center justify-center"
      >
        <span className="text-xs text-gray-400">No data</span>
      </div>
    );
  }

  const min = Math.min(...safe);
  const max = Math.max(...safe);
  const span = Math.max(1e-9, max - min);

  const toXY = (v: number, i: number) => {
    const x = (i / (safe.length - 1)) * (width - 8) + 4;
    const y = (1 - (v - min) / span) * (height - 8) + 4;
    return { x, y };
  };

  const d = safe
    .map((v, i) => {
      const { x, y } = toXY(v, i);
      return `${i === 0 ? 'M' : 'L'} ${x.toFixed(2)} ${y.toFixed(2)}`;
    })
    .join(' ');

  return (
    <svg width={width} height={height} className="block">
      <rect
        x="0"
        y="0"
        width={width}
        height={height}
        rx="8"
        fill="rgba(0,0,0,0.03)"
      />
      <path d={d} fill="none" stroke={color} strokeWidth="2" strokeLinecap="round" />
    </svg>
  );
}
