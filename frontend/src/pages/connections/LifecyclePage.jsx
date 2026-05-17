/**
 * Lifecycle Decision Engine
 * Clean trader interface — no badges, no pills, no decoration
 * Color = action only
 */

import React, { useState, useEffect, useCallback } from 'react';
import { RefreshCw, ChevronDown, ChevronUp } from 'lucide-react';

const API = process.env.REACT_APP_BACKEND_URL || '';

const ACTION_COLOR = {
  'STRONG BUY': '#16a34a',
  'BUY': '#16a34a',
  'HOLD': '#9ca3af',
  'AVOID': '#6b7280',
  'EXIT': '#ef4444',
};

const PHASE_HEX = {
  ACCUMULATION: '#3b82f6',
  IGNITION: '#16a34a',
  EXPANSION: '#d97706',
  DISTRIBUTION: '#ef4444',
};

const ENTRY_COLOR = {
  EARLY: '#16a34a',
  OPEN: '#22c55e',
  LATE: '#d97706',
  AVOID: '#6b7280',
};

/* ── PHASE STATUS BAR ──────────────────────────────────────── */
function PhaseBar({ counts, dominant }) {
  const total = Object.values(counts).reduce((a, b) => a + b, 0) || 1;
  const phases = ['ACCUMULATION', 'IGNITION', 'EXPANSION', 'DISTRIBUTION'];
  const labels = { ACCUMULATION: 'ACC', IGNITION: 'IGN', EXPANSION: 'EXP', DISTRIBUTION: 'DIST' };

  return (
    <div className="flex items-center gap-0.5 w-full" data-testid="phase-bar">
      {phases.map(p => {
        const pct = (counts[p] || 0) / total * 100;
        const isDom = p === dominant;
        return (
          <div key={p} className="flex items-center gap-1" style={{ width: `${Math.max(pct, 6)}%` }}>
            <div style={{ flex: 1, height: 3, borderRadius: 2, background: PHASE_HEX[p], opacity: isDom ? 1 : 0.15 }} />
            <span style={{ fontSize: 10, fontWeight: 600, color: isDom ? PHASE_HEX[p] : '#d1d5db', whiteSpace: 'nowrap' }}>
              {labels[p]} {counts[p] || 0}
            </span>
          </div>
        );
      })}
    </div>
  );
}

/* ── MARKET STATE ──────────────────────────────────────────── */
function MarketState({ marketState }) {
  const { dominant, dominantCount, action } = marketState;
  const hex = PHASE_HEX[dominant] || '#fff';

  return (
    <div style={{ background: '#0a0a0a', borderRadius: 10, padding: '20px 24px', marginBottom: 20 }} data-testid="market-state-block">
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 10, marginBottom: 4 }}>
        <span style={{ color: hex, fontSize: 18, fontWeight: 600 }}>{dominant} DOMINANT</span>
        <span style={{ color: '#6b7280', fontSize: 12 }}>{dominantCount} assets</span>
      </div>
      <p style={{ color: '#9ca3af', fontSize: 12, marginBottom: 14 }}>{action.headline}</p>
      <div style={{ display: 'flex', gap: 40 }}>
        <div>
          {action.do.map((d, i) => (
            <div key={i} style={{ fontSize: 12, color: '#d1d5db', marginBottom: 3 }}>
              <span style={{ color: '#22c55e', fontWeight: 600, marginRight: 6 }}>+</span>{d}
            </div>
          ))}
        </div>
        <div>
          {action.dont.map((d, i) => (
            <div key={i} style={{ fontSize: 12, color: '#6b7280', marginBottom: 3 }}>
              <span style={{ color: '#ef4444', fontWeight: 600, marginRight: 6 }}>-</span>{d}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

/* ── PUMP DETECTOR ─────────────────────────────────────────── */
function PumpDetector({ signals }) {
  if (!signals || signals.length === 0) return null;

  return (
    <div style={{ background: '#0a0a0a', borderRadius: 10, padding: '20px 24px', marginBottom: 20 }} data-testid="pump-detector">
      <div style={{ fontSize: 11, fontWeight: 600, color: '#22c55e', letterSpacing: '0.08em', marginBottom: 14 }}>
        PUMP DETECTOR
      </div>

      {/* Header */}
      <div style={{ display: 'flex', gap: 0, padding: '0 0 6px', fontSize: 9, fontWeight: 600, color: '#4b5563', letterSpacing: '0.1em', textTransform: 'uppercase' }}>
        <span style={{ width: 80 }}>Token</span>
        <span style={{ width: 50, textAlign: 'right' }}>Score</span>
        <span style={{ width: 50, textAlign: 'right' }}>Vel</span>
        <span style={{ width: 50, textAlign: 'right' }}>Uniq</span>
        <span style={{ width: 90, textAlign: 'center' }}>Phase</span>
        <span style={{ width: 70 }}>Entry</span>
      </div>

      {signals.map(s => (
        <div key={s.symbol} style={{ display: 'flex', alignItems: 'center', padding: '6px 0' }} data-testid={`pump-${s.symbol}`}>
          <span style={{ width: 80, fontSize: 13, fontWeight: 600, color: '#f9fafb' }}>${s.symbol}</span>
          <span style={{ width: 50, textAlign: 'right', fontSize: 12, fontWeight: 500, color: '#d1d5db', fontVariantNumeric: 'tabular-nums' }}>
            {(s.score * 100).toFixed(0)}
          </span>
          <span style={{ width: 50, textAlign: 'right', fontSize: 11, color: '#9ca3af', fontVariantNumeric: 'tabular-nums' }}>
            x{s.velocity?.toFixed(1) || '—'}
          </span>
          <span style={{ width: 50, textAlign: 'right', fontSize: 11, color: '#9ca3af', fontVariantNumeric: 'tabular-nums' }}>
            {s.unique?.toFixed(2) || '—'}
          </span>
          <span style={{ width: 90, textAlign: 'center', fontSize: 10, fontWeight: 500, color: PHASE_HEX[s.phase] || '#6b7280' }}>
            {s.phase}
          </span>
          <span style={{ width: 70, fontSize: 10, fontWeight: 600, color: ENTRY_COLOR[s.entry] || '#6b7280' }}>
            {s.entry}
          </span>
        </div>
      ))}
    </div>
  );
}

/* ── ASSETS TABLE ──────────────────────────────────────────── */
function AssetsTable({ assets }) {
  const [expanded, setExpanded] = useState(false);
  const pri = { 'STRONG BUY': 0, 'BUY': 1, 'HOLD': 2, 'AVOID': 3, 'EXIT': 4 };
  const sorted = [...assets].sort((a, b) => (pri[a.action] ?? 5) - (pri[b.action] ?? 5) || b.score - a.score);
  const visible = expanded ? sorted : sorted.slice(0, 25);

  return (
    <div style={{ marginBottom: 20 }} data-testid="top-assets">
      <div style={{ fontSize: 11, fontWeight: 600, color: '#111827', letterSpacing: '0.08em', marginBottom: 10 }}>
        ASSETS
      </div>

      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 0, padding: '0 0 6px', fontSize: 9, fontWeight: 600, color: '#9ca3af', letterSpacing: '0.1em', textTransform: 'uppercase' }}>
        <span style={{ width: 72 }}>Asset</span>
        <span style={{ width: 72 }}>Action</span>
        <span style={{ width: 50, textAlign: 'right' }}>Score</span>
        <span style={{ width: 80, textAlign: 'center' }}>Phase</span>
        <span style={{ width: 64 }}>Entry</span>
        <span style={{ width: 56, textAlign: 'right' }}>24h</span>
        <span style={{ flex: 1, paddingLeft: 12 }}>Distribution</span>
      </div>

      {visible.map(a => {
        const scores = a.scores || {};
        return (
          <div key={a.asset} className="hover:bg-gray-50/40 transition-colors"
            style={{ display: 'flex', alignItems: 'center', gap: 0, padding: '5px 0' }}
            data-testid={`asset-${a.asset}`}>
            <span style={{ width: 72, fontSize: 12, fontWeight: 600, color: '#111827' }}>${a.asset}</span>
            <span style={{ width: 72, fontSize: 11, fontWeight: 600, color: ACTION_COLOR[a.action] || '#6b7280' }}>{a.action}</span>
            <span style={{ width: 50, textAlign: 'right', fontSize: 11, fontWeight: 500, color: '#6b7280', fontVariantNumeric: 'tabular-nums' }}>
              {(a.score * 100).toFixed(0)}
            </span>
            <span style={{ width: 80, textAlign: 'center', fontSize: 10, fontWeight: 500, color: PHASE_HEX[a.state] || '#6b7280' }}>{a.state}</span>
            <span style={{ width: 64, fontSize: 10, color: '#9ca3af' }}>{a.entry}</span>
            <span style={{
              width: 56, textAlign: 'right', fontSize: 11, fontWeight: 500, fontVariantNumeric: 'tabular-nums',
              color: a.priceChange24h > 0 ? '#16a34a' : a.priceChange24h < 0 ? '#ef4444' : '#9ca3af',
            }}>
              {a.priceChange24h > 0 ? '+' : ''}{a.priceChange24h?.toFixed(1)}%
            </span>
            <div style={{ flex: 1, display: 'flex', height: 3, borderRadius: 2, overflow: 'hidden', marginLeft: 12, background: '#f3f4f6' }}>
              {['accumulation', 'ignition', 'expansion', 'distribution'].map(p => (
                <div key={p} style={{ width: `${(scores[p] || 0) * 100}%`, background: PHASE_HEX[p.toUpperCase()] }} />
              ))}
            </div>
          </div>
        );
      })}

      {assets.length > 25 && (
        <button onClick={() => setExpanded(!expanded)}
          data-testid="toggle-assets-btn"
          style={{ display: 'flex', alignItems: 'center', gap: 4, margin: '8px auto 0', fontSize: 11, color: '#9ca3af', background: 'none', border: 'none', cursor: 'pointer' }}>
          {expanded
            ? <><ChevronUp style={{ width: 12, height: 12 }} /> less</>
            : <><ChevronDown style={{ width: 12, height: 12 }} /> all {assets.length}</>}
        </button>
      )}
    </div>
  );
}

/* ── CLUSTER SIGNALS ───────────────────────────────────────── */
function ClusterSignals({ clusters, assets }) {
  if (!clusters || clusters.length === 0) return null;

  return (
    <div style={{ marginBottom: 20 }} data-testid="cluster-signals">
      <div style={{ fontSize: 11, fontWeight: 600, color: '#111827', letterSpacing: '0.08em', marginBottom: 10 }}>
        CLUSTER SIGNALS
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 16 }}>
        {clusters.map(c => {
          const hex = PHASE_HEX[c.state] || '#6b7280';
          const topTokens = (c.assets || [])
            .map(sym => assets.find(a => a.asset === sym))
            .filter(Boolean)
            .sort((a, b) => b.score - a.score)
            .slice(0, 4);

          return (
            <div key={c.cluster} data-testid={`cluster-${c.cluster}`}>
              <div style={{ marginBottom: 4 }}>
                <span style={{ fontSize: 12, fontWeight: 600, color: '#111827' }}>{c.cluster}</span>
                <span style={{ fontSize: 10, fontWeight: 500, color: hex, marginLeft: 8 }}>{c.state}</span>
              </div>
              <div style={{ fontSize: 10, color: '#9ca3af', marginBottom: 6 }}>{c.assetCount} tokens</div>
              <div style={{ display: 'flex', height: 2, borderRadius: 1, overflow: 'hidden', background: '#e5e7eb', marginBottom: 6 }}>
                {['accumulation', 'ignition', 'expansion', 'distribution'].map(p => (
                  <div key={p} style={{ width: `${(c.scores?.[p] || 0) * 100}%`, background: PHASE_HEX[p.toUpperCase()] }} />
                ))}
              </div>
              {topTokens.length > 0 && (
                <div style={{ fontSize: 10, color: '#6b7280' }}>
                  {topTokens.map(t => (
                    <span key={t.asset} style={{ marginRight: 8, color: ACTION_COLOR[t.action] || '#6b7280', fontWeight: 700 }}>
                      ${t.asset}
                    </span>
                  ))}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

/* ── CAPITAL FLOW ──────────────────────────────────────────── */
function CapitalFlow({ rotations }) {
  if (!rotations || rotations.length === 0) return null;

  return (
    <div style={{ marginBottom: 20 }} data-testid="rotation-signals">
      <div style={{ fontSize: 11, fontWeight: 600, color: '#d97706', letterSpacing: '0.08em', marginBottom: 10 }}>
        CAPITAL FLOW
      </div>

      {rotations.map((r, i) => (
        <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '4px 0', fontSize: 12 }} data-testid={`rotation-${i}`}>
          <span style={{ color: '#6b7280' }}>{r.fromCluster}</span>
          <span style={{ color: '#d97706', fontWeight: 600 }}>&rarr;</span>
          <span style={{ color: '#111827', fontWeight: 600 }}>{r.toCluster}</span>
          <span style={{ color: '#6b7280', fontSize: 11, fontVariantNumeric: 'tabular-nums' }}>{(r.erp * 100).toFixed(0)}%</span>
          <span style={{ color: '#d97706', fontSize: 10, fontWeight: 700 }}>{r.class}</span>
        </div>
      ))}
    </div>
  );
}

/* ── MAIN PAGE ─────────────────────────────────────────────── */
export default function LifecyclePage() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const [lcRes, clRes, erRes] = await Promise.all([
        fetch(`${API}/api/connections/lifecycle`).then(r => r.json()),
        fetch(`${API}/api/connections/cluster-lifecycle`).then(r => r.json()),
        fetch(`${API}/api/connections/early-rotation/active`).then(r => r.json()),
      ]);

      if (lcRes.ok) {
        setData({
          assets: lcRes.data || [],
          clusters: clRes.data || [],
          rotations: erRes.data || [],
          marketState: lcRes.marketState || null,
          pumpSignals: lcRes.pumpSignals || [],
        });
      }
    } catch {}
    finally { setLoading(false); }
  }, []);

  useEffect(() => { loadData(); }, [loadData]);

  if (loading && !data) {
    return (
      <div className="flex items-center justify-center py-20">
        <RefreshCw className="w-5 h-5 animate-spin text-gray-300" />
      </div>
    );
  }

  if (!data) return null;

  const { assets, clusters, rotations, marketState, pumpSignals } = data;
  const counts = marketState?.phaseCounts || {};

  return (
    <div className="min-h-screen" data-testid="lifecycle-page">
      <div style={{ maxWidth: 1600, margin: '0 auto', padding: '16px 24px' }}>
        {/* Header */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 14 }}>
          <div>
            <h1 style={{ fontSize: 20, fontWeight: 600, color: '#111827', letterSpacing: '-0.02em', margin: 0 }}>Lifecycle</h1>
            <p style={{ fontSize: 11, color: '#9ca3af', margin: '2px 0 0' }}>buy / hold / exit</p>
          </div>
          <button onClick={loadData} disabled={loading}
            style={{ display: 'flex', alignItems: 'center', padding: '6px 14px', borderRadius: 8, background: '#111827', color: '#fff', border: 'none', cursor: 'pointer', opacity: loading ? 0.5 : 1 }}
            data-testid="refresh-btn">
            <RefreshCw style={{ width: 13, height: 13 }} className={loading ? 'animate-spin' : ''} />
          </button>
        </div>

        <div style={{ marginBottom: 14 }}>
          <PhaseBar counts={counts} dominant={marketState?.dominant} />
        </div>

        {marketState && <MarketState marketState={marketState} />}
        <PumpDetector signals={pumpSignals} />
        <AssetsTable assets={assets} />
        <ClusterSignals clusters={clusters} assets={assets} />
        <CapitalFlow rotations={rotations} />
      </div>
    </div>
  );
}
