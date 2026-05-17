/**
 * Block 3: Alt Table — unified, compact altcoin signals with real scoring
 */
import React, { useState, useEffect, useCallback } from 'react';
import { Loader2, AlertTriangle, ChevronDown } from 'lucide-react';

const API = process.env.REACT_APP_BACKEND_URL;

const BIAS_CFG = {
  BUY:   { color: '#16a34a', bg: '#f0fdf4', border: '#bbf7d0', label: 'Buy' },
  WATCH: { color: '#d97706', bg: '#fffbeb', border: '#fde68a', label: 'Watch' },
  AVOID: { color: '#dc2626', bg: '#fef2f2', border: '#fecaca', label: 'Avoid' },
};

const RISK_CFG = {
  LOW:  { color: '#16a34a' },
  MED:  { color: '#d97706' },
  HIGH: { color: '#dc2626' },
};

function ScoreBar({ score }) {
  const pct = Math.min(100, Math.max(0, score));
  const color = pct >= 70 ? '#16a34a' : pct >= 50 ? '#d97706' : '#dc2626';
  return (
    <div className="flex items-center gap-2">
      <div style={{ width: 48, height: 4, background: '#e2e8f0', borderRadius: 2, overflow: 'hidden' }}>
        <div style={{ width: `${pct}%`, height: '100%', background: color, borderRadius: 2, transition: 'width 0.3s' }} />
      </div>
      <span className="tabular-nums text-[12px] font-medium" style={{ color, minWidth: 24 }}>{score}</span>
    </div>
  );
}

export default function AltSignalsTable({ horizon = '7D' }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [selectedHorizon, setSelectedHorizon] = useState(horizon);
  const [showAll, setShowAll] = useState(false);

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API}/api/prediction/exchange/alts?horizon=${selectedHorizon}&limit=30`);
      if (!res.ok) throw new Error(`${res.status}`);
      const json = await res.json();
      if (json.ok) setData(json);
    } catch (e) {
      console.error('AltSignalsTable fetch error:', e);
    }
    setLoading(false);
  }, [selectedHorizon]);

  useEffect(() => { fetchData(); }, [fetchData]);

  if (loading) return (
    <div className="flex items-center justify-center h-48" data-testid="alt-table-loading">
      <Loader2 className="w-5 h-5 animate-spin" style={{ color: '#94a3b8' }} />
    </div>
  );

  if (!data) return (
    <div className="text-center py-8" style={{ color: '#94a3b8', fontSize: 13 }} data-testid="alt-table-empty">No alt data</div>
  );

  const rows = data.rows.filter(r => r.symbol);
  const visible = showAll ? rows : rows.slice(0, 10);

  return (
    <div data-testid="alt-signals-table" style={{ background: '#fff', borderRadius: 12, border: '1px solid rgba(15,23,42,0.06)' }}>
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3" style={{ borderBottom: '1px solid rgba(15,23,42,0.06)' }}>
        <div className="flex items-center gap-3">
          <span style={{ fontSize: 13, fontWeight: 600, color: '#0f172a' }}>Alt Signals</span>
          <span style={{ fontSize: 11, color: '#94a3b8' }}>{data.universe?.count || 0} assets</span>
        </div>
        <div className="flex items-center gap-1 bg-gray-100 rounded-lg p-0.5">
          {['24H', '7D', '30D'].map(h => (
            <button
              key={h}
              onClick={() => setSelectedHorizon(h)}
              data-testid={`alt-horizon-${h}`}
              className={`px-2.5 py-1 rounded-md text-[11px] font-medium transition-all ${
                selectedHorizon === h ? 'bg-white text-blue-600 shadow-sm' : 'text-gray-500 hover:text-gray-700'
              }`}
            >
              {h}
            </button>
          ))}
        </div>
      </div>

      {/* Table */}
      <div className="overflow-auto" style={{ maxHeight: 420 }}>
        <table className="w-full text-[13px]">
          <thead>
            <tr style={{ background: '#f8fafc', position: 'sticky', top: 0, zIndex: 2, borderBottom: '1px solid rgba(15,23,42,0.06)' }}>
              <th className="text-left py-2 px-4 font-semibold" style={{ color: '#64748b' }}>Symbol</th>
              <th className="text-center py-2 px-4 font-semibold" style={{ color: '#64748b' }}>Bias</th>
              <th className="text-center py-2 px-4 font-semibold" style={{ color: '#64748b' }}>Score</th>
              <th className="text-center py-2 px-4 font-semibold" style={{ color: '#64748b' }}>Risk</th>
              <th className="text-right py-2 px-4 font-semibold" style={{ color: '#64748b' }}>Ret 24h</th>
              <th className="text-right py-2 px-4 font-semibold" style={{ color: '#64748b' }}>Volume</th>
              <th className="text-left py-2 px-4 font-semibold" style={{ color: '#64748b' }}>Drivers</th>
              <th className="text-center py-2 px-4 font-semibold" style={{ color: '#64748b' }}>Health</th>
            </tr>
          </thead>
          <tbody>
            {visible.length === 0 && (
              <tr><td colSpan={8} className="text-center py-8" style={{ color: '#94a3b8', fontSize: 12 }}>No signals available</td></tr>
            )}
            {visible.map((row, i) => {
              const bias = BIAS_CFG[row.bias] || BIAS_CFG.WATCH;
              const risk = RISK_CFG[row.risk] || RISK_CFG.LOW;
              const isDataGap = row.health?.status === 'DATA_GAP';
              return (
                <tr key={row.symbol || i} className="hover:bg-slate-50/50 transition-colors"
                  style={{ borderBottom: '1px solid rgba(15,23,42,0.04)', opacity: isDataGap ? 0.6 : 1 }}
                  data-testid={`alt-row-${row.symbol}`}>
                  <td className="py-2 px-4">
                    <span className="font-medium" style={{ color: '#0f172a' }}>{row.symbol.replace('USDT', '')}</span>
                    <span style={{ color: '#94a3b8', fontSize: 11 }}>/USDT</span>
                  </td>
                  <td className="py-2 px-4 text-center">
                    <span className="inline-block px-2 py-0.5 rounded-full text-[11px] font-semibold"
                      style={{ background: bias.bg, color: bias.color, border: `1px solid ${bias.border}` }}>
                      {bias.label}
                    </span>
                  </td>
                  <td className="py-2 px-4"><ScoreBar score={row.score} /></td>
                  <td className="py-2 px-4 text-center">
                    <span className="text-[11px] font-medium" style={{ color: risk.color }}>{row.risk}</span>
                  </td>
                  <td className="py-2 px-4 text-right tabular-nums" style={{ color: row.metrics?.ret_24h >= 0 ? '#16a34a' : '#dc2626' }}>
                    {row.metrics?.ret_24h >= 0 ? '+' : ''}{(row.metrics?.ret_24h * 100).toFixed(1)}%
                  </td>
                  <td className="py-2 px-4 text-right tabular-nums" style={{ color: '#0f172a', fontSize: 12 }}>
                    {row.metrics?.volume_24h_usd > 0
                      ? `$${(row.metrics.volume_24h_usd / 1e6).toFixed(1)}M`
                      : '—'}
                  </td>
                  <td className="py-2 px-4">
                    <div className="flex flex-wrap gap-1">
                      {(row.drivers || []).slice(0, 3).map(d => (
                        <span key={d} className="text-[10px] font-medium" style={{ color: '#475569' }}>
                          {d}
                        </span>
                      ))}
                    </div>
                  </td>
                  <td className="py-2 px-4 text-center">
                    {isDataGap ? (
                      <span className="inline-flex items-center gap-1 text-[11px]" style={{ color: '#d97706' }}>
                        <AlertTriangle className="w-3 h-3" /> Gap
                      </span>
                    ) : (
                      <span className="text-[11px]" style={{ color: '#16a34a' }}>OK</span>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {/* Show more */}
      {rows.length > 10 && (
        <div className="px-4 py-2.5 text-center" style={{ borderTop: '1px solid rgba(15,23,42,0.06)' }}>
          <button
            onClick={() => setShowAll(!showAll)}
            data-testid="alt-show-more"
            className="inline-flex items-center gap-1 text-[12px] font-medium hover:text-blue-700 transition-colors"
            style={{ color: '#3b82f6' }}
          >
            {showAll ? 'Show less' : `Show all ${rows.length}`}
            <ChevronDown className={`w-3.5 h-3.5 transition-transform ${showAll ? 'rotate-180' : ''}`} />
          </button>
        </div>
      )}
    </div>
  );
}
