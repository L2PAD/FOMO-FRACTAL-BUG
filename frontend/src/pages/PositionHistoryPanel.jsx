/**
 * Position History Panel (P1) — Collapsible, multi-line chart with events
 */

import { useState, useEffect, useCallback } from 'react';
import {
  LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer,
  ReferenceLine, ReferenceArea
} from 'recharts';
import { ChevronDown, ChevronUp, History, Clock } from 'lucide-react';

const API = process.env.REACT_APP_BACKEND_URL;

const RANGES = ['6h', '24h', '7d', '30d'];

const ACTION_COLORS = {
  NO_TRADE: '#94a3b8', HOLD: '#d97706', BUY: '#16a34a', SELL: '#dc2626',
};
const MODE_COLORS = {
  DEFENSIVE: '#dc2626', NEUTRAL: '#d97706', AGGRESSIVE: '#16a34a',
};
const EVENT_COLORS = {
  ACTION_FLIP: '#6366f1', REGIME_CHANGE: '#d97706', GATE_CHANGE: '#dc2626', RISK_SPIKE: '#f59e0b',
};

function formatTs(ts) {
  const d = new Date(ts * 1000);
  return d.toLocaleTimeString('en', { hour: '2-digit', minute: '2-digit', hour12: false }) +
    ' ' + d.toLocaleDateString('en', { month: 'short', day: 'numeric' });
}

function CustomTooltip({ active, payload }) {
  if (!active || !payload?.[0]) return null;
  const d = payload[0].payload;
  const ac = ACTION_COLORS[d.action] || '#94a3b8';
  return (
    <div className="rounded-xl shadow-lg p-3 min-w-[180px]" style={{ background: '#fff', border: '1px solid #e2e8f0' }}>
      <div className="text-hint font-medium mb-1.5">{formatTs(d.ts)}</div>
      <div className="flex items-center gap-2 mb-1.5">
        <span className="text-badge px-1.5 py-0.5 rounded" style={{ background: `${ac}12`, color: ac }}>{d.action}</span>
        <span className="font-bold" style={{ fontSize: 13, color: '#0f172a' }}>{d.sizeMult?.toFixed(2)}x</span>
        <span className="text-hint">{d.mode}</span>
      </div>
      {d.gates?.length > 0 && (
        <div className="flex gap-1 mb-1.5 flex-wrap">
          {d.gates.map(g => <span key={g} className="text-badge px-1 py-0.5 rounded" style={{ background: 'rgba(220,38,38,0.06)', color: '#dc2626' }}>{g}</span>)}
        </div>
      )}
      {d.drivers?.length > 0 && (
        <div className="mb-1.5">
          {d.drivers.map((dr, i) => <div key={i} className="text-hint font-medium" style={{ color: '#475569' }}>{dr}</div>)}
        </div>
      )}
      <div className="grid grid-cols-2 gap-x-3 gap-y-0.5 pt-1.5 text-hint" style={{ borderTop: '1px solid #f1f5f9' }}>
        <div>riskOff: <span className="font-semibold">{(d.riskOffProb * 100).toFixed(0)}%</span></div>
        <div>macroMult: <span className="font-semibold">{d.macroMult?.toFixed(2)}</span></div>
        <div>exec: <span className="font-semibold">{d.executionScore?.toFixed(3)}</span></div>
        <div>edge: <span className="font-semibold">{d.edge?.toFixed(3)}</span></div>
      </div>
    </div>
  );
}

export default function PositionHistoryPanel() {
  const [open, setOpen] = useState(false);
  const [range, setRange] = useState('30d');
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);

  const fetchHistory = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API}/api/overview/history?asset=BTCUSDT&range=${range}`);
      const json = await res.json();
      setData(json);
    } catch {}
    setLoading(false);
  }, [range]);

  useEffect(() => {
    if (open) fetchHistory();
  }, [open, fetchHistory]);

  const series = data?.series || [];
  const events = data?.events || [];
  const stats = data?.stats || {};

  // Normalize totalRisk to 0..1 for overlay
  const chartData = series.map(s => ({
    ...s,
    riskNorm: (s.totalRisk || 50) / 100,
  }));

  return (
    <div className="rounded-2xl overflow-hidden" data-testid="position-history-panel"
      style={{ background: '#fff', border: '1px solid #e2e8f0' }}>
      {/* Header */}
      <button onClick={() => setOpen(!open)} data-testid="history-toggle"
        className="w-full flex items-center justify-between px-5 py-3.5 text-left transition-colors"
        style={{ background: open ? '#f8fafc' : '#fff' }}
        onMouseEnter={e => { if (!open) e.currentTarget.style.background = '#f8fafc'; }}
        onMouseLeave={e => { if (!open) e.currentTarget.style.background = '#fff'; }}>
        <div className="flex items-center gap-2">
          <History className="w-4 h-4" style={{ color: '#6366f1' }} />
          <span className="text-card-title">Position History</span>
          {stats.totalPoints > 0 && (
            <span className="text-badge px-1.5 py-0.5 rounded-full" style={{ background: '#f1f5f9', color: '#94a3b8' }}>{stats.totalPoints} pts</span>
          )}
        </div>
        {open ? <ChevronUp className="w-4 h-4" style={{ color: '#94a3b8' }} /> : <ChevronDown className="w-4 h-4" style={{ color: '#94a3b8' }} />}
      </button>

      {/* Content */}
      <div className="overflow-hidden transition-all duration-200" style={{ maxHeight: open ? 500 : 0, opacity: open ? 1 : 0 }}>
        <div className="px-5 pb-5">
          {/* Range chips */}
          <div className="flex items-center gap-2 mb-3">
            {RANGES.map(r => (
              <button key={r} onClick={() => setRange(r)} data-testid={`range-${r}`}
                className="px-2.5 py-1 rounded-lg text-badge transition-colors"
                style={{
                  background: range === r ? 'rgba(99,102,241,0.08)' : '#f8fafc',
                  color: range === r ? '#6366f1' : '#94a3b8',
                  border: `1px solid ${range === r ? 'rgba(99,102,241,0.15)' : '#e2e8f0'}`,
                }}>{r}</button>
            ))}
            <div className="flex items-center gap-1 ml-auto">
              <div className="w-1.5 h-1.5 rounded-full animate-pulse" style={{ background: '#16a34a' }} />
              <span className="text-hint">Live</span>
            </div>
          </div>

          {loading && <div className="h-40 flex items-center justify-center"><Clock className="w-4 h-4 animate-spin" style={{ color: '#94a3b8' }} /></div>}

          {!loading && chartData.length > 0 && (
            <>
              {/* Multi-line Chart */}
              <div className="h-[140px] mb-3" data-testid="history-chart">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={chartData} margin={{ top: 4, right: 4, bottom: 0, left: 0 }}>
                    <XAxis dataKey="ts" tickFormatter={ts => {
                      const d = new Date(ts * 1000);
                      return d.toLocaleDateString('en', { month: 'short', day: 'numeric' });
                    }} tick={{ fontSize: 9, fill: '#94a3b8' }} axisLine={false} tickLine={false} />
                    <YAxis domain={[0, 1.2]} tick={{ fontSize: 9, fill: '#94a3b8' }} axisLine={false} tickLine={false} width={28} />
                    <Tooltip content={<CustomTooltip />} />
                    <Line type="monotone" dataKey="sizeMult" stroke="#6366f1" strokeWidth={2} dot={false} name="Size" />
                    <Line type="monotone" dataKey="macroMult" stroke="#d97706" strokeWidth={1} dot={false} strokeDasharray="4 2" name="Macro" />
                    <Line type="monotone" dataKey="riskNorm" stroke="#dc2626" strokeWidth={1} dot={false} strokeDasharray="2 2" name="Risk" opacity={0.5} />
                    <Line type="monotone" dataKey="confidence" stroke="#16a34a" strokeWidth={1} dot={false} name="Conf" opacity={0.6} />
                    {/* Event markers */}
                    {events.map((ev, i) => (
                      <ReferenceLine key={i} x={ev.ts} stroke={EVENT_COLORS[ev.type] || '#94a3b8'} strokeWidth={1} strokeDasharray="3 3" />
                    ))}
                  </LineChart>
                </ResponsiveContainer>
              </div>

              {/* Legend */}
              <div className="flex items-center gap-4 mb-3">
                {[
                  { label: 'Size', color: '#6366f1', dash: false },
                  { label: 'Macro', color: '#d97706', dash: true },
                  { label: 'Risk', color: '#dc2626', dash: true },
                  { label: 'Conf', color: '#16a34a', dash: false },
                ].map(l => (
                  <div key={l.label} className="flex items-center gap-1.5">
                    <div className="w-3 h-0.5 rounded-full" style={{ background: l.color, opacity: l.dash ? 0.5 : 1 }} />
                    <span className="text-hint">{l.label}</span>
                  </div>
                ))}
              </div>

              {/* Stability Strip */}
              <div className="mb-3">
                <div className="text-hint font-semibold uppercase mb-1" style={{ color: '#94a3b8' }}>Action Timeline</div>
                <div className="flex h-2 rounded-full overflow-hidden gap-px">
                  {chartData.map((d, i) => (
                    <div key={i} className="flex-1 min-w-px" style={{ background: ACTION_COLORS[d.action] || '#94a3b8' }} title={`${d.action} @ ${formatTs(d.ts)}`} />
                  ))}
                </div>
                <div className="text-hint font-semibold uppercase mt-2 mb-1" style={{ color: '#94a3b8' }}>Mode Timeline</div>
                <div className="flex h-2 rounded-full overflow-hidden gap-px">
                  {chartData.map((d, i) => (
                    <div key={i} className="flex-1 min-w-px" style={{ background: MODE_COLORS[d.mode] || '#94a3b8' }} title={`${d.mode} @ ${formatTs(d.ts)}`} />
                  ))}
                </div>
              </div>

              {/* Key Stats */}
              <div className="grid grid-cols-4 gap-3">
                {[
                  { label: 'Flips', value: stats.flipCount, c: stats.flipCount > 3 ? '#d97706' : '#64748b' },
                  { label: 'Avg Size', value: stats.avgSize?.toFixed(2) + 'x' },
                  { label: 'Avg Stability', value: (stats.avgStability * 100).toFixed(0) + '%', c: stats.avgStability > 0.8 ? '#16a34a' : '#d97706' },
                  { label: 'Blocked', value: (stats.blockedPct * 100).toFixed(0) + '%', c: stats.blockedPct > 0.5 ? '#dc2626' : '#64748b' },
                ].map(s => (
                  <div key={s.label} className="text-center">
                    <div className="font-bold tabular-nums" style={{ color: s.c || '#0f172a', fontSize: 16 }}>{s.value}</div>
                    <div className="text-hint">{s.label}</div>
                  </div>
                ))}
              </div>

              {/* Events */}
              {events.length > 0 && (
                <div className="mt-3 pt-3" style={{ borderTop: '1px solid #f1f5f9' }}>
                  <div className="text-hint font-semibold uppercase mb-1.5" style={{ color: '#94a3b8' }}>Events ({events.length})</div>
                  <div className="space-y-1 max-h-[60px] overflow-y-auto">
                    {events.slice(-5).reverse().map((ev, i) => (
                      <div key={i} className="flex items-center gap-2 text-hint">
                        <div className="w-1.5 h-1.5 rounded-full flex-shrink-0" style={{ background: EVENT_COLORS[ev.type] || '#94a3b8' }} />
                        <span className="font-bold" style={{ color: EVENT_COLORS[ev.type] || '#94a3b8' }}>{ev.type.replace(/_/g, ' ')}</span>
                        <span style={{ color: '#64748b' }}>
                          {ev.meta?.from && ev.meta?.to ? `${ev.meta.from} → ${ev.meta.to}` : ''}
                          {ev.meta?.delta ? `Δ${ev.meta.delta}` : ''}
                        </span>
                        <span className="ml-auto" style={{ color: '#cbd5e1' }}>{formatTs(ev.ts)}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </>
          )}

          {!loading && chartData.length === 0 && (
            <div className="h-20 flex items-center justify-center text-hint">
              No history data yet. Data accumulates as the system runs.
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
