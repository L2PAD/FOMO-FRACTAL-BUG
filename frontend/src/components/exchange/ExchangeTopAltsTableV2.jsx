/**
 * Exchange Top Alts Table V2
 * ===========================
 * 
 * BLOCK E5: Top altcoins with reliability-adjusted values
 * Symmetric with SentimentTop20TableV2
 * 
 * Features:
 * - Sorted by FINAL score
 * - Direction badges
 * - RAW → FINAL transformation
 * - Explain popover
 * - Reliability flags
 * - Clean light theme
 */

import { useEffect, useState } from "react";
import ExchangeExplainPopover from "./ExchangeExplainPopover";
import { getDirectionColor, formatPercent } from "./exchange-ui-adjustments";

const API_URL = process.env.REACT_APP_BACKEND_URL || '';

export default function ExchangeTopAltsTableV2({ horizon = '7D', limit = 20 }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    fetch(`${API_URL}/api/market/exchange/top-alts-v2?horizon=${horizon}&limit=${limit}`)
      .then(res => res.json())
      .then(d => {
        setData(d);
        setLoading(false);
      })
      .catch(err => {
        console.error('[ExchangeTopAltsV2] Error:', err);
        setLoading(false);
      });
  }, [horizon, limit]);

  if (loading) {
    return (
      <div className="bg-white rounded-xl border border-gray-200 p-6 animate-pulse">
        <div className="h-4 bg-gray-200 rounded w-1/4 mb-4" />
        <div className="space-y-3">
          {[...Array(5)].map((_, i) => (
            <div key={i} className="h-8 bg-gray-100 rounded" />
          ))}
        </div>
      </div>
    );
  }

  if (!data?.rows?.length) {
    return (
      <div className="bg-white rounded-xl border border-gray-200 p-6 text-center">
        <p className="text-gray-500 text-sm">No signals available</p>
      </div>
    );
  }

  const { rows, safeMode, uriLevel, activeCount } = data;

  return (
    <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
      {/* Header */}
      <div className="px-5 py-4 border-b border-gray-100 flex items-center justify-between">
        <div>
          <h3 className="font-semibold text-gray-900">Top Signals ({activeCount})</h3>
          <p className="text-xs text-gray-500 mt-0.5">
            {horizon} horizon
          </p>
        </div>
        <div className="flex items-center gap-3">
          {safeMode && (
            <span className="text-xs font-medium text-amber-800">
              SAFE MODE
            </span>
          )}
          <span className={`text-xs font-medium ${
            uriLevel === 'OK' ? 'text-green-700' :
            uriLevel === 'WARN' ? 'text-yellow-700' :
            uriLevel === 'DEGRADED' ? 'text-orange-700' :
            'text-red-700'
          }`}>
            URI: {uriLevel}
          </span>
        </div>
      </div>

      {/* Table */}
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-gray-50 text-gray-500 text-xs uppercase">
              <th className="px-4 py-3 text-left font-medium">Asset</th>
              <th className="px-4 py-3 text-left font-medium">Signal</th>
              <th className="px-4 py-3 text-right font-medium">Expected Move</th>
              <th className="px-4 py-3 text-right font-medium">Confidence</th>
              <th className="px-4 py-3 text-center font-medium">Risk Flags</th>
              <th className="px-4 py-3 text-right font-medium"></th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {rows.map((row, i) => {
              const dirColor = getDirectionColor(row.direction);
              
              return (
                <tr key={i} className="hover:bg-gray-50 transition-colors">
                  <td className="px-4 py-3">
                    <span className="font-semibold text-gray-900">{row.symbol}</span>
                  </td>
                  <td className="px-4 py-3">
                    <span 
                      className="text-xs font-medium"
                      style={{
                        color: dirColor,
                      }}
                    >
                      {row.direction}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-right">
                    <span className={row.expectedMovePctFinal >= 0 ? 'text-green-600 font-medium' : 'text-red-600 font-medium'}>
                      {row.expectedMovePctFinal >= 0 ? '+' : ''}
                      {formatPercent(row.expectedMovePctFinal)}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-right">
                    <span className="font-medium text-gray-900">
                      {Math.round(row.confidenceFinal * 100)}%
                    </span>
                  </td>
                  <td className="px-4 py-3 text-center">
                    <div className="flex items-center justify-center gap-1 flex-wrap">
                      {row.flags?.map((flag, fi) => (
                        <span 
                          key={fi}
                          className={`text-xs ${
                            flag === 'SAFE_MODE' ? 'text-amber-700' :
                            flag === 'URI_ADJ' ? 'text-blue-700' :
                            flag === 'CAPITAL_GATE' ? 'text-violet-700' :
                            'text-gray-600'
                          }`}
                        >
                          {flag}
                        </span>
                      ))}
                      {(!row.flags || row.flags.length === 0) && (
                        <span className="text-gray-400">—</span>
                      )}
                    </div>
                  </td>
                  <td className="px-4 py-3 text-right">
                    <ExchangeExplainPopover row={row} />
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
