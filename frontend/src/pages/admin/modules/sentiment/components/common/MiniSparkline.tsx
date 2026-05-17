"use client";

import React from "react";

interface MiniSparklineProps {
  values: number[];
  color?: string;
  height?: number;
  showDots?: boolean;
  showArea?: boolean;
}

/**
 * Mini Sparkline Chart for Admin Panels
 * Clean, minimal visualization of time series data
 */
export default function MiniSparkline({ 
  values, 
  color = "rgb(59, 130, 246)", // blue-500
  height = 40,
  showDots = false,
  showArea = true,
}: MiniSparklineProps) {
  if (!values?.length || values.length < 2) {
    return (
      <div 
        className="flex items-center justify-center text-xs text-slate-400"
        style={{ height }}
      >
        No data
      </div>
    );
  }

  const max = Math.max(...values);
  const min = Math.min(...values);
  const range = max - min || 1;
  const padding = 2;

  const points = values.map((v, i) => {
    const x = padding + (i / (values.length - 1)) * (100 - padding * 2);
    const y = padding + (1 - (v - min) / range) * (100 - padding * 2);
    return { x, y, value: v };
  });

  const pathData = points.map((p, i) => `${i === 0 ? 'M' : 'L'} ${p.x} ${p.y}`).join(' ');
  
  // Area path (fill under the line)
  const areaPath = `${pathData} L ${points[points.length - 1].x} ${100 - padding} L ${padding} ${100 - padding} Z`;

  return (
    <svg 
      viewBox="0 0 100 100" 
      preserveAspectRatio="none"
      style={{ width: "100%", height }}
      className="overflow-visible"
    >
      {/* Gradient definition */}
      <defs>
        <linearGradient id={`sparkline-gradient-${color.replace(/[^a-z0-9]/gi, '')}`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={color} stopOpacity="0.3" />
          <stop offset="100%" stopColor={color} stopOpacity="0.05" />
        </linearGradient>
      </defs>

      {/* Area fill */}
      {showArea && (
        <path
          d={areaPath}
          fill={`url(#sparkline-gradient-${color.replace(/[^a-z0-9]/gi, '')})`}
        />
      )}

      {/* Line */}
      <path
        d={pathData}
        fill="none"
        stroke={color}
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
        vectorEffect="non-scaling-stroke"
      />

      {/* Dots at key points */}
      {showDots && (
        <>
          {/* First point */}
          <circle cx={points[0].x} cy={points[0].y} r="2" fill={color} />
          {/* Last point */}
          <circle 
            cx={points[points.length - 1].x} 
            cy={points[points.length - 1].y} 
            r="3" 
            fill={color}
            stroke="white"
            strokeWidth="1"
          />
        </>
      )}
    </svg>
  );
}

/**
 * Mini Bar Chart for discrete values
 */
export function MiniBarChart({ 
  values, 
  color = "rgb(59, 130, 246)",
  height = 40,
}: { 
  values: number[]; 
  color?: string;
  height?: number;
}) {
  if (!values?.length) {
    return (
      <div 
        className="flex items-center justify-center text-xs text-slate-400"
        style={{ height }}
      >
        No data
      </div>
    );
  }

  const max = Math.max(...values, 0.01);
  const barWidth = 100 / values.length;

  return (
    <svg 
      viewBox="0 0 100 100" 
      preserveAspectRatio="none"
      style={{ width: "100%", height }}
    >
      {values.map((v, i) => {
        const barHeight = (v / max) * 90;
        return (
          <rect
            key={i}
            x={i * barWidth + 1}
            y={100 - barHeight}
            width={barWidth - 2}
            height={barHeight}
            fill={color}
            opacity={0.7 + (i / values.length) * 0.3}
            rx="1"
          />
        );
      })}
    </svg>
  );
}
