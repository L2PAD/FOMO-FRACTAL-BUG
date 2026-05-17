/**
 * Sparkline Chart (Mini for table)
 */
import React from 'react';
import { LineChart, Line, ResponsiveContainer } from 'recharts';

export function Sparkline({ data, height = 24, width = 80, color = '#111827' }) {
  const points = (data || [])
    .map((v, i) => ({ i, v: v == null ? null : Number(v) }))
    .filter((p) => p.v != null);

  if (points.length < 2) {
    return <div style={{ height, width, minWidth: width }} />;
  }

  return (
    <div style={{ width, height, minWidth: width, minHeight: height }}>
      <ResponsiveContainer width="100%" height={height}>
        <LineChart data={points}>
          <Line
            type="monotone"
            dataKey="v"
            stroke={color}
            strokeWidth={1.6}
            dot={false}
            isAnimationActive={false}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
