/**
 * Narratives v2 — Decision Engine
 * Pipeline: Trade Setup → Narrative Flow → Rotation → Front-Run → Top Picks → Tokens → Smart Money Origin
 * Clean trader UI: no badges, no pills, no borders. Color = action only.
 */

import React, { useState, useEffect, useCallback } from 'react';
import { RefreshCw, ChevronDown, ChevronUp } from 'lucide-react';

const API = process.env.REACT_APP_BACKEND_URL || '';

const AC = {
  'BUY EARLY': '#16a34a', 'BUY': '#16a34a', 'WATCH': '#d97706',
  'LATE': '#9ca3af', 'AVOID': '#6b7280',
};
const PH = {
  IGNITION: '#16a34a', SEEDING: '#3b82f6', EXPANSION: '#d97706',
  SATURATION: '#ef4444', DECAY: '#6b7280',
};
const SIG = { STRONG: '#16a34a', EARLY: '#22c55e', FORMING: '#d97706', WEAK: '#6b7280', FIRST: '#16a34a' };

const R = (props) => <div style={{ display: 'flex', alignItems: 'center', gap: 16, padding: '6px 0', ...props.s }} {...props} />;

/* ── TRADE SETUP (hero) ────────────────────────────────── */
function TradeSetup({ setup }) {
  if (!setup) return null;
  const actionColor = AC[setup.action] || '#6b7280';

  return (
    <div style={{ background: '#0a0a0a', borderRadius: 10, padding: '24px 28px', marginBottom: 20 }} data-testid="trade-setup">
      <div style={{ fontSize: 11, fontWeight: 700, color: actionColor, letterSpacing: '0.08em', marginBottom: 10 }}>
        CURRENT OPPORTUNITY
      </div>

      <div style={{ display: 'flex', alignItems: 'baseline', gap: 12, marginBottom: 6 }}>
        <span style={{ fontSize: 20, fontWeight: 600, color: '#f9fafb' }}>{setup.narrative}</span>
        <span style={{ fontSize: 12, fontWeight: 500, color: PH[setup.phase] || '#6b7280' }}>{setup.phase}</span>
      </div>

      <div style={{ display: 'flex', gap: 20, marginBottom: 14, fontSize: 12, color: '#9ca3af' }}>
        {setup.rotation && (
          <span>Rotation: <span style={{ color: '#d97706' }}>{setup.rotation.from} → {setup.narrative}</span></span>
        )}
        {setup.frontRun && (
          <span>Front-run: <span style={{ color: '#22c55e' }}>{setup.frontRun}</span></span>
        )}
      </div>

      <div style={{ fontSize: 16, fontWeight: 600, color: actionColor, marginBottom: 14 }}>
        {setup.action}
      </div>

      {setup.tokens && setup.tokens.length > 0 && (
        <div style={{ display: 'flex', gap: 20 }}>
          {setup.tokens.map(t => (
            <div key={t.token}>
              <span style={{ fontSize: 13, fontWeight: 600, color: '#f9fafb', marginRight: 6 }}>${t.token}</span>
              <span style={{ fontSize: 11, fontWeight: 700, color: AC[t.action] || '#6b7280' }}>{t.action}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

/* ── NARRATIVE FLOW TABLE ──────────────────────────────── */
function NarrativeFlow({ narratives }) {
  if (!narratives?.length) return null;
  return (
    <div style={{ background: '#0a0a0a', borderRadius: 10, padding: '20px 24px', marginBottom: 20 }} data-testid="narrative-flow">
      <div style={{ fontSize: 11, fontWeight: 700, color: '#22c55e', letterSpacing: '0.08em', marginBottom: 12 }}>NARRATIVE FLOW</div>
      <div style={{ display: 'flex', gap: 16, padding: '0 0 6px', fontSize: 9, fontWeight: 600, color: '#4b5563', letterSpacing: '0.1em', textTransform: 'uppercase' }}>
        <span style={{ width: 180 }}>Narrative</span>
        <span style={{ width: 72 }}>Phase</span>
        <span style={{ width: 44, textAlign: 'right' }}>Score</span>
        <span style={{ width: 40, textAlign: 'right' }}>Vel</span>
        <span style={{ width: 56, textAlign: 'right' }}>Mentions</span>
        <span style={{ width: 32, textAlign: 'right' }}>Inf</span>
        <span style={{ width: 36, textAlign: 'center' }}>Conf</span>
        <span style={{ width: 90 }}>Action</span>
        <span style={{ flex: 1 }}>Tokens</span>
      </div>
      {narratives.map(n => (
        <R key={n.key} data-testid={`narrative-${n.key}`}>
          <span style={{ width: 180, fontSize: 13, fontWeight: 600, color: '#f9fafb' }}>{n.name}</span>
          <span style={{ width: 72, fontSize: 10, fontWeight: 500, color: PH[n.phase] || '#6b7280' }}>{n.phase}</span>
          <span style={{ width: 44, textAlign: 'right', fontSize: 12, fontWeight: 500, color: '#d1d5db', fontVariantNumeric: 'tabular-nums' }}>{(n.score * 100).toFixed(0)}</span>
          <span style={{ width: 40, textAlign: 'right', fontSize: 11, color: '#9ca3af', fontVariantNumeric: 'tabular-nums' }}>{n.velocity}</span>
          <span style={{ width: 56, textAlign: 'right', fontSize: 11, color: '#9ca3af', fontVariantNumeric: 'tabular-nums' }}>{n.mentions}</span>
          <span style={{ width: 32, textAlign: 'right', fontSize: 11, color: '#9ca3af', fontVariantNumeric: 'tabular-nums' }}>{n.influencers}</span>
          <span style={{ width: 36, textAlign: 'center', fontSize: 9, fontWeight: 700, color: n.confidence === 'HIGH' ? '#d1d5db' : '#4b5563' }}>{n.confidence}</span>
          <span style={{ width: 90, fontSize: 11, fontWeight: 600, color: AC[n.action] || '#6b7280' }}>{n.action}</span>
          <div style={{ flex: 1, fontSize: 10, color: '#6b7280' }}>
            {(n.tokens || []).map(t => <span key={t} style={{ marginRight: 8 }}>${t}</span>)}
          </div>
        </R>
      ))}
    </div>
  );
}

/* ── ROTATION FLOW (+ action) ──────────────────────────── */
function RotationFlow({ rotations }) {
  if (!rotations?.length) return null;
  return (
    <div style={{ background: '#0a0a0a', borderRadius: 10, padding: '20px 24px', marginBottom: 20 }} data-testid="rotation-flow">
      <div style={{ fontSize: 11, fontWeight: 600, color: '#d97706', letterSpacing: '0.08em', marginBottom: 12 }}>ROTATION FLOW</div>
      <div style={{ display: 'flex', gap: 16, padding: '0 0 6px', fontSize: 9, fontWeight: 600, color: '#4b5563', letterSpacing: '0.1em', textTransform: 'uppercase' }}>
        <span style={{ width: 320 }}>Direction</span>
        <span style={{ width: 44, textAlign: 'right' }}>Score</span>
        <span style={{ width: 60 }}>Signal</span>
        <span style={{ width: 60 }}>Action</span>
        <span style={{ flex: 1 }}>Top Tokens</span>
      </div>
      {rotations.map((r, i) => (
        <R key={i} data-testid={`rotation-${i}`}>
          <div style={{ width: 320, display: 'flex', alignItems: 'center', gap: 8 }}>
            <span style={{ fontSize: 12, color: '#6b7280' }}>{r.from}</span>
            <span style={{ fontSize: 12, fontWeight: 600, color: '#d97706' }}>&rarr;</span>
            <span style={{ fontSize: 13, fontWeight: 600, color: '#f9fafb' }}>{r.to}</span>
          </div>
          <span style={{ width: 44, textAlign: 'right', fontSize: 12, fontWeight: 500, color: '#d1d5db', fontVariantNumeric: 'tabular-nums' }}>{(r.score * 100).toFixed(0)}</span>
          <span style={{ width: 60, fontSize: 10, fontWeight: 600, color: SIG[r.signal] || '#6b7280' }}>{r.signal}</span>
          <span style={{ width: 60, fontSize: 10, fontWeight: 600, color: AC[r.action] || '#6b7280' }}>{r.action}</span>
          <div style={{ flex: 1, fontSize: 10, color: '#6b7280' }}>
            {(r.topTokens || []).map(t => <span key={t} style={{ marginRight: 8 }}>${t}</span>)}
          </div>
        </R>
      ))}
    </div>
  );
}

/* ── FRONT-RUN SIGNALS (STRONG/EARLY/WEAK) ─────────────── */
function FrontRunSignals({ signals }) {
  if (!signals?.length) return null;
  return (
    <div style={{ background: '#0a0a0a', borderRadius: 10, padding: '20px 24px', marginBottom: 20 }} data-testid="frontrun-signals">
      <div style={{ fontSize: 11, fontWeight: 700, color: '#3b82f6', letterSpacing: '0.08em', marginBottom: 12 }}>FRONT-RUN SIGNALS</div>
      <div style={{ display: 'flex', gap: 16, padding: '0 0 6px', fontSize: 9, fontWeight: 600, color: '#4b5563', letterSpacing: '0.1em', textTransform: 'uppercase' }}>
        <span style={{ width: 180 }}>Narrative</span>
        <span style={{ width: 44, textAlign: 'right' }}>Score</span>
        <span style={{ width: 60 }}>Signal</span>
        <span style={{ width: 40, textAlign: 'right' }}>Vel</span>
        <span style={{ width: 56, textAlign: 'right' }}>Mentions</span>
        <span style={{ width: 56, textAlign: 'right' }}>Inf Ratio</span>
        <span style={{ flex: 1 }}>Tokens</span>
      </div>
      {signals.map((s, i) => (
        <R key={i} data-testid={`frontrun-${i}`}>
          <span style={{ width: 180, fontSize: 13, fontWeight: 600, color: '#f9fafb' }}>{s.name}</span>
          <span style={{ width: 44, textAlign: 'right', fontSize: 12, fontWeight: 500, color: '#d1d5db', fontVariantNumeric: 'tabular-nums' }}>{(s.score * 100).toFixed(0)}</span>
          <span style={{ width: 60, fontSize: 10, fontWeight: 600, color: SIG[s.label] || '#6b7280' }}>{s.label}</span>
          <span style={{ width: 40, textAlign: 'right', fontSize: 11, color: '#9ca3af', fontVariantNumeric: 'tabular-nums' }}>{s.velocity}</span>
          <span style={{ width: 56, textAlign: 'right', fontSize: 11, color: '#9ca3af', fontVariantNumeric: 'tabular-nums' }}>{s.mentions}</span>
          <span style={{ width: 56, textAlign: 'right', fontSize: 11, color: '#9ca3af', fontVariantNumeric: 'tabular-nums' }}>{s.infRatio}</span>
          <div style={{ flex: 1, fontSize: 10, color: '#6b7280' }}>
            {(s.tokens || []).map(t => <span key={t} style={{ marginRight: 8 }}>${t}</span>)}
          </div>
        </R>
      ))}
    </div>
  );
}

/* ── TOP PICKS ─────────────────────────────────────────── */
function TopPicks({ picks }) {
  if (!picks?.length) return null;
  return (
    <div style={{ marginBottom: 20 }} data-testid="top-picks">
      <div style={{ fontSize: 11, fontWeight: 600, color: '#16a34a', letterSpacing: '0.08em', marginBottom: 10 }}>TOP PICKS</div>
      <div style={{ display: 'flex', gap: 24 }}>
        {picks.map(t => (
          <div key={t.token} data-testid={`pick-${t.token}`}>
            <span style={{ fontSize: 16, fontWeight: 600, color: '#111827', marginRight: 8 }}>${t.token}</span>
            <span style={{ fontSize: 12, fontWeight: 500, color: '#6b7280', fontVariantNumeric: 'tabular-nums', marginRight: 8 }}>{(t.score * 100).toFixed(0)}</span>
            <span style={{ fontSize: 12, fontWeight: 600, color: '#16a34a' }}>BUY</span>
          </div>
        ))}
      </div>
    </div>
  );
}

/* ── TOKENS TABLE ──────────────────────────────────────── */
function TokensTable({ tokens }) {
  const [expanded, setExpanded] = useState(false);
  if (!tokens?.length) return null;
  const visible = expanded ? tokens : tokens.slice(0, 15);
  return (
    <div style={{ marginBottom: 20 }} data-testid="narrative-tokens">
      <div style={{ fontSize: 11, fontWeight: 700, color: '#111827', letterSpacing: '0.08em', marginBottom: 10 }}>TOKENS</div>
      <div style={{ display: 'flex', gap: 16, padding: '0 0 6px', fontSize: 9, fontWeight: 600, color: '#9ca3af', letterSpacing: '0.1em', textTransform: 'uppercase' }}>
        <span style={{ width: 72 }}>Token</span>
        <span style={{ width: 44, textAlign: 'right' }}>Score</span>
        <span style={{ width: 64 }}>Action</span>
        <span style={{ width: 160 }}>Narrative</span>
        <span style={{ width: 72 }}>Phase</span>
        <span style={{ width: 56, textAlign: 'right' }}>Mentions</span>
        <span style={{ width: 56, textAlign: 'right' }}>Sentiment</span>
      </div>
      {visible.map(t => (
        <div key={`${t.token}-${t.narrativeKey}`} className="hover:bg-gray-50/40 transition-colors"
          style={{ display: 'flex', alignItems: 'center', gap: 16, padding: '5px 0' }} data-testid={`token-${t.token}`}>
          <span style={{ width: 72, fontSize: 12, fontWeight: 600, color: '#111827' }}>${t.token}</span>
          <span style={{ width: 44, textAlign: 'right', fontSize: 11, fontWeight: 500, color: '#6b7280', fontVariantNumeric: 'tabular-nums' }}>{(t.score * 100).toFixed(0)}</span>
          <span style={{ width: 64, fontSize: 11, fontWeight: 600, color: AC[t.action] || '#6b7280' }}>{t.action}</span>
          <span style={{ width: 160, fontSize: 10, color: '#9ca3af' }}>{t.narrative}</span>
          <span style={{ width: 72, fontSize: 10, fontWeight: 500, color: PH[t.phase] || '#6b7280' }}>{t.phase}</span>
          <span style={{ width: 56, textAlign: 'right', fontSize: 11, color: '#9ca3af', fontVariantNumeric: 'tabular-nums' }}>{t.mentions}</span>
          <span style={{ width: 56, textAlign: 'right', fontSize: 11, fontVariantNumeric: 'tabular-nums',
            color: t.sentiment > 0.5 ? '#16a34a' : t.sentiment > 0.3 ? '#d97706' : '#9ca3af' }}>{(t.sentiment * 100).toFixed(0)}%</span>
        </div>
      ))}
      {tokens.length > 15 && (
        <button onClick={() => setExpanded(!expanded)} data-testid="toggle-tokens-btn"
          style={{ display: 'flex', alignItems: 'center', gap: 4, margin: '8px auto 0', fontSize: 11, color: '#9ca3af', background: 'none', border: 'none', cursor: 'pointer' }}>
          {expanded ? <><ChevronUp style={{ width: 12, height: 12 }} /> less</> : <><ChevronDown style={{ width: 12, height: 12 }} /> all {tokens.length}</>}
        </button>
      )}
    </div>
  );
}

/* ── SMART MONEY ORIGIN ────────────────────────────────── */
function SmartMoneyOrigin({ origins }) {
  if (!origins?.length) return null;
  return (
    <div style={{ background: '#0a0a0a', borderRadius: 10, padding: '20px 24px', marginBottom: 20 }} data-testid="smart-money-origin">
      <div style={{ fontSize: 11, fontWeight: 700, color: '#a78bfa', letterSpacing: '0.08em', marginBottom: 12 }}>SMART MONEY ORIGIN</div>
      <div style={{ display: 'flex', gap: 16, padding: '0 0 6px', fontSize: 9, fontWeight: 600, color: '#4b5563', letterSpacing: '0.1em', textTransform: 'uppercase' }}>
        <span style={{ width: 140 }}>Author</span>
        <span style={{ width: 44, textAlign: 'right' }}>Score</span>
        <span style={{ width: 50 }}>Signal</span>
        <span style={{ width: 160 }}>Narrative</span>
        <span style={{ width: 72 }}>Token</span>
        <span style={{ width: 80, textAlign: 'right' }}>Reach</span>
        <span style={{ width: 50, textAlign: 'right' }}>Timing</span>
        <span style={{ width: 50, textAlign: 'right' }}>Impact</span>
      </div>
      {origins.map((o, i) => (
        <R key={i} data-testid={`origin-${i}`}>
          <a href={`https://twitter.com/${o.author}`} target="_blank" rel="noopener noreferrer"
            style={{ width: 140, fontSize: 12, fontWeight: 600, color: '#a78bfa', textDecoration: 'none' }}
            className="hover:underline">@{o.author}</a>
          <span style={{ width: 44, textAlign: 'right', fontSize: 12, fontWeight: 500, color: '#d1d5db', fontVariantNumeric: 'tabular-nums' }}>{(o.score * 100).toFixed(0)}</span>
          <span style={{ width: 50, fontSize: 10, fontWeight: 600, color: SIG[o.label] || '#6b7280' }}>{o.label}</span>
          <span style={{ width: 160, fontSize: 10, color: '#9ca3af' }}>{o.narrative}</span>
          <span style={{ width: 72, fontSize: 11, fontWeight: 500, color: '#d1d5db' }}>{o.token ? `$${o.token}` : ''}</span>
          <span style={{ width: 80, textAlign: 'right', fontSize: 10, color: '#6b7280', fontVariantNumeric: 'tabular-nums' }}>{o.reach >= 1000 ? `${(o.reach / 1000).toFixed(0)}K` : o.reach}</span>
          <span style={{ width: 50, textAlign: 'right', fontSize: 10, color: '#9ca3af', fontVariantNumeric: 'tabular-nums' }}>{(o.timing * 100).toFixed(0)}%</span>
          <span style={{ width: 50, textAlign: 'right', fontSize: 10, color: '#9ca3af', fontVariantNumeric: 'tabular-nums' }}>{(o.impact * 100).toFixed(0)}%</span>
        </R>
      ))}
    </div>
  );
}

/* ── MAIN PAGE ─────────────────────────────────────────── */
export default function NarrativesPage() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API}/api/narrative-flow`);
      const json = await res.json();
      if (json.ok) setData(json);
    } catch {}
    finally { setLoading(false); }
  }, []);

  useEffect(() => { loadData(); }, [loadData]);

  if (loading && !data) {
    return <div className="flex items-center justify-center py-20"><RefreshCw className="w-5 h-5 animate-spin text-gray-300" /></div>;
  }
  if (!data) return null;

  return (
    <div className="min-h-screen" data-testid="narratives-page">
      <div style={{ maxWidth: 1600, margin: '0 auto', padding: '16px 24px' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 14 }}>
          <div>
            <h1 style={{ fontSize: 20, fontWeight: 600, color: '#111827', letterSpacing: '-0.02em', margin: 0 }}>Narratives</h1>
            <p style={{ fontSize: 11, color: '#9ca3af', margin: '2px 0 0' }}>capital flow radar</p>
          </div>
          <button onClick={loadData} disabled={loading}
            style={{ display: 'flex', alignItems: 'center', padding: '6px 14px', borderRadius: 8, background: '#111827', color: '#fff', border: 'none', cursor: 'pointer', opacity: loading ? 0.5 : 1 }}
            data-testid="refresh-btn">
            <RefreshCw style={{ width: 13, height: 13 }} className={loading ? 'animate-spin' : ''} />
          </button>
        </div>

        <TradeSetup setup={data.tradeSetup} />
        <NarrativeFlow narratives={data.narratives} />
        <RotationFlow rotations={data.rotations} />
        <FrontRunSignals signals={data.frontRuns} />
        <TopPicks picks={data.topPicks} />
        <TokensTable tokens={data.tokens} />
        <SmartMoneyOrigin origins={data.origins} />
      </div>
    </div>
  );
}
