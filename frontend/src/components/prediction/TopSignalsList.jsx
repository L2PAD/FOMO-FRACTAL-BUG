/**
 * Block 4: Top Signals — compact list of strongest signals
 */
import React, { useState, useEffect, useCallback } from 'react';
import { Loader2, TrendingUp, TrendingDown, Eye, ChevronRight, X } from 'lucide-react';
import { createPortal } from 'react-dom';

const API = process.env.REACT_APP_BACKEND_URL;

const ACTION_CFG = {
  BUY:   { color: '#16a34a', bg: '#f0fdf4', border: '#bbf7d0', icon: TrendingUp },
  SELL:  { color: '#dc2626', bg: '#fef2f2', border: '#fecaca', icon: TrendingDown },
  WATCH: { color: '#d97706', bg: '#fffbeb', border: '#fde68a', icon: Eye },
};

const TIER_CFG = {
  A: { color: '#16a34a', label: 'A' },
  B: { color: '#3b82f6', label: 'B' },
  C: { color: '#94a3b8', label: 'C' },
};

function SignalDrawer({ signal, onClose }) {
  if (!signal) return null;
  const action = ACTION_CFG[signal.action] || ACTION_CFG.WATCH;
  const tier = TIER_CFG[signal.tier] || TIER_CFG.C;

  return createPortal(
    <div className="fixed inset-0" style={{ zIndex: 50 }}>
      <div className="absolute inset-0 bg-black/30 backdrop-blur-sm" onClick={onClose} />
      <div className="absolute right-0 top-0 bottom-0 w-full max-w-md bg-white shadow-2xl flex flex-col"
        style={{ animation: 'slideIn 0.2s ease-out' }}>
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4" style={{ borderBottom: '1px solid rgba(15,23,42,0.08)' }}>
          <div>
            <h3 className="font-semibold text-base" style={{ color: '#0f172a' }}>{signal.symbol}</h3>
            <p style={{ fontSize: 12, color: '#64748b' }}>Signal Detail</p>
          </div>
          <button onClick={onClose} className="p-1.5 rounded-lg hover:bg-gray-100 transition-colors" data-testid="signal-drawer-close">
            <X className="w-4 h-4" style={{ color: '#64748b' }} />
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto px-5 py-4 space-y-5">
          {/* Action Badge */}
          <div className="flex items-center gap-3">
            <span className="inline-flex items-center gap-1.5 text-sm font-bold"
              style={{ color: action.color }}>
              {React.createElement(action.icon, { className: 'w-4 h-4' })}
              {signal.action}
            </span>
            <span className="text-sm font-semibold"
              style={{ color: tier.color }}>
              Tier {tier.label}
            </span>
          </div>

          {/* Metrics */}
          <div className="grid grid-cols-2 gap-3">
            <MetricCard label="Conviction" value={`${signal.conviction}%`}
              color={signal.conviction >= 60 ? '#16a34a' : '#d97706'} />
            <MetricCard label="Horizon" value={signal.horizon} color="#3b82f6" />
          </div>

          {/* One-liner */}
          <div style={{ background: '#f8fafc', borderRadius: 8, padding: '12px 14px', border: '1px solid rgba(15,23,42,0.06)' }}>
            <span style={{ fontSize: 11, color: '#64748b', textTransform: 'uppercase', letterSpacing: '0.05em', fontWeight: 600 }}>Summary</span>
            <p style={{ fontSize: 13, color: '#0f172a', marginTop: 4, lineHeight: 1.5 }}>{signal.oneLiner}</p>
          </div>

          {/* Integrity */}
          <div style={{ background: '#f8fafc', borderRadius: 8, padding: '12px 14px', border: '1px solid rgba(15,23,42,0.06)' }}>
            <span style={{ fontSize: 11, color: '#64748b', textTransform: 'uppercase', letterSpacing: '0.05em', fontWeight: 600 }}>Data Integrity</span>
            <div className="flex items-center gap-3 mt-2">
              <span style={{ fontSize: 13, color: signal.integrity?.status === 'OK' ? '#16a34a' : '#d97706' }}>
                {signal.integrity?.status || 'N/A'}
              </span>
              <span style={{ fontSize: 12, color: '#64748b' }}>
                Coverage: {signal.integrity?.coveragePct || 0}%
              </span>
            </div>
          </div>
        </div>
      </div>
      <style>{`@keyframes slideIn { from { transform: translateX(100%); } to { transform: translateX(0); } }`}</style>
    </div>,
    document.body
  );
}

function MetricCard({ label, value, color }) {
  return (
    <div style={{ background: '#f8fafc', borderRadius: 8, padding: '10px 12px', border: '1px solid rgba(15,23,42,0.06)' }}>
      <div style={{ fontSize: 11, color: '#64748b', marginBottom: 2 }}>{label}</div>
      <div className="font-bold tabular-nums" style={{ fontSize: 18, color }}>{value}</div>
    </div>
  );
}

export default function TopSignalsList() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState(null);

  const fetchData = useCallback(async () => {
    try {
      const res = await fetch(`${API}/api/prediction/exchange/top-signals?limit=10`);
      if (!res.ok) throw new Error(`${res.status}`);
      const json = await res.json();
      if (json.ok) setData(json);
    } catch (e) {
      console.error('TopSignals fetch error:', e);
    }
    setLoading(false);
  }, []);

  useEffect(() => { fetchData(); }, [fetchData]);

  if (loading) return (
    <div className="flex items-center justify-center h-48" data-testid="top-signals-loading">
      <Loader2 className="w-5 h-5 animate-spin" style={{ color: '#94a3b8' }} />
    </div>
  );

  if (!data) return (
    <div className="text-center py-8" style={{ color: '#94a3b8', fontSize: 13 }} data-testid="top-signals-empty">No signal data</div>
  );

  const signals = data.signals || [];

  return (
    <div data-testid="top-signals-list" style={{ background: '#fff', borderRadius: 12, border: '1px solid rgba(15,23,42,0.06)' }}>
      {/* Header */}
      <div className="px-4 py-3" style={{ borderBottom: '1px solid rgba(15,23,42,0.06)' }}>
        <div className="flex items-center gap-2">
          <span style={{ fontSize: 13, fontWeight: 600, color: '#0f172a' }}>Top Signals</span>
          <span className="text-[10px] font-bold tabular-nums" style={{ color: '#3b82f6' }}>
            {signals.length}
          </span>
        </div>
      </div>

      {/* Signal list */}
      <div className="divide-y" style={{ borderColor: 'rgba(15,23,42,0.04)' }}>
        {signals.length === 0 && (
          <div className="text-center py-8" style={{ color: '#94a3b8', fontSize: 12 }}>No active signals</div>
        )}
        {signals.map((s, i) => {
          const action = ACTION_CFG[s.action] || ACTION_CFG.WATCH;
          const tier = TIER_CFG[s.tier] || TIER_CFG.C;
          const ActionIcon = action.icon;
          return (
            <button
              key={`${s.symbol}-${i}`}
              onClick={() => setSelected(s)}
              data-testid={`signal-row-${s.symbol}`}
              className="w-full flex items-center gap-3 px-4 py-3 hover:bg-slate-50/80 transition-colors text-left"
            >
              {/* Rank */}
              <span className="tabular-nums text-[11px] font-medium" style={{ color: '#94a3b8', minWidth: 16 }}>
                {i + 1}
              </span>

              {/* Action icon */}
              <span className="flex items-center justify-center w-7 h-7 rounded-lg" style={{ background: action.bg }}>
                <ActionIcon className="w-3.5 h-3.5" style={{ color: action.color }} />
              </span>

              {/* Symbol + one-liner */}
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <span className="font-medium text-[13px]" style={{ color: '#0f172a' }}>{s.symbol.replace('USDT', '')}</span>
                  <span className="text-[10px] font-bold"
                    style={{ color: tier.color }}>
                    {tier.label}
                  </span>
                </div>
                <p className="text-[11px] truncate" style={{ color: '#64748b', maxWidth: 280 }}>{s.oneLiner}</p>
              </div>

              {/* Conviction */}
              <div className="text-right">
                <span className="tabular-nums text-[14px] font-bold" style={{ color: s.conviction >= 60 ? '#16a34a' : s.conviction >= 40 ? '#d97706' : '#94a3b8' }}>
                  {s.conviction}%
                </span>
              </div>

              <ChevronRight className="w-3.5 h-3.5 flex-shrink-0" style={{ color: '#cbd5e1' }} />
            </button>
          );
        })}
      </div>

      {/* Drawer */}
      {selected && <SignalDrawer signal={selected} onClose={() => setSelected(null)} />}
    </div>
  );
}
