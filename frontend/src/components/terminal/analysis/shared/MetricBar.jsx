/**
 * MetricBar - Visual progress bar for metrics
 */

import React from 'react';

export default function MetricBar({ label, value = 0 }) {
  const pct = Math.max(0, Math.min(100, Math.round((value || 0) * 100)));

  return (
    <div className="space-y-1">
      <div className="flex items-center justify-between text-xs">
        <span className="text-gray-400">{label}</span>
        <span className="text-white">{pct}%</span>
      </div>
      <div className="h-2 rounded bg-white/5">
        <div
          className="h-2 rounded bg-blue-500 transition-all"
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}
