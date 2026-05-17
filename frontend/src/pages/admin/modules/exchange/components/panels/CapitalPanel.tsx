/**
 * Capital Panel
 * ==============
 * 

 */

import React from 'react';
import Card from '../Card';
import StatusBadge from '../StatusBadge';
import MiniSparkline from '../common/MiniSparkline';
import { ExchangeAdminSnapshot } from '../../types/exchangeAdmin.types';

interface CapitalPanelProps {
  snapshot: ExchangeAdminSnapshot;
}

function fmtPct(x?: number): string {
  if (x === undefined || x === null || !Number.isFinite(x)) return '—';
  return `${(x * 100).toFixed(2)}%`;
}

export default function CapitalPanel({ snapshot }: CapitalPanelProps) {
  const c = snapshot.capital;

  return (
    <Card title="Capital Health (30D)" right={<StatusBadge level={c.level} />}>
      <div className="flex gap-4">
        <div className="flex-1 grid grid-cols-2 gap-2 text-sm">
          <div>
            <div className="text-gray-500 text-xs">Trades</div>
            <div className="font-semibold text-gray-900">{c.trades30d}</div>
          </div>
          <div>
            <div className="text-gray-500 text-xs">Return</div>
            <div className={`font-semibold ${c.return30d >= 0 ? 'text-green-600' : 'text-red-600'}`}>
              {fmtPct(c.return30d)}
            </div>
          </div>
          <div>
            <div className="text-gray-500 text-xs">Win Rate</div>
            <div className="font-semibold text-gray-900">{fmtPct(c.winRate)}</div>
          </div>
          <div>
            <div className="text-gray-500 text-xs">Expectancy</div>
            <div className="font-semibold text-gray-900">{fmtPct(c.expectancy)}</div>
          </div>
          <div>
            <div className="text-gray-500 text-xs">Max DD</div>
            <div className="font-semibold text-red-600">{fmtPct(c.maxDD)}</div>
          </div>
          <div>
            <div className="text-gray-500 text-xs">Sharpe</div>
            <div className="font-semibold text-gray-900">{c.sharpe?.toFixed(2) ?? '—'}</div>
          </div>
          <div>
            <div className="text-gray-500 text-xs">Equity</div>
            <div className="font-semibold text-gray-900">{c.equity?.toFixed(2) ?? '—'}</div>
          </div>
        </div>

        <div className="flex flex-col items-end">
          <MiniSparkline 
            points={c.recentEquity ?? []} 
            color={c.return30d >= 0 ? 'rgba(16, 185, 129, 0.8)' : 'rgba(239, 68, 68, 0.8)'} 
          />
          <div className="text-xs text-gray-500 mt-1">30D equity trend</div>
        </div>
      </div>

      <div className="mt-3 pt-3">
        <div className="flex items-center justify-between">
          <span className="text-sm text-gray-600">Promotion Eligible</span>
          <span className={`font-semibold ${c.gates.promotionEligible ? 'text-green-600' : 'text-red-600'}`}>
            {c.gates.promotionEligible ? 'YES' : 'NO'}
          </span>
        </div>
        {c.gates.reasons.length > 0 && (
          <div className="mt-2 flex flex-wrap gap-1">
            {c.gates.reasons.map((r, i) => (
              <span key={i} className="px-2 py-0.5 bg-red-50 text-red-600 rounded text-xs">
                {r}
              </span>
            ))}
          </div>
        )}
      </div>

      <div className="mt-2 text-xs text-gray-500">
        Gates: Exp &gt; 0%, MaxDD &lt; 15%, Sharpe &gt; 0.10, URI &gt; 60%
      </div>
    </Card>
  );
}
