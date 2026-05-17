/**
 * MetaBrainForecastTable — Prediction Table
 *
 * Displays forecast predictions per day, matching the style
 * of the Exchange prediction table. Shows day labels
 * (Yesterday/Today/Tomorrow), targets, confidence, and status.
 *
 * Row count depends on horizon:
 * - 1D: 3 rows (yesterday + today + tomorrow)
 * - 7D: 9 rows (+ 6 pending days)
 * - 30D: 32 rows (+ 27 pending days, scrollable)
 */
import React, { useEffect, useState, useCallback } from 'react';
import { Loader2, Info } from 'lucide-react';

const API_URL = process.env.REACT_APP_BACKEND_URL || '';

const DAY_BADGE_COLORS = {
  Yesterday: 'bg-gray-100 text-gray-600',
  Today: 'bg-blue-50 text-blue-600',
  Tomorrow: 'bg-violet-50 text-violet-600',
};

const STATUS_COLORS = {
  Hit: 'bg-emerald-50 text-emerald-600',
  Miss: 'bg-red-50 text-red-500',
  'Missed opp': 'bg-orange-50 text-orange-500',
  Pending: 'bg-gray-50 text-gray-400',
};

export default function MetaBrainForecastTable({ asset = 'BTC', horizonDays = 7 }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API_URL}/api/meta-brain-v2/forecast-table?asset=${asset}&horizonDays=${horizonDays}`);
      const json = await res.json();
      if (json.ok) setData(json);
    } catch (e) {
      console.error('[ForecastTable] error:', e);
    } finally {
      setLoading(false);
    }
  }, [asset, horizonDays]);

  useEffect(() => { fetchData(); }, [fetchData]);

  if (loading && !data) {
    return (
      <div className="flex items-center justify-center py-10 bg-white rounded-xl border border-gray-100" data-testid="meta-forecast-table-loading">
        <Loader2 className="w-5 h-5 animate-spin text-gray-400" />
      </div>
    );
  }

  if (!data || !data.rows?.length) {
    return (
      <div className="p-6 bg-white border border-gray-100 rounded-xl text-center text-sm text-gray-400" data-testid="meta-forecast-table-empty">
        No forecast data available
      </div>
    );
  }

  const { summary, rows: rawRows } = data;

  // Deduplicate: collapse consecutive pending rows with same target+direction into ranges
  const rows = [];
  for (let i = 0; i < rawRows.length; i++) {
    const row = rawRows[i];
    if (!row.hasData || row.dayLabel) {
      // Keep special rows (Yesterday, Today, Tomorrow) and empty rows as-is
      rows.push(row);
      continue;
    }
    // Check if this pending row matches the previous pending row
    const prev = rows.length > 0 ? rows[rows.length - 1] : null;
    if (
      prev && prev.hasData && !prev.dayLabel &&
      prev.target === row.target &&
      prev.direction === row.direction &&
      prev.status === row.status
    ) {
      // Merge: update the date range on previous row
      if (!prev._endDate) prev._endDate = row.date;
      else prev._endDate = row.date;
      continue;
    }
    rows.push({ ...row });
  }

  // Find divider index: first row without data after the header rows
  const pendingStart = rows.findIndex((r, i) => !r.hasData && i > 2);

  return (
    <div className="border border-gray-100 rounded-xl overflow-hidden bg-white" data-testid="meta-forecast-table">
      {/* Summary bar */}
      <div className="px-5 py-3 border-b border-gray-100 bg-gray-50/80 flex items-center gap-5 text-sm">
        <span className="text-gray-500">
          Win Rate{' '}
          <span className={`font-semibold ${(summary?.winRate ?? 0) >= 50 ? 'text-emerald-600' : 'text-red-500'}`}>
            {summary?.winRate ?? 0}%
          </span>
        </span>
        <span className="text-gray-500">
          Avg Return{' '}
          <span className="font-semibold text-emerald-600">+{(summary?.avgReturn ?? 0).toFixed(2)}%</span>
        </span>
        <span className="text-gray-500">
          Evaluated{' '}
          <span className="font-medium text-gray-700">{summary?.evaluated ?? 0}</span>
        </span>
      </div>

      {/* Table */}
      <div className={horizonDays > 7 ? 'max-h-[400px] overflow-y-auto' : ''}>
        <table className="w-full text-sm">
          <thead className="bg-gray-50/50 border-b border-gray-100 sticky top-0 z-10">
            <tr className="text-gray-400 text-left text-xs font-semibold">
              <th className="px-5 py-2.5">Day</th>
              <th className="px-4 py-2.5">Eval At</th>
              <th className="px-4 py-2.5">Dir</th>
              <th className="px-4 py-2.5 text-right">Target</th>
              <th className="px-4 py-2.5 text-right">Conf</th>
              <th className="px-4 py-2.5 text-right">Status</th>
            </tr>
          </thead>
          <tbody>
            {rows.filter(r => r.hasData).map((row, idx) => (
              <React.Fragment key={idx}>
                {/* Pending divider */}
                {idx === pendingStart && pendingStart > 0 && (
                  <tr>
                    <td colSpan={6} className="px-5 py-2 text-xs text-gray-400 bg-gray-50/50 border-t border-gray-100">
                      Pending — {rows.filter(r => r.hasData && r.status === 'Pending').length} forecasts awaiting evaluation
                    </td>
                  </tr>
                )}
                <tr
                  className={`border-b border-gray-50 hover:bg-blue-50/20 transition-colors ${!row.hasData ? 'opacity-40' : ''}`}
                  data-testid={`meta-forecast-row-${idx}`}
                >
                  {/* Day */}
                  <td className="px-5 py-3">
                    {row.dayLabel ? (
                      <span className={`text-xs font-medium px-2.5 py-1 rounded-md ${DAY_BADGE_COLORS[row.dayLabel] || 'bg-gray-100 text-gray-500'}`}>
                        {row.dayLabel}
                      </span>
                    ) : null}
                  </td>
                  {/* Eval At */}
                  <td className="px-4 py-3 text-gray-600 text-xs">
                    {row.date}
                    {row._endDate && <span className="text-gray-400"> — {row._endDate}</span>}
                  </td>
                  {/* Direction */}
                  <td className="px-4 py-3">
                    {row.hasData ? (
                      <span className={`text-xs font-medium ${
                        row.direction === 'LONG' ? 'text-emerald-600' :
                        row.direction === 'SHORT' ? 'text-red-500' :
                        'text-gray-500'
                      }`}>
                        {row.direction}
                      </span>
                    ) : <span className="text-gray-300 text-xs">—</span>}
                  </td>
                  {/* Target */}
                  <td className="px-4 py-3 text-right text-xs font-mono text-gray-700">
                    {row.hasData && row.target != null ? `$${row.target.toLocaleString()}` : <span className="text-gray-300">—</span>}
                  </td>
                  {/* Confidence */}
                  <td className="px-4 py-3 text-right text-xs text-gray-500">
                    {row.hasData && row.confidence != null ? `${row.confidence}%` : <span className="text-gray-300">—</span>}
                  </td>
                  {/* Status */}
                  <td className="px-4 py-3 text-right">
                    {row.hasData ? (
                      <span className={`text-xs font-medium px-2 py-0.5 rounded ${STATUS_COLORS[row.status] || 'bg-gray-50 text-gray-400'}`}>
                        {row.status}
                      </span>
                    ) : <span className="text-gray-300 text-xs">—</span>}
                  </td>
                </tr>
              </React.Fragment>
            ))}
          </tbody>
        </table>
      </div>

      {loading && data && (
        <div className="absolute inset-0 bg-white/50 flex items-center justify-center">
          <Loader2 className="w-4 h-4 animate-spin text-gray-400" />
        </div>
      )}
    </div>
  );
}
