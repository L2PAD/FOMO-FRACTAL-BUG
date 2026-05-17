/**
 * Drift Panel
 * ============
 * 

 */

import React from 'react';
import Card from '../Card';
import StatusBadge from '../StatusBadge';
import MiniSparkline from '../common/MiniSparkline';
import { ExchangeAdminSnapshot } from '../../types/exchangeAdmin.types';

interface DriftPanelProps {
  snapshot: ExchangeAdminSnapshot;
}

export default function DriftPanel({ snapshot }: DriftPanelProps) {
  const d = snapshot.drift;

  return (
    <Card title="Drift Stabilization (PSI)" right={<StatusBadge level={d.level} />}>
      <div className="flex gap-4">
        <div className="flex-1 space-y-2 text-sm">
          <div className="flex justify-between">
            <span className="text-gray-500">PSI Now</span>
            <span className="font-medium text-gray-900">{d.psiNow?.toFixed(4) ?? '—'}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-gray-500">PSI EMA</span>
            <span className="font-medium text-gray-900">{d.psiEma?.toFixed(4) ?? '—'}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-gray-500">EMA Alpha</span>
            <span className="font-medium text-gray-900">{d.emaAlpha ?? 0.2}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-gray-500">Streak (WARN/DEG/CRIT)</span>
            <span className="font-medium text-gray-900">
              {d.streakWarn ?? 0} / {d.streakDegraded ?? 0} / {d.streakCritical ?? 0}
            </span>
          </div>
          <div className="flex justify-between">
            <span className="text-gray-500">Baseline</span>
            <span className="font-medium text-gray-900">{d.lastBaselineVersion ?? '—'}</span>
          </div>
        </div>
        
        <div className="flex flex-col items-end">
          <MiniSparkline points={d.recentPsi ?? []} color="rgba(99, 102, 241, 0.8)" />
          <div className="text-xs text-gray-500 mt-1">Recent PSI trend</div>
        </div>
      </div>
      
      <div className="mt-3 pt-3 text-xs text-gray-500">
        Thresholds: OK &lt; 0.15, WARN 0.15–0.30, DEGRADED 0.30–0.50, CRITICAL &gt; 0.50
      </div>
    </Card>
  );
}
