/**
 * Labs Drilldown Drawer (P2) — State Probability + Risk Contribution + Explainability
 */

import { useState, useEffect, useCallback } from 'react';
import { X, FlaskConical, ArrowRight, Shield, Lightbulb } from 'lucide-react';

const API = process.env.REACT_APP_BACKEND_URL;

const REGIME_COLORS = {
  CAPITAL_EXIT: '#dc2626', ALT_ROTATION: '#16a34a',
  FLIGHT_TO_BTC: '#f59e0b', NEUTRAL: '#64748b',
};

function SL({ children }) {
  return <div className="text-card-title">{children}</div>;
}

export default function LabsDrawer({ isOpen, onClose }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API}/api/labs/drilldown?asset=BTCUSDT`);
      setData(await res.json());
    } catch {}
    setLoading(false);
  }, []);

  useEffect(() => {
    if (isOpen) fetchData();
  }, [isOpen, fetchData]);

  const state = data?.state || {};
  const risk = data?.risk || {};
  const explain = data?.explain || {};

  return (
    <>
      {/* Overlay */}
      {isOpen && <div className="fixed inset-0 z-40" style={{ background: 'rgba(0,0,0,0.1)' }} onClick={onClose} />}

      {/* Drawer */}
      <div className="fixed top-0 right-0 h-full z-50 transition-transform duration-300 overflow-y-auto"
        data-testid="labs-drawer"
        style={{
          width: 380,
          transform: isOpen ? 'translateX(0)' : 'translateX(100%)',
          background: '#fff',
          borderLeft: '1px solid #e2e8f0',
          boxShadow: isOpen ? '-8px 0 24px rgba(0,0,0,0.06)' : 'none',
        }}>

        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4" style={{ borderBottom: '1px solid #f1f5f9' }}>
          <div className="flex items-center gap-2">
            <FlaskConical className="w-4 h-4" style={{ color: '#6366f1' }} />
            <span className="text-sm font-bold" style={{ color: '#0f172a' }}>Labs Drilldown</span>
          </div>
          <button onClick={onClose} data-testid="labs-close" className="p-1 rounded-lg transition-colors"
            onMouseEnter={e => e.currentTarget.style.background = '#f1f5f9'}
            onMouseLeave={e => e.currentTarget.style.background = 'transparent'}>
            <X className="w-4 h-4" style={{ color: '#94a3b8' }} />
          </button>
        </div>

        {loading && <div className="p-5 text-center text-hint">Loading...</div>}

        {!loading && data && (
          <div className="p-5 space-y-6">

            {/* ═══ Section 1: State Probability ═══ */}
            <div data-testid="labs-state-probs">
              <SL>Regime Probabilities</SL>
              <div className="mt-3 space-y-2.5">
                {state.regimeProbs?.map((r, i) => {
                  const rc = REGIME_COLORS[r.id] || '#64748b';
                  return (
                    <div key={r.id} className="transition-all duration-200" style={{ animationDelay: `${i * 40}ms` }}>
                      <div className="flex items-center justify-between mb-1">
                        <div className="flex items-center gap-2">
                          <span className="text-hint font-medium" style={{ color: '#475569' }}>{r.id.replace(/_/g, ' ')}</span>
                          {r.current && <span className="text-badge px-1.5 py-0.5 rounded" style={{ background: `${rc}12`, color: rc }}>CURRENT</span>}
                        </div>
                        <span className="font-bold tabular-nums" style={{ color: rc, fontSize: 14 }}>{(r.p * 100).toFixed(1)}%</span>
                      </div>
                      <div className="h-1.5 rounded-full overflow-hidden" style={{ background: '#f1f5f9' }}>
                        <div className="h-full rounded-full transition-all duration-500" style={{ width: `${r.p * 100}%`, background: rc }} />
                      </div>
                    </div>
                  );
                })}
              </div>

              {/* Transitions */}
              <div className="mt-4 pt-3" style={{ borderTop: '1px solid #f1f5f9' }}>
                <SL>Transition Probabilities (from current)</SL>
                <div className="mt-2 space-y-1.5">
                  {state.transitions?.map((t, i) => {
                    const tc = REGIME_COLORS[t.to] || '#64748b';
                    return (
                      <div key={t.to} className="flex items-center justify-between">
                        <div className="flex items-center gap-1.5">
                          <ArrowRight className="w-3 h-3" style={{ color: '#cbd5e1' }} />
                          <span className="text-hint font-medium" style={{ color: '#475569' }}>{t.to.replace(/_/g, ' ')}</span>
                          {t.label && <span className="text-badge px-1 py-0.5 rounded" style={{ background: '#f1f5f9', color: '#94a3b8' }}>{t.label}</span>}
                        </div>
                        <span className="text-hint font-bold tabular-nums" style={{ color: tc }}>{(t.p * 100).toFixed(1)}%</span>
                      </div>
                    );
                  })}
                </div>

                {/* Meta */}
                {state.transitionMeta && (
                  <div className="mt-2.5 rounded-lg px-3 py-2" style={{ background: '#f8fafc' }}>
                    <div className="grid grid-cols-3 gap-2">
                      {[
                        { l: 'Inertia', v: state.transitionMeta.inertia },
                        { l: 'CPI Drift', v: state.transitionMeta.cpiDrift },
                        { l: 'RiskOff Mom', v: state.transitionMeta.riskOffMom },
                      ].map(m => (
                        <div key={m.l} className="text-center">
                          <div className="text-hint">{m.l}</div>
                          <div className="text-hint font-bold tabular-nums" style={{ color: m.v > 0 ? '#16a34a' : m.v < 0 ? '#dc2626' : '#64748b' }}>
                            {m.v > 0 ? '+' : ''}{m.v?.toFixed(3)}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </div>

            {/* ═══ Section 2: Risk Contribution ═══ */}
            <div data-testid="labs-risk-contrib">
              <div className="flex items-center gap-2 mb-3">
                <Shield className="w-3.5 h-3.5" style={{ color: '#dc2626' }} />
                <SL>Risk Contribution</SL>
              </div>

              {/* Split bars */}
              <div className="space-y-2.5">
                {[
                  { l: 'Macro', v: risk.split?.macro, c: '#d97706' },
                  { l: 'Core', v: risk.split?.core, c: '#6366f1' },
                  { l: 'Signals', v: risk.split?.signals, c: '#64748b' },
                ].map(s => (
                  <div key={s.l}>
                    <div className="flex justify-between mb-1">
                      <span className="text-hint font-medium" style={{ color: '#64748b' }}>{s.l}</span>
                      <span className="text-hint font-bold tabular-nums" style={{ color: s.c }}>{((s.v || 0) * 100).toFixed(0)}%</span>
                    </div>
                    <div className="h-2 rounded-full overflow-hidden" style={{ background: '#f1f5f9' }}>
                      <div className="h-full rounded-full transition-all duration-500" style={{ width: `${(s.v || 0) * 100}%`, background: s.c }} />
                    </div>
                  </div>
                ))}
              </div>

              {/* Drivers */}
              <div className="mt-4 pt-3" style={{ borderTop: '1px solid #f1f5f9' }}>
                <SL>Top Risk Drivers</SL>
                <div className="mt-2 space-y-2">
                  {risk.drivers?.map((dr, i) => {
                    const dc = dr.sign === '+' ? '#dc2626' : '#16a34a';
                    return (
                      <div key={i} className="flex items-center gap-3">
                        <span className="font-bold w-[48px] flex-shrink-0 tabular-nums" style={{ color: dc, fontSize: 14 }}>
                          {dr.sign}{dr.value.toFixed(3)}
                        </span>
                        <span className="text-hint font-medium flex-1" style={{ color: '#475569' }}>{dr.label}</span>
                        <div className="w-10 h-1 rounded-full overflow-hidden" style={{ background: '#f1f5f9' }}>
                          <div className="h-full rounded-full" style={{ width: `${dr.conf * 100}%`, background: dc, opacity: 0.6 }} />
                        </div>
                        <span className="text-hint tabular-nums">{(dr.conf * 100).toFixed(0)}%</span>
                      </div>
                    );
                  })}
                </div>
              </div>
            </div>

            {/* ═══ Section 3: Explainability ═══ */}
            <div data-testid="labs-explain">
              <div className="flex items-center gap-2 mb-3">
                <Lightbulb className="w-3.5 h-3.5" style={{ color: '#f59e0b' }} />
                <SL>Why This Decision</SL>
              </div>
              <div className="space-y-2 mb-3">
                {explain.bullets?.map((b, i) => (
                  <div key={i} className="flex items-start gap-2 text-hint font-medium" style={{ color: '#475569' }}>
                    <span className="text-hint font-bold" style={{ color: '#6366f1' }}>{i + 1}.</span>
                    {b}
                  </div>
                ))}
              </div>
              {explain.narrative && (
                <div className="rounded-lg px-3.5 py-2.5 text-hint italic leading-relaxed" style={{ background: '#f8fafc', color: '#64748b', border: '1px solid #f1f5f9' }}>
                  {explain.narrative}
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </>
  );
}
