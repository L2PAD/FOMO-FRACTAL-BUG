/**
 * SentimentPerformanceTable V2 — BLOCK P2.4
 * ==========================================
 * 
 * Performance table specific to Sentiment module:
 * - Shows RAW vs FINAL confidence/targets
 * - SafeMode signals marked as VOIDED
 * - Outcome tracking (TP/FP/FN/WEAK)
 */

import React, { useEffect, useState } from 'react';
import { RefreshCwIcon, TrendingUpIcon, TrendingDownIcon, MinusIcon, ShieldAlert, AlertTriangle, CheckCircle, XCircle, HelpCircle } from 'lucide-react';

const API_URL = process.env.REACT_APP_BACKEND_URL || '';

function windowKeyToHorizon(windowKey) {
  if (windowKey === '24H' || windowKey === '1D') return '24H';
  if (windowKey === '30D') return '30D';
  return '7D';
}

export default function SentimentPerformanceTableV2({
  symbol = 'BTC',
  windowKey = '24H',
  limit = 10,
}) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const horizon = windowKeyToHorizon(windowKey);

  useEffect(() => {
    let alive = true;
    setLoading(true);
    setError(null);

    fetch(`${API_URL}/api/market/sentiment/performance-v2?symbol=${symbol}&horizon=${horizon}&limit=${limit}`)
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

    return () => { alive = false; };
  }, [symbol, horizon, limit]);

  const getOutcomeIcon = (outcome) => {
    switch (outcome) {
      case 'TP':
        return <CheckCircle className="w-3.5 h-3.5 text-emerald-500" />;
      case 'FP':
        return <XCircle className="w-3.5 h-3.5 text-red-500" />;
      case 'FN':
        return <AlertTriangle className="w-3.5 h-3.5 text-orange-500" />;
      case 'WEAK':
        return <MinusIcon className="w-3.5 h-3.5 text-gray-400" />;
      case 'VOIDED':
        return <ShieldAlert className="w-3.5 h-3.5 text-amber-500" />;
      default:
        return <HelpCircle className="w-3.5 h-3.5 text-gray-300" />;
    }
  };

  const getOutcomeColor = (outcome) => {
    switch (outcome) {
      case 'TP': return 'text-emerald-600 bg-emerald-50';
      case 'FP': return 'text-red-600 bg-red-50';
      case 'FN': return 'text-orange-600 bg-orange-50';
      case 'WEAK': return 'text-gray-500 bg-gray-50';
      case 'VOIDED': return 'text-amber-600 bg-amber-50';
      default: return 'text-gray-400 bg-gray-50';
    }
  };

  const getDirectionIcon = (dir) => {
    if (dir === 'LONG') return <TrendingUpIcon className="w-3.5 h-3.5 text-emerald-500" />;
    if (dir === 'SHORT') return <TrendingDownIcon className="w-3.5 h-3.5 text-red-500" />;
    return <MinusIcon className="w-3.5 h-3.5 text-gray-400" />;
  };

  const formatPrice = (p) => {
    if (!p) return '—';
    return '$' + p.toLocaleString(undefined, { maximumFractionDigits: 0 });
  };

  const formatPct = (v) => {
    if (v === null || v === undefined) return '—';
    const pct = (v * 100).toFixed(1);
    return pct + '%';
  };

  const formatDate = (iso) => {
    const d = new Date(iso);
    return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
  };

  const formatTime = (iso) => {
    const d = new Date(iso);
    return d.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' });
  };

  if (loading) {
    return (
      <div 
        className="bg-white rounded-xl border border-gray-200 p-4"
        data-testid="sentiment-performance-v2-loading"
      >
        <div className="flex items-center justify-between mb-3">
          <div className="text-xs font-medium text-gray-500 uppercase tracking-wide">
            Sentiment Performance • {symbol}
          </div>
          <RefreshCwIcon className="w-4 h-4 text-gray-400 animate-spin" />
        </div>
        <div className="text-center py-8 text-gray-400 text-sm">
          Loading performance data...
        </div>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div 
        className="bg-white rounded-xl border border-gray-200 p-4"
        data-testid="sentiment-performance-v2-error"
      >
        <div className="flex items-center justify-between mb-3">
          <div className="text-xs font-medium text-gray-500 uppercase tracking-wide">
            Sentiment Performance • {symbol}
          </div>
          <AlertTriangle className="w-4 h-4 text-amber-500" />
        </div>
        <div className="text-center py-8 text-gray-400 text-sm">
          {error || 'No data available'}
        </div>
      </div>
    );
  }

  const { rows, summary } = data;

  // Process rows: mark SafeMode as VOIDED
  const processedRows = rows.map(row => ({
    ...row,
    outcome: row.notes?.includes('SAFE_MODE') ? 'VOIDED' : row.outcome,
  }));

  return (
    <div 
      className="bg-white rounded-xl border border-gray-200 overflow-hidden"
      data-testid="sentiment-performance-v2-table"
    >
      {/* Header */}
      <div className="px-4 py-3 border-b border-gray-100 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="text-xs font-medium text-gray-500 uppercase tracking-wide">
            Sentiment Performance • {symbol} • {horizon}
          </span>
        </div>
        <div className="flex items-center gap-4 text-xs">
          <div className="flex items-center gap-1">
            <span className="text-gray-500">Win Rate:</span>
            <span className={`font-semibold ${summary.winRate >= 0.5 ? 'text-emerald-600' : 'text-red-600'}`}>
              {formatPct(summary.winRate)}
            </span>
          </div>
          <div className="flex items-center gap-1">
            <span className="text-gray-500">Avg Δ:</span>
            <span className={`font-medium ${summary.avgReturn >= 0 ? 'text-emerald-600' : 'text-red-600'}`}>
              {formatPct(summary.avgReturn)}
            </span>
          </div>
          <div className="text-gray-400">
            {summary.wins} W / {summary.losses} L / {summary.pending} P
          </div>
        </div>
      </div>

      {/* Table */}
      <div className="overflow-x-auto">
        <table className="w-full text-xs">
          <thead>
            <tr className="text-gray-400 border-b border-gray-100 bg-gray-50">
              <th className="text-left py-2.5 px-3 font-medium">DATE</th>
              <th className="text-right py-2.5 px-3 font-medium">ENTRY</th>
              <th className="text-right py-2.5 px-3 font-medium">TARGET RAW</th>
              <th className="text-right py-2.5 px-3 font-medium">TARGET FINAL</th>
              <th className="text-center py-2.5 px-3 font-medium">DIR</th>
              <th className="text-right py-2.5 px-3 font-medium">CONF RAW</th>
              <th className="text-right py-2.5 px-3 font-medium">CONF FINAL</th>
              <th className="text-right py-2.5 px-3 font-medium">ACTUAL</th>
              <th className="text-center py-2.5 px-3 font-medium">STATUS</th>
              <th className="text-left py-2.5 px-3 font-medium">FLAGS</th>
            </tr>
          </thead>
          <tbody>
            {processedRows.map((row, idx) => (
              <tr 
                key={idx}
                className="border-b border-gray-50 hover:bg-gray-50/50"
              >
                <td className="py-2.5 px-3 font-medium text-gray-800">
                  <div>{formatDate(row.asOf)}</div>
                  <div className="text-[10px] text-gray-400">{formatTime(row.asOf)}</div>
                </td>
                <td className="py-2.5 px-3 text-right text-gray-600">
                  {formatPrice(row.entry)}
                </td>
                <td className="py-2.5 px-3 text-right text-gray-500">
                  {formatPrice(row.rawTarget)}
                </td>
                <td className={`py-2.5 px-3 text-right font-medium ${
                  row.finalTarget !== row.rawTarget ? 'text-indigo-600' : 'text-gray-600'
                }`}>
                  {formatPrice(row.finalTarget)}
                </td>
                <td className="py-2.5 px-3 text-center">
                  {getDirectionIcon(row.direction)}
                </td>
                <td className="py-2.5 px-3 text-right text-gray-500">
                  {formatPct(row.rawConfidence)}
                </td>
                <td className={`py-2.5 px-3 text-right font-medium ${
                  row.finalConfidence !== row.rawConfidence 
                    ? row.finalConfidence === 0 ? 'text-amber-600' : 'text-indigo-600'
                    : 'text-gray-600'
                }`}>
                  {formatPct(row.finalConfidence)}
                </td>
                <td className="py-2.5 px-3 text-right text-gray-600">
                  {formatPrice(row.actual)}
                </td>
                <td className="py-2.5 px-3 text-center">
                  <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium ${getOutcomeColor(row.outcome)}`}>
                    {getOutcomeIcon(row.outcome)}
                    {row.outcome}
                  </span>
                </td>
                <td className="py-2.5 px-3">
                  <div className="flex flex-wrap gap-1">
                    {row.notes?.map((note, i) => (
                      <span 
                        key={i}
                        className={`px-1.5 py-0.5 text-[10px] font-medium rounded ${
                          note === 'SAFE_MODE' ? 'bg-amber-100 text-amber-700' :
                          note === 'URI_ADJ' ? 'bg-indigo-100 text-indigo-700' :
                          note === 'CALIBRATED' ? 'bg-blue-100 text-blue-700' :
                          'bg-gray-100 text-gray-600'
                        }`}
                      >
                        {note}
                      </span>
                    ))}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Footer Legend */}
      <div className="px-4 py-2 border-t border-gray-100 bg-gray-50 flex items-center gap-4 text-[10px] text-gray-500">
        <span className="flex items-center gap-1">
          <CheckCircle className="w-3 h-3 text-emerald-500" /> TP = Correct
        </span>
        <span className="flex items-center gap-1">
          <XCircle className="w-3 h-3 text-red-500" /> FP = Wrong
        </span>
        <span className="flex items-center gap-1">
          <AlertTriangle className="w-3 h-3 text-orange-500" /> FN = Missed
        </span>
        <span className="flex items-center gap-1">
          <ShieldAlert className="w-3 h-3 text-amber-500" /> VOIDED = SafeMode
        </span>
        <span className="flex items-center gap-1">
          <MinusIcon className="w-3 h-3 text-gray-400" /> WEAK = Insignificant
        </span>
      </div>
    </div>
  );
}
