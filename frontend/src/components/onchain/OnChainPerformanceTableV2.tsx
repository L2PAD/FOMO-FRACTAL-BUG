/**
 * OnChain Performance Table V2
 * =============================
 * 
 * BLOCK O9.5: Historical performance table for OnChain signals
 * Shows recent observations with governance states
 * 
 * Features:
 * - Recent observations list
 * - Score/Confidence over time
 * - State badges
 * - Guardrail indicators
 */

import { useState, useEffect } from 'react';
import { OnchainPoint, GuardrailState, FinalState } from '../../lib/onchain/types';
import { formatGuardrailState, formatConfidence, biasLabel } from '../../lib/onchain/analytics';

const API_URL = process.env.REACT_APP_BACKEND_URL || '';

// State badge styling
const STATE_STYLES: Record<FinalState | string, string> = {
  ACCUMULATION: 'bg-emerald-100 text-emerald-700',
  DISTRIBUTION: 'bg-red-100 text-red-700',
  NEUTRAL: 'bg-slate-100 text-slate-600',
  SAFE: 'bg-amber-100 text-amber-700',
  NO_DATA: 'bg-gray-100 text-gray-500',
};

interface Props {
  symbol?: string;
  window?: string;
  limit?: number;
}

export default function OnChainPerformanceTableV2({ 
  symbol = 'ETH', 
  window = '30d',
  limit = 10 
}: Props) {
  const [points, setPoints] = useState<OnchainPoint[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    setError(null);

    fetch(`${API_URL}/api/v10/onchain-v2/chart/${symbol}?window=${window}`)
      .then(res => res.json())
      .then(json => {
        if (json.ok && json.points) {
          // Take last N points, reversed (newest first)
          const recent = json.points.slice(-limit).reverse();
          setPoints(recent);
        }
        setLoading(false);
      })
      .catch(err => {
        console.error('[OnChainPerformance] Error:', err);
        setError(err.message);
        setLoading(false);
      });
  }, [symbol, window, limit]);

  if (loading) {
    return (
      <div className="bg-white rounded-xl border border-gray-200 p-4">
        <div className="animate-pulse">
          <div className="h-4 bg-gray-100 rounded w-40 mb-4" />
          <div className="space-y-2">
            {[1, 2, 3].map(i => (
              <div key={i} className="h-8 bg-gray-50 rounded" />
            ))}
          </div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-white rounded-xl border border-gray-200 p-4">
        <p className="text-sm text-red-600">Error loading performance data</p>
      </div>
    );
  }

  if (!points.length) {
    return (
      <div className="bg-white rounded-xl border border-gray-200 p-4">
        <p className="text-sm text-gray-500">No historical data available</p>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-xl border border-gray-200 overflow-hidden" data-testid="onchain-performance-table">
      {/* Header */}
      <div className="px-4 py-3 border-b border-gray-100">
        <h3 className="font-semibold text-gray-900">OnChain Signal History</h3>
        <p className="text-xs text-gray-500 mt-0.5">Last {limit} observations for {symbol}</p>
      </div>

      {/* Table */}
      <div className="overflow-x-auto">
        <table className="w-full">
          <thead>
            <tr className="bg-slate-50 text-xs text-gray-500 uppercase">
              <th className="px-4 py-2 text-left font-medium">Time</th>
              <th className="px-4 py-2 text-left font-medium">State</th>
              <th className="px-4 py-2 text-right font-medium">Score</th>
              <th className="px-4 py-2 text-right font-medium">Confidence</th>
              <th className="px-4 py-2 text-right font-medium">Guardrail</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {points.map((point, i) => {
              const date = new Date(point.t);
              const state = point.state || biasLabel(point.score).toUpperCase().replace('ING', '');
              const guardrail = formatGuardrailState(point.guardrailState || 'HEALTHY');
              
              return (
                <tr key={i} className="text-sm hover:bg-slate-50 transition-colors">
                  <td className="px-4 py-2.5">
                    <div className="text-gray-900 font-medium">
                      {date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}
                    </div>
                    <div className="text-xs text-gray-400">
                      {date.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' })}
                    </div>
                  </td>
                  <td className="px-4 py-2.5">
                    <span className={`inline-flex px-2 py-0.5 rounded text-xs font-medium ${
                      STATE_STYLES[state] || STATE_STYLES.NEUTRAL
                    }`}>
                      {state}
                    </span>
                  </td>
                  <td className="px-4 py-2.5 text-right">
                    <span className={`font-medium tabular-nums ${
                      point.score >= 0.62 ? 'text-emerald-600' :
                      point.score <= 0.38 ? 'text-red-600' : 'text-gray-700'
                    }`}>
                      {Math.round(point.score * 100)}
                    </span>
                  </td>
                  <td className="px-4 py-2.5 text-right">
                    <span className={`tabular-nums ${
                      point.confidence < 0.4 ? 'text-amber-600' :
                      point.confidence < 0.7 ? 'text-gray-600' : 'text-emerald-600'
                    }`}>
                      {formatConfidence(point.confidence)}
                    </span>
                  </td>
                  <td className="px-4 py-2.5 text-right">
                    <span className={`inline-flex px-1.5 py-0.5 rounded text-[10px] font-medium ${guardrail.color}`}>
                      {guardrail.label}
                    </span>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {/* Legend */}
      <div className="px-4 py-2.5 bg-slate-50 border-t border-gray-100">
        <div className="flex flex-wrap gap-4 text-[10px] text-gray-500">
          <span><span className="inline-block w-2 h-2 rounded bg-emerald-500 mr-1" />Score ≥62 = Accumulating</span>
          <span><span className="inline-block w-2 h-2 rounded bg-red-500 mr-1" />Score ≤38 = Distributing</span>
          <span><span className="inline-block w-2 h-2 rounded bg-slate-400 mr-1" />38-62 = Neutral</span>
        </div>
      </div>
    </div>
  );
}
