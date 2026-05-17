/**
 * Data Health Panel
 * ==================
 * 

 */

import React from 'react';
import Card from '../Card';
import StatusBadge from '../StatusBadge';
import { ExchangeAdminSnapshot } from '../../types/exchangeAdmin.types';

interface DataHealthPanelProps {
  snapshot: ExchangeAdminSnapshot;
}

function formatTime(iso?: string): string {
  if (!iso) return '—';
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleString();
}

export default function DataHealthPanel({ snapshot }: DataHealthPanelProps) {
  const d = snapshot.dataHealth;

  return (
    <Card title="Data Provider Health" right={<StatusBadge level={d.level} />}>
      <div className="grid grid-cols-2 gap-4 text-sm">
        <div>
          <div className="text-gray-500 text-xs">Provider</div>
          <div className="font-medium text-gray-900">{d.provider || '—'}</div>
        </div>
        <div>
          <div className="text-gray-500 text-xs">Last Candle</div>
          <div className="font-medium text-gray-900">{formatTime(d.lastCandleAt)}</div>
        </div>
        <div>
          <div className="text-gray-500 text-xs">Lag (sec)</div>
          <div className="font-medium text-gray-900">{d.candlesLagSec ?? '—'}</div>
        </div>
        <div>
          <div className="text-gray-500 text-xs">Coverage</div>
          <div className="font-medium text-gray-900">{d.coveragePct ?? '—'}%</div>
        </div>
        <div>
          <div className="text-gray-500 text-xs">Fetch Errors (24h)</div>
          <div className={`font-medium ${(d.fetchErrors24h ?? 0) > 0 ? 'text-red-600' : 'text-gray-900'}`}>
            {d.fetchErrors24h ?? 0}
          </div>
        </div>
      </div>
      
      {d.reasons.length > 0 && (
        <div className="mt-3 pt-3">
          <div className="text-xs text-gray-500 mb-1">Status Reasons:</div>
          <div className="flex flex-wrap gap-1">
            {d.reasons.map((r, i) => (
              <span key={i} className="text-xs text-gray-600">
                {r}
              </span>
            ))}
          </div>
        </div>
      )}
    </Card>
  );
}
