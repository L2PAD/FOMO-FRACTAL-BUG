/**
 * Base Forecast Table — Pure UI Component
 * 
 * Renders the shared table shell for all forecast performance tables.
 * No data fetching — receives data via props.
 * 
 * Columns: Day | Eval At | Dir | Target | Error% | Δ Entry | Conf | Status
 */

import React, { useState, useMemo } from 'react';
import { createPortal } from 'react-dom';

const HORIZON_OPTIONS = ['7D', '30D', '90D', '180D', '365D'];

const STATUS_STYLE = {
  hit:     { label: 'Hit',     color: '#16a34a', bg: 'rgba(22,163,74,0.08)' },
  miss:    { label: 'Miss',    color: '#dc2626', bg: 'rgba(220,38,38,0.08)' },
  pending: { label: 'Pending', color: '#94a3b8', bg: 'rgba(148,163,184,0.08)' },
};

function Tip({ children, text }) {
  const [show, setShow] = useState(false);
  const [pos, setPos] = useState({ x: 0, y: 0 });
  const handleEnter = (e) => {
    const rect = e.currentTarget.getBoundingClientRect();
    setPos({ x: Math.min(rect.left, window.innerWidth - 240), y: rect.bottom + 4 });
    setShow(true);
  };
  return (
    <span className="cursor-help" onMouseEnter={handleEnter} onMouseLeave={() => setShow(false)}>
      {children}
      {show && createPortal(
        <div className="fixed max-w-[240px]" style={{ left: pos.x, top: pos.y, zIndex: 99999, pointerEvents: 'none' }}>
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
function getRowStatus(row) { return row.status === 'pending' ? 'pending' : row.hit === true ? 'hit' : 'miss'; }
function confColor(c) { return c >= 0.7 ? '#16a34a' : c >= 0.4 ? '#d97706' : '#94a3b8'; }

function Th({ children, tip, right, center }) {
  const align = right ? 'text-right' : center ? 'text-center' : 'text-left';
  const inner = tip ? <Tip text={tip}><span>{children}</span></Tip> : children;
  return <th className={`py-2 px-3 font-semibold ${align}`} style={{ color: '#64748b' }}>{inner}</th>;
}

function ForecastRow({ row, isPending }) {
  const status = getRowStatus(row);
  const ss = STATUS_STYLE[status];
  const dirColor = row.direction === 'UP' ? '#16a34a' : row.direction === 'DOWN' ? '#dc2626' : '#64748b';

  let deltaEntry = null;
  let deltaColor = '#64748b';
  if (row.actualPrice && row.entryPrice && row.entryPrice > 0) {
    deltaEntry = (row.actualPrice - row.entryPrice) / row.entryPrice;
    deltaColor = deltaEntry > 0 ? '#16a34a' : deltaEntry < 0 ? '#dc2626' : '#64748b';
  }

  return (
    <tr className="transition-colors hover:bg-slate-50/50"
      style={{ borderBottom: '1px solid rgba(15,23,42,0.04)', opacity: isPending ? 0.5 : 1 }}
      data-testid={`forecast-row-${row.horizon}-${row.createdAt}`}>
      <td className="py-2 px-3 tabular-nums" style={{ color: '#64748b', fontSize: 12 }}>{fmtDate(row.createdAt)}</td>
      <td className="py-2 px-3 tabular-nums" style={{ color: '#64748b' }}>
        <Tip text={`Created: ${fmtDate(row.createdAt)}\nEntry: ${fmt$(row.entryPrice)}\nModel: ${row.modelVersion || '—'}`}>
          <span>{fmtDate(row.evaluateAt)}</span>
        </Tip>
      </td>
      <td className="py-2 px-3 font-medium" style={{ color: dirColor }}>
        {row.direction}
        {row.directionCorrect != null && (
          <span style={{ fontSize: 10, marginLeft: 4, color: row.directionCorrect ? '#16a34a' : '#dc2626' }}>
            {row.directionCorrect ? '✓' : '✗'}
          </span>
        )}
      </td>
      <td className="py-2 px-3 text-right tabular-nums" style={{ color: '#0f172a' }}>
        <Tip text={`Entry: ${fmt$(row.entryPrice)}\nExpected: ${row.expectedReturn != null ? (row.expectedReturn >= 0 ? '+' : '') + (row.expectedReturn * 100).toFixed(2) + '%' : '—'}${row.actualPrice ? '\nActual: ' + fmt$(row.actualPrice) : ''}`}>
          <span>{fmt$(row.targetPrice)}</span>
        </Tip>
      </td>
      <td className="py-2 px-3 text-right tabular-nums" style={{ color: row.errorPct != null ? (row.errorPct <= 0.03 ? '#16a34a' : row.errorPct <= 0.08 ? '#d97706' : '#dc2626') : '#94a3b8' }}>
        {row.errorPct != null ? `${(row.errorPct * 100).toFixed(2)}%` : '—'}
      </td>
      <td className="py-2 px-3 text-right tabular-nums" style={{ color: deltaColor }}>
        {deltaEntry != null ? `${deltaEntry >= 0 ? '+' : ''}${(deltaEntry * 100).toFixed(2)}%` : '—'}
      </td>
      <td className="py-2 px-3 text-right tabular-nums" style={{ color: confColor(row.confidence || 0) }}>
        {row.confidence != null ? `${(row.confidence * 100).toFixed(0)}%` : '—'}
      </td>
      <td className="py-2 px-3 text-center">
        <span className="inline-block text-[11px] font-medium px-2 py-0.5 rounded-md" style={{ color: ss.color, background: ss.bg }}>
          {ss.label}
        </span>
      </td>
    </tr>
  );
}

/**
 * @param {Object} props
 * @param {Object|null} props.data - { rows, summary } from API
 * @param {boolean} props.loading
 * @param {string} props.activeHorizon
 * @param {function} props.onHorizonChange
 * @param {string} props.testIdPrefix - e.g. 'btc', 'spx', 'dxy'
 */
export default function BaseForecastTable({ data, loading, activeHorizon, onHorizonChange, testIdPrefix = 'forecast' }) {
  const { resolvedRows, pendingRows, summary } = useMemo(() => {
    if (!data) return { resolvedRows: [], pendingRows: [], summary: null };
    const resolved = data.rows.filter(r => r.status === 'resolved').sort((a, b) => new Date(b.evaluateAt) - new Date(a.evaluateAt));
    const pending = data.rows.filter(r => r.status === 'pending').sort((a, b) => new Date(a.evaluateAt) - new Date(b.evaluateAt));
    return { resolvedRows: resolved, pendingRows: pending, summary: data.summary };
  }, [data]);

  return (
    <div data-testid={`${testIdPrefix}-performance-table`} className="bg-white rounded-xl p-6 mb-6 border border-gray-100">
      {/* Section Title */}
      <h2 className="text-lg font-semibold text-gray-900 mb-4">Prediction Performance</h2>

      {/* Horizon Tabs */}
      <div className="flex items-center gap-1 mb-4" data-testid={`${testIdPrefix}-horizon-tabs`}>
        {HORIZON_OPTIONS.map(h => (
          <button
            key={h}
            data-testid={`${testIdPrefix}-horizon-tab-${h}`}
            onClick={() => onHorizonChange(h)}
            className={`px-3 py-1.5 rounded-md text-xs font-medium transition-all ${
              activeHorizon === h
                ? 'bg-gray-900 text-white'
                : 'text-gray-500 hover:text-gray-900 hover:bg-gray-100'
            }`}
          >
            {h}
          </button>
        ))}
      </div>

      {loading ? (
        <div className="text-center py-6" style={{ color: '#94a3b8', fontSize: 13 }}>Loading...</div>
      ) : !data ? (
        <div className="text-center py-6" style={{ color: '#94a3b8', fontSize: 13 }}>No data</div>
      ) : (
        <>
          {/* Summary bar */}
          <div className="flex items-center gap-5 mb-4 px-1" data-testid={`${testIdPrefix}-perf-summary`}>
            <div className="flex items-center gap-1.5">
              <span style={{ color: '#64748b', fontSize: 12 }}>Win Rate</span>
              <span className="font-bold tabular-nums" data-testid={`${testIdPrefix}-perf-win-rate`}
                style={{ fontSize: 14, color: summary.winRate >= 0.5 ? '#16a34a' : summary.winRate >= 0.3 ? '#d97706' : '#94a3b8' }}>
                {(summary.winRate * 100).toFixed(0)}%
              </span>
            </div>
            <div className="flex items-center gap-1.5">
              <span style={{ color: '#64748b', fontSize: 12 }}>Dir Acc</span>
              <span className="font-bold tabular-nums"
                style={{ fontSize: 14, color: summary.dirAccuracy >= 0.6 ? '#16a34a' : summary.dirAccuracy >= 0.4 ? '#d97706' : '#94a3b8' }}>
                {(summary.dirAccuracy * 100).toFixed(0)}%
              </span>
            </div>
            <div className="flex items-center gap-1.5">
              <span style={{ color: '#64748b', fontSize: 12 }}>Avg Error</span>
              <span className="font-bold tabular-nums" data-testid={`${testIdPrefix}-perf-avg-error`}
                style={{ fontSize: 14, color: summary.avgError <= 0.03 ? '#16a34a' : summary.avgError <= 0.08 ? '#d97706' : '#dc2626' }}>
                {(summary.avgError * 100).toFixed(2)}%
              </span>
            </div>
            <div className="flex items-center gap-1.5">
              <span style={{ color: '#64748b', fontSize: 12 }}>Evaluated</span>
              <span className="tabular-nums" style={{ fontSize: 13, color: '#0f172a' }}>
                {summary.evaluated}/{summary.total}
              </span>
            </div>
          </div>

          {/* Table */}
          <div className="overflow-auto rounded-lg" style={{ maxHeight: 420, border: '1px solid rgba(15,23,42,0.06)' }}>
            <table className="w-full text-[13px]" data-testid={`${testIdPrefix}-perf-table`}>
              <thead>
                <tr style={{ background: '#f8fafc', position: 'sticky', top: 0, zIndex: 2, borderBottom: '1px solid rgba(15,23,42,0.08)' }}>
                  <Th>Day</Th>
                  <Th tip="When the prediction is evaluated (createdAt + horizon)">Eval At</Th>
                  <Th>Dir</Th>
                  <Th right>Target</Th>
                  <Th right tip="Prediction error: |actual - target| / target">Error %</Th>
                  <Th right tip="Actual price change from entry: (actual - entry) / entry">Δ Entry</Th>
                  <Th right>Conf</Th>
                  <Th center>Status</Th>
                </tr>
              </thead>
              <tbody>
                {resolvedRows.map((row, i) => <ForecastRow key={`r-${i}`} row={row} />)}
                {pendingRows.length > 0 && (
                  <tr>
                    <td colSpan={8} className="py-2 px-3" style={{ borderTop: '1px solid rgba(15,23,42,0.08)' }}>
                      <span style={{ fontSize: 11, color: '#94a3b8', fontWeight: 500 }}>
                        Pending — {pendingRows.length} forecast{pendingRows.length !== 1 ? 's' : ''}
                      </span>
                    </td>
                  </tr>
                )}
                {pendingRows.map((row, i) => <ForecastRow key={`p-${i}`} row={row} isPending />)}
                {resolvedRows.length === 0 && pendingRows.length === 0 && (
                  <tr>
                    <td colSpan={8} className="py-6 text-center" style={{ color: '#94a3b8', fontSize: 13 }}>
                      No forecasts yet
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}
