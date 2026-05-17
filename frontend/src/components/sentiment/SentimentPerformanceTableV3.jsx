/**
 * Sentiment Forecast Performance Table V3
 * Same design as Exchange Performance Table — unified format
 * Data: /api/market/sentiment/performance-v2
 */

import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { createPortal } from 'react-dom';

const API = process.env.REACT_APP_BACKEND_URL;

const OUTCOME_STYLE = {
  TP:      { label: 'Hit',        color: '#16a34a' },
  WEAK:    { label: 'Partial',    color: '#d97706' },
  FP:      { label: 'Miss',       color: '#dc2626' },
  FN:      { label: 'Missed opp', color: '#dc2626' },
  PENDING: { label: 'Pending',    color: '#94a3b8' },
  OVERDUE: { label: 'Overdue',    color: '#b45309' },
  VOIDED:  { label: 'Voided',     color: '#94a3b8' },
  NEUTRAL: { label: 'Neutral',    color: '#64748b' },
};

const OUTCOME_TIP = {
  TP: 'Target reached — prediction hit the target price',
  WEAK: 'Correct direction, but target not reached',
  FP: 'Wrong direction — opposite move',
  FN: 'Missed opportunity — no position taken',
  PENDING: 'Horizon not expired yet — evaluation will happen later',
  OVERDUE: 'Evaluation overdue — pipeline has not processed this yet',
  VOIDED: 'Voided by safe mode or system override',
};

function Tip({ children, text }) {
  const [show, setShow] = useState(false);
  const [pos, setPos] = useState({ x: 0, y: 0 });

  const handleEnter = (e) => {
    const rect = e.currentTarget.getBoundingClientRect();
    setPos({ x: Math.min(rect.left, window.innerWidth - 220), y: rect.bottom + 4 });
    setShow(true);
  };

  return (
    <span className="cursor-help" onMouseEnter={handleEnter} onMouseLeave={() => setShow(false)}>
      {children}
      {show && createPortal(
        <div className="fixed max-w-[220px]" style={{ left: pos.x, top: pos.y, zIndex: 99999, pointerEvents: 'none' }}>
          <div className="rounded-md px-2.5 py-1.5 shadow-lg whitespace-pre-line" style={{ background: '#0f172a', color: '#e2e8f0', fontSize: 11, lineHeight: 1.4 }}>
            {text}
          </div>
        </div>,
        document.body
      )}
    </span>
  );
}

function fmt$(v) { return v ? `$${Math.round(v).toLocaleString()}` : '—'; }
function fmtDate(iso) { return new Date(iso).toLocaleDateString('en', { month: 'short', day: 'numeric' }); }

/** Get YYYY-MM-DD for a date offset from today (UTC) */
function getDateBucket(offsetDays) {
  const d = new Date();
  d.setUTCDate(d.getUTCDate() + offsetDays);
  return d.toISOString().slice(0, 10);
}

/** Find the best matching row for a given date bucket — by forecast creation date (asOf/createdAt) (null-safe) */
function findRowForDate(rows, dateBucket) {
  if (!Array.isArray(rows) || rows.length === 0) return null;
  return rows.find(r => (r && (r.createdAt || r.asOf || '')).slice(0, 10) === dateBucket) || null;
}

export default function SentimentPerformanceTableV3({ symbol = 'BTC', horizon = '7D', limit = 30 }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  const fetchData = useCallback(async () => {
    try {
      const res = await fetch(`${API}/api/market/sentiment/performance-v2?symbol=${symbol}&horizon=${horizon}&limit=${limit}`);
      if (!res.ok) throw new Error(`${res.status}`);
      const json = await res.json();
      if (json.ok) setData(json);
    } catch {}
    setLoading(false);
  }, [symbol, horizon, limit]);

  useEffect(() => { fetchData(); }, [fetchData]);

  // Compute fixed top 3 rows and remaining pending
  const { topRows, pendingRest, summary } = useMemo(() => {
    const emptySummary = { winRate: 0, avgReturn: 0, evaluated: 0, total: 0, overdue: 0, wins: 0, losses: 0 };
    if (!data) return { topRows: [], pendingRest: [], summary: emptySummary };

    const rows = Array.isArray(data?.rows) ? data.rows : [];
    const summary = (data && typeof data.summary === 'object' && data.summary) ? data.summary : emptySummary;
    const yesterdayBucket = getDateBucket(-1);
    const todayBucket = getDateBucket(0);
    const tomorrowBucket = getDateBucket(1);

    const yesterdayRow = findRowForDate(rows, yesterdayBucket);
    const todayRow = findRowForDate(rows, todayBucket);
    const tomorrowRow = findRowForDate(rows, tomorrowBucket);

    const topRows = [
      { label: 'Yesterday', bucket: yesterdayBucket, row: yesterdayRow },
      { label: 'Today',     bucket: todayBucket,     row: todayRow },
      { label: 'Tomorrow',  bucket: tomorrowBucket,  row: tomorrowRow },
    ];

    // IDs of top rows to exclude from pending list
    const topEvalDates = new Set(topRows.filter(t => t.row).map(t => t.row.evaluateAt));

    // Remaining pending rows (exclude top 3, sorted by evaluateAt ASC)
    const pendingRest = rows
      .filter(r => r && r.outcome === 'PENDING' && !topEvalDates.has(r.evaluateAt))
      .sort((a, b) => new Date(a.evaluateAt) - new Date(b.evaluateAt));

    return { topRows, pendingRest, summary };
  }, [data]);

  if (loading) return <div className="text-center py-8" style={{ color: '#94a3b8', fontSize: 13 }}>Loading...</div>;
  if (!data) return <div className="text-center py-8" style={{ color: '#94a3b8', fontSize: 13 }}>No data</div>;

  const sWinRate = Number.isFinite(summary?.winRate) ? summary.winRate : 0;
  const sAvgReturn = Number.isFinite(summary?.avgReturn) ? summary.avgReturn : 0;
  const sEvaluated = Number.isFinite(summary?.evaluated)
    ? summary.evaluated
    : ((Number.isFinite(summary?.wins) ? summary.wins : 0) + (Number.isFinite(summary?.losses) ? summary.losses : 0));
  const sTotal = Number.isFinite(summary?.total) ? summary.total : 0;
  const sOverdue = Number.isFinite(summary?.overdue) ? summary.overdue : 0;

  return (
    <div data-testid="sentiment-performance-table">
      {/* Summary bar */}
      <div className="flex items-center gap-5 mb-4 px-1" data-testid="perf-summary">
        <div className="flex items-center gap-1.5">
          <span style={{ color: '#64748b', fontSize: 12 }}>Win Rate</span>
          <span className="font-bold tabular-nums" data-testid="perf-win-rate"
            style={{ fontSize: 15, color: sWinRate >= 0.5 ? '#16a34a' : sWinRate >= 0.3 ? '#d97706' : '#dc2626' }}>
            {(sWinRate * 100).toFixed(0)}%
          </span>
        </div>
        <div className="flex items-center gap-1.5">
          <span style={{ color: '#64748b', fontSize: 12 }}>Avg Return</span>
          <span className="font-bold tabular-nums" data-testid="perf-avg-return"
            style={{ fontSize: 15, color: sAvgReturn >= 0 ? '#16a34a' : '#dc2626' }}>
            {sAvgReturn >= 0 ? '+' : ''}{(sAvgReturn * 100).toFixed(2)}%
          </span>
        </div>
        <div className="flex items-center gap-1.5">
          <span style={{ color: '#64748b', fontSize: 12 }}>Evaluated</span>
          <span className="tabular-nums" style={{ fontSize: 13, color: '#0f172a' }}>
            {sEvaluated}/{sTotal}
          </span>
        </div>
        {sOverdue > 0 && (
          <div className="flex items-center gap-1.5">
            <span style={{ color: '#b45309', fontSize: 12 }}>Overdue</span>
            <span className="tabular-nums" style={{ fontSize: 13, color: '#b45309' }}>
              {sOverdue}
            </span>
          </div>
        )}
        <Tip text="Based on evaluated predictions only. PENDING/OVERDUE excluded. Formula: TP / (TP + FP + WEAK)">
          <span style={{ color: '#94a3b8', fontSize: 11, borderBottom: '1px dashed #cbd5e1' }}>
            how it's calculated
          </span>
        </Tip>
      </div>

      {/* Table */}
      <div className="overflow-auto rounded-lg" style={{ maxHeight: '420px', border: '1px solid rgba(15,23,42,0.06)' }}>
        <table className="w-full text-[13px]" data-testid="perf-table">
          <thead>
            <tr style={{ background: '#f8fafc', position: 'sticky', top: 0, zIndex: 2, borderBottom: '1px solid rgba(15,23,42,0.08)' }}>
              <th className="text-left py-2 px-3 font-semibold" style={{ color: '#64748b', width: 90 }}>Day</th>
              <th className="text-left py-2 px-3 font-semibold" style={{ color: '#64748b' }}>
                <Tip text="Shows when the prediction is evaluated (createdAt + horizon)">
                  <span>Eval At</span>
                </Tip>
              </th>
              <th className="text-left py-2 px-3 font-semibold" style={{ color: '#64748b' }}>Dir</th>
              <th className="text-right py-2 px-3 font-semibold" style={{ color: '#64748b' }}>Target</th>
              <th className="text-right py-2 px-3 font-semibold" style={{ color: '#64748b' }}>Conf</th>
              <th className="text-center py-2 px-3 font-semibold" style={{ color: '#64748b' }}>Status</th>
            </tr>
          </thead>
          <tbody>
            {/* Fixed Top 3: Yesterday / Today / Tomorrow */}
            {topRows.map(({ label, bucket, row }) => (
              <FixedRow key={label} label={label} bucket={bucket} row={row} />
            ))}

            {/* Divider: Pending */}
            {pendingRest.length > 0 && (
              <tr>
                <td colSpan={6} className="py-2 px-3" style={{ borderTop: '1px solid rgba(15,23,42,0.08)' }}>
                  <span style={{ fontSize: 11, color: '#94a3b8', fontWeight: 500 }} data-testid="pending-divider">
                    Pending — {pendingRest.length} forecast{pendingRest.length !== 1 ? 's' : ''} awaiting evaluation
                  </span>
                </td>
              </tr>
            )}

            {/* Remaining pending forecasts */}
            {pendingRest.map((row, i) => (
              <PerformanceRow key={`p-${i}`} row={row} />
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

/** Fixed top row — Yesterday/Today/Tomorrow. Shows placeholder if no data. */
function FixedRow({ label, bucket, row }) {
  const isToday = label === 'Today';
  const bgStyle = isToday ? { background: 'rgba(37,99,235,0.04)' } : {};
  const labelColor = label === 'Yesterday' ? '#64748b' : label === 'Today' ? '#2563eb' : '#8b5cf6';

  if (!row) {
    return (
      <tr style={{ borderBottom: '1px solid rgba(15,23,42,0.04)', ...bgStyle }} data-testid={`perf-fixed-${label.toLowerCase()}`}>
        <td className="py-2 px-3">
          <span className="text-[11px] font-semibold px-1.5 py-0.5 rounded" style={{ background: `${labelColor}12`, color: labelColor }}>
            {label}
          </span>
        </td>
        <td className="py-2 px-3 tabular-nums" style={{ color: '#94a3b8' }}>{fmtDate(bucket + 'T00:00:00Z')}</td>
        <td className="py-2 px-3" style={{ color: '#cbd5e1' }}>—</td>
        <td className="py-2 px-3 text-right" style={{ color: '#cbd5e1' }}>—</td>
        <td className="py-2 px-3 text-right" style={{ color: '#cbd5e1' }}>—</td>
        <td className="py-2 px-3 text-center">
          <span className="text-[11px] font-medium px-2 py-0.5 rounded-full" style={{ background: '#f1f5f9', color: '#94a3b8' }}>
            No data
          </span>
        </td>
      </tr>
    );
  }

  const os = OUTCOME_STYLE[row.outcome] || OUTCOME_STYLE.PENDING;
  const dirColor = row.direction === 'LONG' ? '#16a34a' : row.direction === 'SHORT' ? '#dc2626' : '#64748b';

  return (
    <tr className="transition-colors hover:bg-slate-50/50"
      style={{ borderBottom: '1px solid rgba(15,23,42,0.04)', ...bgStyle }}
      data-testid={`perf-fixed-${label.toLowerCase()}`}>
      <td className="py-2 px-3">
        <span className="text-[11px] font-semibold px-1.5 py-0.5 rounded" style={{ background: `${labelColor}12`, color: labelColor }}>
          {label}
        </span>
      </td>
      <td className="py-2 px-3 tabular-nums" style={{ color: '#64748b' }}>
        <Tip text={`Created: ${fmtDate(row.createdAt || row.asOf)}`}>
          <span>{fmtDate(row.evaluateAt || row.asOf)}</span>
        </Tip>
      </td>
      <td className="py-2 px-3" style={{ color: dirColor }}>
        {row.direction}
      </td>
      <td className="py-2 px-3 text-right tabular-nums" style={{ color: '#0f172a' }}>
        {row.finalTarget ? (
          <Tip text={`Entry: ${fmt$(row.entry)}\nExpected: ${row.entry ? ((row.finalTarget - row.entry) / row.entry * 100).toFixed(2) + '%' : '—'}`}>
            <span>{fmt$(row.finalTarget)}</span>
          </Tip>
        ) : (
          <span style={{ color: '#94a3b8' }}>—</span>
        )}
      </td>
      <td className="py-2 px-3 text-right tabular-nums" style={{ color: '#0f172a' }}>
        {row.finalConfidence != null ? `${(row.finalConfidence * 100).toFixed(0)}%` : '—'}
      </td>
      <td className="py-2 px-3 text-center">
        <Tip text={OUTCOME_TIP[row.outcome] || ''}>
          <span className="text-[11px] font-medium px-2 py-0.5 rounded-full"
            style={{ background: `${os.color}12`, color: os.color }}>
            {os.label}
          </span>
        </Tip>
      </td>
    </tr>
  );
}

function PerformanceRow({ row }) {
  const isPending = row.outcome === 'PENDING';
  const isOverdue = row.outcome === 'OVERDUE';
  const os = OUTCOME_STYLE[row.outcome] || OUTCOME_STYLE.PENDING;
  const dirColor = row.direction === 'LONG' ? '#16a34a' : row.direction === 'SHORT' ? '#dc2626' : '#64748b';

  return (
    <tr className="transition-colors hover:bg-slate-50/50"
      style={{ borderBottom: '1px solid rgba(15,23,42,0.04)', opacity: isPending ? 0.55 : isOverdue ? 0.75 : 1 }}
      data-testid={`perf-row-${row.evaluateAt || row.createdAt}`}>
      <td className="py-2 px-3" />
      <td className="py-2 px-3 tabular-nums" style={{ color: '#64748b' }}>
        <Tip text={`Created: ${fmtDate(row.createdAt || row.asOf)}`}>
          <span>{fmtDate(row.evaluateAt || row.asOf)}</span>
        </Tip>
      </td>
      <td className="py-2 px-3" style={{ color: dirColor }}>
        {row.direction}
      </td>
      <td className="py-2 px-3 text-right tabular-nums" style={{ color: '#0f172a' }}>
        {row.finalTarget ? (
          <Tip text={`Entry: ${fmt$(row.entry)}\nExpected: ${row.entry ? ((row.finalTarget - row.entry) / row.entry * 100).toFixed(2) + '%' : '—'}`}>
            <span>{fmt$(row.finalTarget)}</span>
          </Tip>
        ) : (
          <span style={{ color: '#94a3b8' }}>—</span>
        )}
      </td>
      <td className="py-2 px-3 text-right tabular-nums" style={{ color: '#0f172a' }}>
        {row.finalConfidence != null ? `${(row.finalConfidence * 100).toFixed(0)}%` : '—'}
      </td>
      <td className="py-2 px-3 text-center">
        <Tip text={OUTCOME_TIP[row.outcome] || ''}>
          <span className="text-[11px] font-medium px-2 py-0.5 rounded-full"
            style={{ background: `${os.color}12`, color: os.color }}>
            {os.label}
          </span>
        </Tip>
      </td>
    </tr>
  );
}
