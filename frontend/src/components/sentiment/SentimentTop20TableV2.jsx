/**
 * SentimentTop20Table V2 — BLOCK P1.2 + P2.3 UI
 * ==============================================
 * 
 * Displays TOP 20 crypto symbols with reliability-adjusted sentiment scores.
 * NOW USES /api/market/sentiment/top-alts-v2 with:
 * - RAW vs FINAL confidence
 * - RAW vs FINAL expected move
 * - SafeMode awareness
 * - Risk/adjustment flags
 * - P2.3: Per-row explain popover
 */

import React, { useEffect, useState } from 'react';
import { TrendingUpIcon, TrendingDownIcon, MinusIcon, RefreshCwIcon, ShieldAlert, AlertTriangle } from 'lucide-react';
import SentimentExplainPopover from './SentimentExplainPopover';

const API_URL = process.env.REACT_APP_BACKEND_URL || '';

function windowKeyToHorizon(windowKey) {
  if (windowKey === '24H' || windowKey === '1D') return '24H';
  if (windowKey === '30D') return '30D';
  return '7D';
}

export default function SentimentTop20TableV2({
  windowKey,
  onPick,
  selectedSymbol,
}) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const horizon = windowKeyToHorizon(windowKey);

  useEffect(() => {
    let alive = true;
    setLoading(true);
    setError(null);

    fetch(`${API_URL}/api/market/sentiment/top-alts-v2?horizon=${horizon}&limit=20`)
      .then(r => r.json())
      .then(res => {
        if (!alive) return;
        if (res.ok) {
          setData(res);
        } else {
          setError(res.error || 'Failed to load data');
        }
        setLoading(false);
      })
      .catch(err => {
        if (!alive) return;
        setError(err.message);
        setLoading(false);
      });

    return () => {
      alive = false;
    };
  }, [horizon]);

  const getDirectionIcon = (dir) => {
    if (dir === 'LONG') return <TrendingUpIcon className="w-3.5 h-3.5 text-emerald-500" />;
    if (dir === 'SHORT') return <TrendingDownIcon className="w-3.5 h-3.5 text-red-500" />;
    return <MinusIcon className="w-3.5 h-3.5 text-gray-400" />;
  };

  const getDirectionColor = (dir) => {
    if (dir === 'LONG') return 'text-emerald-600';
    if (dir === 'SHORT') return 'text-red-600';
    return 'text-gray-500';
  };

  const getBiasColor = (bias) => {
    if (bias > 0.3) return 'text-emerald-600 bg-emerald-50';
    if (bias < -0.3) return 'text-red-600 bg-red-50';
    if (bias > 0) return 'text-emerald-500';
    if (bias < 0) return 'text-red-500';
    return 'text-gray-500';
  };

  const getExpColor = (exp) => {
    if (exp > 0) return 'text-emerald-600';
    if (exp < 0) return 'text-red-600';
    return 'text-gray-500';
  };

  if (loading) {
    return (
      <div 
        className="bg-white rounded-xl border border-gray-200 p-4"
        data-testid="sentiment-top20-v2-loading"
      >
        <div className="flex items-center justify-between mb-3">
          <div className="text-xs font-medium text-gray-500 uppercase tracking-wide">
            TOP 20 Sentiment
          </div>
          <RefreshCwIcon className="w-4 h-4 text-gray-400 animate-spin" />
        </div>
        <div className="text-center py-8 text-gray-400 text-sm">
          Loading sentiment data...
        </div>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div 
        className="bg-white rounded-xl border border-gray-200 p-4"
        data-testid="sentiment-top20-v2-error"
      >
        <div className="flex items-center justify-between mb-3">
          <div className="text-xs font-medium text-gray-500 uppercase tracking-wide">
            TOP 20 Sentiment
          </div>
          <AlertTriangle className="w-4 h-4 text-amber-500" />
        </div>
        <div className="text-center py-8 text-gray-400 text-sm">
          {error || 'No data available'}
        </div>
      </div>
    );
  }

  const { rows, safeMode, uriLevel, activeCount } = data;

  return (
    <div 
      className="bg-white rounded-xl border border-gray-200 p-4"
      data-testid="sentiment-top20-v2-table"
    >
      {/* Header */}
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <span className="text-xs font-medium text-gray-500 uppercase tracking-wide">
            TOP 20 • {horizon}
          </span>
          {safeMode && (
            <span className="flex items-center gap-1 px-2 py-0.5 bg-amber-100 text-amber-700 text-xs font-medium rounded-full">
              <ShieldAlert className="w-3 h-3" />
              SAFE MODE
            </span>
          )}
          {!safeMode && uriLevel !== 'OK' && (
            <span className={`px-2 py-0.5 text-xs font-medium rounded-full ${
              uriLevel === 'WARN' ? 'bg-yellow-100 text-yellow-700' :
              uriLevel === 'DEGRADED' ? 'bg-orange-100 text-orange-700' :
              'bg-red-100 text-red-700'
            }`}>
              URI {uriLevel}
            </span>
          )}
        </div>
        <span className="text-xs text-gray-400">
          {activeCount} active
        </span>
      </div>

      {/* Table */}
      <div className="overflow-x-auto">
        <table className="w-full text-xs">
          <thead>
            <tr className="text-gray-400 border-b border-gray-100">
              <th className="text-left py-2 font-medium">SYMBOL</th>
              <th className="text-right py-2 font-medium">SCORE</th>
              <th className="text-right py-2 font-medium">BIAS</th>
              <th className="text-center py-2 font-medium">DIR</th>
              <th className="text-right py-2 font-medium">EXP% RAW</th>
              <th className="text-right py-2 font-medium">EXP% FINAL</th>
              <th className="text-right py-2 font-medium">CONF</th>
              <th className="text-left py-2 font-medium">FLAGS</th>
              <th className="text-center py-2 font-medium w-10"></th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr 
                key={row.symbol}
                onClick={() => onPick?.(row.symbol)}
                className={`border-b border-gray-50 cursor-pointer transition-colors ${
                  selectedSymbol === row.symbol 
                    ? 'bg-indigo-50' 
                    : 'hover:bg-gray-50'
                }`}
              >
                <td className="py-2.5 font-medium text-gray-800">
                  {row.symbol}
                </td>
                <td className="py-2.5 text-right text-gray-600">
                  {(row.score * 100).toFixed(0)}%
                </td>
                <td className={`py-2.5 text-right ${getBiasColor(row.bias)}`}>
                  {row.bias >= 0 ? '+' : ''}{row.bias.toFixed(2)}
                </td>
                <td className="py-2.5 text-center">
                  <span className={`flex items-center justify-center gap-1 ${getDirectionColor(row.direction)}`}>
                    {getDirectionIcon(row.direction)}
                    <span className="sr-only">{row.direction}</span>
                  </span>
                </td>
                <td className={`py-2.5 text-right ${getExpColor(row.expectedMovePctRaw)}`}>
                  {row.expectedMovePctRaw >= 0 ? '+' : ''}{row.expectedMovePctRaw.toFixed(2)}%
                </td>
                <td className={`py-2.5 text-right font-medium ${getExpColor(row.expectedMovePctFinal)}`}>
                  {row.expectedMovePctFinal >= 0 ? '+' : ''}{row.expectedMovePctFinal.toFixed(2)}%
                </td>
                <td className="py-2.5 text-right">
                  <span className="text-gray-400">
                    {(row.confidenceRaw * 100).toFixed(0)}%
                  </span>
                  {row.confidenceFinal !== row.confidenceRaw && (
                    <span className="text-indigo-500 ml-1">
                      → {(row.confidenceFinal * 100).toFixed(0)}%
                    </span>
                  )}
                </td>
                <td className="py-2.5 text-left">
                  <div className="flex flex-wrap gap-1">
                    {row.flags.map((flag, i) => (
                      <span 
                        key={i}
                        className={`px-1.5 py-0.5 text-[10px] font-medium rounded ${
                          flag === 'SAFE_MODE' ? 'bg-amber-100 text-amber-700' :
                          flag === 'URI_ADJ' ? 'bg-indigo-100 text-indigo-700' :
                          flag === 'CALIBRATED' ? 'bg-blue-100 text-blue-700' :
                          flag === 'LOW_DATA' ? 'bg-gray-100 text-gray-500' :
                          'bg-gray-100 text-gray-600'
                        }`}
                      >
                        {flag}
                      </span>
                    ))}
                  </div>
                </td>
                <td className="py-2.5 text-center" onClick={(e) => e.stopPropagation()}>
                  <SentimentExplainPopover explain={row.explain} symbol={row.symbol} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Footer info */}
      {safeMode && (
        <div className="mt-3 p-2 bg-amber-50 rounded-lg text-xs text-amber-700">
          <strong>Safe Mode Active:</strong> All predictions are set to NEUTRAL due to low data reliability (URI: {uriLevel}).
        </div>
      )}
    </div>
  );
}
