/**
 * Calibration Panel
 * ==================
 * 

 */

import React from 'react';
import Card from '../Card';
import StatusBadge from '../StatusBadge';
import { ExchangeAdminSnapshot } from '../../types/exchangeAdmin.types';

interface CalibrationPanelProps {
  snapshot: ExchangeAdminSnapshot;
}

export default function CalibrationPanel({ snapshot }: CalibrationPanelProps) {
  const c = snapshot.calibration;

  return (
    <Card title="Calibration (Beta-Binomial)" right={<StatusBadge level={c.level} />}>
      <div className="flex items-center gap-4 mb-4">
        <div>
          <div className="text-xs text-gray-500">Expected Calibration Error</div>
          <div className="text-3xl font-bold text-gray-900">
            {c.ece !== undefined ? `${(c.ece * 100).toFixed(1)}%` : '—'}
            <span className="text-sm font-normal text-gray-500 ml-1">ECE</span>
          </div>
        </div>
        <div className="text-sm text-gray-500">
          <div>Target: &lt; 5% (well-calibrated)</div>
          <div>Prior: Beta(2,2) • Updated with each finalized decision</div>
        </div>
      </div>

      {c.buckets && c.buckets.length > 0 && (
        <div className="space-y-1">
          <div className="text-xs text-gray-500 mb-2">Reliability Diagram (Buckets)</div>
          {c.buckets.map((b, i) => {
            const gap = Math.abs(b.predicted - b.actual);
            return (
              <div key={i} className="flex items-center gap-2 text-xs">
                <div className="w-20 text-gray-500">{b.range}</div>
                <div className="flex-1 flex items-center gap-1">
                  <div className="w-12 text-right text-gray-600">{(b.predicted * 100).toFixed(0)}%</div>
                  <div className="flex-1 h-3 bg-gray-100 rounded-full overflow-hidden relative">
                    <div 
                      className="absolute h-full bg-blue-200 rounded-full" 
                      style={{ width: `${b.predicted * 100}%` }} 
                    />
                    <div 
                      className={`absolute h-full rounded-full ${gap > 0.05 ? 'bg-red-400' : 'bg-emerald-400'}`}
                      style={{ width: `${b.actual * 100}%` }} 
                    />
                  </div>
                  <div className="w-12 text-gray-600">{(b.actual * 100).toFixed(0)}%</div>
                </div>
                <div className="w-10 text-right text-gray-400">n={b.samples}</div>
              </div>
            );
          })}
        </div>
      )}

      <div className="mt-3 pt-3 flex justify-between text-xs text-gray-500">
        <span>Total Samples: {c.totalSamples ?? '—'}</span>
        <span>Last Run: {c.lastRunAt ? new Date(c.lastRunAt).toLocaleString() : '—'}</span>
      </div>
    </Card>
  );
}
