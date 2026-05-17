/**
 * URI Panel
 * ==========
 * 

 */

import React from 'react';
import Card from '../Card';
import StatusBadge from '../StatusBadge';
import { ExchangeAdminSnapshot, ReliabilityLevel } from '../../types/exchangeAdmin.types';

interface UriPanelProps {
  snapshot: ExchangeAdminSnapshot;
}

function ComponentRow({ label, score, level }: { label: string; score: number; level: ReliabilityLevel }) {
  const pct = Math.round(score * 100);
  const barColor = 
    level === 'OK' ? 'bg-emerald-500' :
    level === 'WARN' ? 'bg-amber-500' :
    level === 'DEGRADED' ? 'bg-orange-500' :
    level === 'CRITICAL' ? 'bg-red-500' : 'bg-gray-400';

  return (
    <div className="flex items-center gap-3">
      <div className="w-28 text-sm text-gray-600">{label}</div>
      <div className="flex-1 h-2 bg-gray-100 rounded-full overflow-hidden">
        <div className={`h-full ${barColor} rounded-full transition-all`} style={{ width: `${pct}%` }} />
      </div>
      <div className="w-12 text-right text-sm font-medium text-gray-900">{pct}%</div>
      <StatusBadge level={level} />
    </div>
  );
}

export default function UriPanel({ snapshot }: UriPanelProps) {
  const { uri } = snapshot;
  const c = uri.components;

  return (
    <Card title="Unified Reliability Index (URI)" right={<StatusBadge level={uri.uriLevel} />}>
      {/* URI Score Gauge */}
      <div className="flex items-center gap-4 mb-4">
        <div className="relative w-24 h-24">
          <svg className="w-24 h-24 -rotate-90" viewBox="0 0 100 100">
            <circle cx="50" cy="50" r="40" fill="none" stroke="#e5e7eb" strokeWidth="12" />
            <circle 
              cx="50" cy="50" r="40" 
              fill="none" 
              stroke={
                uri.uriLevel === 'OK' ? '#10b981' :
                uri.uriLevel === 'WARN' ? '#f59e0b' :
                uri.uriLevel === 'DEGRADED' ? '#f97316' : '#ef4444'
              }
              strokeWidth="12"
              strokeDasharray={`${uri.uriScore * 251.2} 251.2`}
              strokeLinecap="round"
            />
          </svg>
          <div className="absolute inset-0 flex items-center justify-center">
            <span className="text-2xl font-bold text-gray-900">{Math.round(uri.uriScore * 100)}%</span>
          </div>
        </div>
        <div className="flex-1 space-y-2">
          <ComponentRow label="Data Health" score={c.dataHealth.score} level={c.dataHealth.level} />
          <ComponentRow label="Drift Health" score={c.driftHealth.score} level={c.driftHealth.level} />
          <ComponentRow label="Capital Health" score={c.capitalHealth.score} level={c.capitalHealth.level} />
          <ComponentRow label="Calibration" score={c.calibrationHealth.score} level={c.calibrationHealth.level} />
        </div>
      </div>
    </Card>
  );
}
