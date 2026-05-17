/**
 * Overview V2.3 Intelligence — Decision Intelligence Dashboard
 * Typography: Gilroy design system (no font-mono for numbers)
 */

import { useState, useEffect, useCallback, useMemo, lazy, Suspense } from 'react';
import { createPortal } from 'react-dom';
import {
  RefreshCw, Loader2, TrendingUp, TrendingDown, Minus,
  ShieldAlert, AlertTriangle, ArrowRight, Lock, Target,
  ChevronRight, ChevronDown, Layers, Zap, GitBranch, FlaskConical
} from 'lucide-react';
import { AreaChart, Area, ResponsiveContainer, Tooltip } from 'recharts';

const PositionHistoryPanel = lazy(() => import('./PositionHistoryPanel'));
const LabsDrawer = lazy(() => import('./LabsDrawer'));
import TacticalPanel from '../components/TacticalPanel';

const API = process.env.REACT_APP_BACKEND_URL;

/* ═══════════ CONSTANTS ═══════════ */

const ACTION_CFG = {
  BUY:      { color: '#16a34a', bg: '#f0fdf4', border: '#bbf7d0', icon: TrendingUp, glow: '0 0 20px rgba(22,163,74,0.15)' },
  SELL:     { color: '#dc2626', bg: '#fef2f2', border: '#fecaca', icon: TrendingDown, glow: '0 0 20px rgba(220,38,38,0.15)' },
  HOLD:     { color: '#d97706', bg: '#fffbeb', border: '#fde68a', icon: Minus, glow: '0 0 20px rgba(217,119,6,0.12)' },
  NO_TRADE: { color: '#64748b', bg: '#f8fafc', border: '#e2e8f0', icon: Lock, glow: 'none' },
};
const MODE_CFG = {
  DEFENSIVE:  { color: '#dc2626', bg: 'transparent' },
  NEUTRAL:    { color: '#d97706', bg: 'transparent' },
  AGGRESSIVE: { color: '#16a34a', bg: 'transparent' },
};
const REGIME_C = { ACCUMULATION: '#16a34a', MARKUP: '#059669', DISTRIBUTION: '#dc2626', MARKDOWN: '#b91c1c' };
const ALT_C = { ALT_BULLISH: '#16a34a', ALT_BEARISH: '#dc2626', ALT_NEUTRAL: '#64748b' };
const LAYER_C = {
  macro: { color: '#d97706', bg: 'transparent' },
  core: { color: '#6366f1', bg: 'transparent' },
  signals: { color: '#64748b', bg: 'transparent' },
};

/* ═══════════ SHARED ═══════════ */

function _clamp(x, lo, hi) { return Math.max(lo, Math.min(hi, x)); }

/** Rich dark tooltip — renders via portal so it's never clipped */
function InfoTip({ children, content }) {
  const [show, setShow] = useState(false);
  const [pos, setPos] = useState({ x: 0, y: 0 });

  const handleEnter = (e) => {
    const rect = e.currentTarget.getBoundingClientRect();
    const tipW = 260;
    let x = rect.left;
    if (x + tipW > window.innerWidth - 16) x = window.innerWidth - tipW - 16;
    if (x < 8) x = 8;
    let y = rect.bottom + 6;
    if (y + 200 > window.innerHeight) y = rect.top - 6;
    setPos({ x, y, above: y < rect.top });
    setShow(true);
  };

  return (
    <span className="relative inline-flex cursor-help" onMouseEnter={handleEnter} onMouseLeave={() => setShow(false)}>
      {children}
      {show && createPortal(
        <div className="fixed max-w-[260px] min-w-[180px]"
          style={{ left: pos.x, top: pos.above ? undefined : pos.y, bottom: pos.above ? `${window.innerHeight - pos.y}px` : undefined, zIndex: 99999, textTransform: 'none', pointerEvents: 'none' }}>
          <div className="rounded-lg px-3 py-2.5 shadow-xl" style={{ background: '#0f172a', color: '#e2e8f0', border: '1px solid #1e293b' }}>
            {content}
          </div>
        </div>,
        document.body
      )}
    </span>
  );
}

/** Tooltip content builder */
function TipTitle({ children }) {
  return <div className="font-medium text-white" style={{ fontSize: 12, letterSpacing: '0.01em' }}>{children}</div>;
}
function TipDesc({ children }) {
  return <div style={{ fontSize: 11, color: '#94a3b8', lineHeight: 1.35, fontWeight: 400 }}>{children}</div>;
}
function TipVal({ label, color, children }) {
  return (
    <div style={{ fontSize: 10.5, lineHeight: 1.3 }}>
      <span className="font-medium" style={{ color: color || '#cbd5e1' }}>{label}</span>
      <span style={{ color: '#64748b', fontWeight: 400 }}> — {children}</span>
    </div>
  );
}

/** Section Label — uses platform's card-title style: 14px Semibold Uppercase */
function SL({ children }) {
  return <div className="text-card-title">{children}</div>;
}

function ImpactBar({ value, maxAbs = 1 }) {
  const pct = Math.min(Math.abs(value) / maxAbs * 100, 100);
  const c = value > 0.01 ? '#16a34a' : value < -0.01 ? '#dc2626' : '#94a3b8';
  return (
    <div className="h-[3px] w-16 rounded-full overflow-hidden" style={{ background: '#e2e8f0' }}>
      <div className="h-full rounded-full transition-all duration-500" style={{ width: `${pct}%`, background: c }} />
    </div>
  );
}

function FadeIn({ delay = 0, children }) {
  const [show, setShow] = useState(false);
  useEffect(() => { const t = setTimeout(() => setShow(true), delay); return () => clearTimeout(t); }, [delay]);
  return <div className="transition-all duration-400" style={{ opacity: show ? 1 : 0, transform: show ? 'translateY(0)' : 'translateY(6px)' }}>{children}</div>;
}

function Card({ children, testId, className = '' }) {
  return <div className={`rounded-2xl p-5 ${className}`} data-testid={testId} style={{ background: '#fff', border: '1px solid #e2e8f0' }}>{children}</div>;
}

/* ═══════════ DECISION CONSOLE 2.0 (HERO) ═══════════ */

function DecisionConsole({ decision, positionHistory }) {
  const sparkData = useMemo(() =>
    (positionHistory || []).map((p, i) => ({ i, v: p.sizeMult, c: p.confidence })),
    [positionHistory]
  );

  if (!decision) return null;
  const ac = ACTION_CFG[decision.action] || ACTION_CFG.NO_TRADE;
  const mc = MODE_CFG[decision.mode] || MODE_CFG.DEFENSIVE;
  const Icon = ac.icon;

  return (
    <div className="rounded-2xl overflow-hidden" data-testid="decision-console"
      style={{ background: ac.bg, border: `1.5px solid ${ac.border}`, boxShadow: ac.glow }}>

      {/* === TOP: Action + Size === */}
      <div className="px-6 pt-5 pb-4">
        <div className="flex items-start justify-between">
          <div>
            <SL><InfoTip content={<>
              <TipTitle>Final Decision</TipTitle>
              <TipDesc>Engine output after Macro → Core → Signals cascade.</TipDesc>
              <TipVal label="BUY" color="#16a34a">Long / add to position</TipVal>
              <TipVal label="SELL" color="#dc2626">Short / reduce exposure</TipVal>
              <TipVal label="HOLD" color="#d97706">Keep current, no new edge</TipVal>
              <TipVal label="NO_TRADE" color="#64748b">Blocked by macro gate</TipVal>
            </>}>Final Decision</InfoTip></SL>
            <div className="flex items-center gap-3 mt-2 flex-wrap">
              <span className="inline-flex items-center gap-2.5"
                data-testid="decision-action"
                style={{ color: ac.color, fontSize: 20, fontWeight: 700, letterSpacing: '-0.01em' }}>
                <Icon className="w-6 h-6" /> {decision.action.replace('_', ' ')}
              </span>
              <span className="text-badge font-bold" style={{ color: mc.color }}>{decision.mode}</span>
              {decision.gates?.map(g => (
                <span key={g} className="text-badge flex items-center gap-1 font-bold"
                  data-testid={`gate-${g}`}
                  style={{ color: '#dc2626' }}>
                  <ShieldAlert className="w-3 h-3" /> {g.replace(/_/g, ' ')}
                </span>
              ))}
            </div>
          </div>

          {/* Size + Confidence + Sparkline */}
          <div className="text-right flex-shrink-0 min-w-[160px]">
            <div data-testid="decision-size" style={{ fontSize: 48, fontWeight: 700, lineHeight: 1, color: ac.color, letterSpacing: '-0.02em' }}>
              {decision.sizeMult.toFixed(2)}<span style={{ fontSize: 20, fontWeight: 600 }}>x</span>
            </div>
            <div className="flex items-center justify-end gap-4 mt-2">
              <div className="text-right">
                <InfoTip content={<>
                  <TipTitle>Confidence</TipTitle>
                  <TipDesc>Model certainty. Higher = larger position size.</TipDesc>
                  <TipVal label=">70%" color="#16a34a">High</TipVal>
                  <TipVal label="40-70%" color="#d97706">Medium</TipVal>
                  <TipVal label="&lt;40%" color="#dc2626">Low</TipVal>
                </>}><div className="text-hint">Confidence</div></InfoTip>
                <div className="text-value-sm" style={{ color: ac.color }}>{(decision.confidence * 100).toFixed(0)}%</div>
              </div>
              {decision.stability && (
                <div className="text-right">
                <InfoTip content={<>
                  <TipTitle>Stability</TipTitle>
                  <TipDesc>Decision consistency: 1 - |dir(t) - dir(t-1)|</TipDesc>
                  <TipVal label=">80%" color="#16a34a">Stable</TipVal>
                  <TipVal label="&lt;50%" color="#dc2626">Frequent flips</TipVal>
                </>}><div className="text-hint">Stability</div></InfoTip>
                  <div className="text-value-sm"
                    style={{ color: decision.stability.index > 0.8 ? '#16a34a' : decision.stability.index > 0.5 ? '#d97706' : '#dc2626' }}>
                    {(decision.stability.index * 100).toFixed(0)}%
                  </div>
                </div>
              )}
            </div>
            {/* Position History Sparkline */}
            {sparkData.length > 2 && (
              <div className="mt-2 h-[28px]" data-testid="position-history-sparkline" style={{ minWidth: 100 }}>
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={sparkData}>
                    <defs>
                      <linearGradient id="sparkGrad" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stopColor={ac.color} stopOpacity={0.3} />
                        <stop offset="100%" stopColor={ac.color} stopOpacity={0} />
                      </linearGradient>
                    </defs>
                    <Area type="monotone" dataKey="v" stroke={ac.color} strokeWidth={1.5} fill="url(#sparkGrad)" dot={false} />
                    <Tooltip content={({ payload }) => {
                      if (!payload?.[0]) return null;
                      const d = payload[0].payload;
                      return <div className="bg-white shadow-lg rounded-lg px-2 py-1 border" style={{ borderColor: '#e2e8f0' }}>
                        <span className="text-hint font-semibold">{d.v.toFixed(2)}x</span>
                        <span className="text-hint ml-1" style={{ color: '#94a3b8' }}>conf {(d.c * 100).toFixed(0)}%</span>
                      </div>;
                    }} />
                  </AreaChart>
                </ResponsiveContainer>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* === STRENGTH GAUGE === */}
      <div className="mx-6 mb-3">
        <div className="flex items-center justify-between mb-1">
          <InfoTip content={<>
            <TipTitle>Decision Strength</TipTitle>
            <TipDesc>Directional force (directionFinal). Distance from zero = conviction.</TipDesc>
            <TipVal label="+" color="#16a34a">Bullish</TipVal>
            <TipVal label="−" color="#dc2626">Bearish</TipVal>
          </>}><span className="text-hint uppercase font-semibold tracking-wide">Decision Strength</span></InfoTip>
          <span className="text-hint font-bold tabular-nums" style={{
            color: (decision.directionFinal || 0) > 0.1 ? '#16a34a' : (decision.directionFinal || 0) < -0.1 ? '#dc2626' : '#64748b'
          }}>{(decision.directionFinal || 0) > 0 ? '+' : ''}{(decision.directionFinal || 0).toFixed(3)}</span>
        </div>
        <div className="h-2 rounded-full overflow-hidden relative" style={{ background: '#e2e8f0' }} data-testid="strength-gauge">
          <div className="absolute top-0 left-1/2 w-px h-full" style={{ background: '#cbd5e1', zIndex: 1 }} />
          {(() => {
            const df = _clamp(decision.directionFinal || 0, -1, 1);
            const pct = Math.abs(df) * 50;
            const isPos = df >= 0;
            return <div className="absolute top-0 h-full rounded-full transition-all duration-500"
              style={{ width: `${pct}%`, left: isPos ? '50%' : `${50 - pct}%`, background: isPos ? '#16a34a' : '#dc2626' }} />;
          })()}
        </div>
      </div>

      {/* === REASONS === */}
      <div className="mx-6 rounded-xl p-4 mb-4" style={{ background: 'rgba(255,255,255,0.7)', border: '1px solid rgba(226,232,240,0.6)' }}>
        <SL><InfoTip content={<>
          <TipTitle>Impact Analysis</TipTitle>
          <TipDesc>% contribution of each layer to the final decision.</TipDesc>
          <TipVal label="Macro" color="#d97706">Regime, risk-off, F&G gates</TipVal>
          <TipVal label="Core" color="#6366f1">Direction, regime, edge</TipVal>
          <TipVal label="Signals" color="#64748b">Execution bias, on-chain, flows</TipVal>
        </>}>Impact Analysis</InfoTip></SL>
        <div className="mt-3 space-y-2.5">
          {decision.reasons?.map((r, i) => {
            const lc = LAYER_C[r.layer] || LAYER_C.signals;
            const impColor = r.impact > 0.01 ? '#16a34a' : r.impact < -0.01 ? '#dc2626' : '#64748b';
            const pct = r.impactPct ?? 0;
            return (
              <div key={i} className="flex items-center gap-3" data-testid={`reason-${r.layer}`}>
                <span className="text-badge w-[60px] text-center flex-shrink-0 font-bold"
                  style={{ color: lc.color }}>{r.layer}</span>
                <span className="text-body flex-1" style={{ color: '#475569' }}>{r.text}</span>
                <div className="h-[3px] w-16 rounded-full overflow-hidden" style={{ background: '#e2e8f0' }}>
                  <div className="h-full rounded-full transition-all duration-500" style={{ width: `${pct}%`, background: lc.color }} />
                </div>
                <span className="font-semibold w-[52px] text-right flex-shrink-0 tabular-nums"
                  style={{ color: impColor, fontSize: 14 }}>
                  {pct.toFixed(0)}%
                </span>
              </div>
            );
          })}
        </div>
      </div>

      {/* === BOTTOM ROW: Allocation + Size Breakdown + Flip Triggers === */}
      <div className="px-6 pb-5 grid grid-cols-3 gap-3">
        {/* Allocation */}
        <div className="rounded-xl p-3.5" style={{ background: 'rgba(255,255,255,0.7)', border: '1px solid rgba(226,232,240,0.6)' }}>
          <SL><InfoTip content={<>
            <TipTitle>Allocation</TipTitle>
            <TipDesc>Recommended portfolio split.</TipDesc>
            <TipVal label="BTC" color="#f59e0b">Bitcoin share</TipVal>
            <TipVal label="ALTS" color="#8b5cf6">Altcoin share</TipVal>
            <TipVal label="STABLE" color="#94a3b8">Stablecoins / cash</TipVal>
          </>}>Allocation</InfoTip></SL>
          <div className="mt-3 space-y-2.5">
            {[
              { label: 'BTC', value: decision.allocation?.btc, color: '#f59e0b' },
              { label: 'ALTS', value: decision.allocation?.alts, color: '#8b5cf6' },
              { label: 'STABLE', value: decision.allocation?.stable, color: '#94a3b8' },
            ].map(a => (
              <div key={a.label} className="flex items-center justify-between">
                <span className="text-hint font-medium">{a.label}</span>
                <div className="flex items-center gap-2">
                  <div className="w-12 h-1.5 rounded-full overflow-hidden" style={{ background: '#e2e8f0' }}>
                    <div className="h-full rounded-full" style={{ width: `${a.value || 0}%`, background: a.color }} />
                  </div>
                  <span className="font-bold tabular-nums w-[36px] text-right" style={{ color: a.color, fontSize: 14 }}>{a.value?.toFixed(0)}%</span>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Size Breakdown */}
        <div className="rounded-xl p-3.5" style={{ background: 'rgba(255,255,255,0.7)', border: '1px solid rgba(226,232,240,0.6)' }}>
          <SL><InfoTip content={<>
            <TipTitle>Size Breakdown</TipTitle>
            <TipDesc>Multipliers that compose the final position size.</TipDesc>
            <TipVal label="Edge">Directional signal strength</TipVal>
            <TipVal label="Risk">Reduction at high risk</TipVal>
            <TipVal label="Sync">Layer alignment (>1 = bonus)</TipVal>
          </>}>Size Breakdown</InfoTip></SL>
          <div className="mt-3 space-y-2.5">
            {[
              { label: 'Edge', value: decision.sizeBreakdown?.edgeStrength, maxV: 1 },
              { label: 'Confidence', value: decision.sizeBreakdown?.confFactor, maxV: 1 },
              { label: 'Risk', value: decision.sizeBreakdown?.riskFactor, maxV: 1 },
              { label: 'Sync', value: decision.sizeBreakdown?.syncFactor, maxV: 2 },
            ].map(s => (
              <div key={s.label} className="flex items-center justify-between">
                <span className="text-hint">{s.label}</span>
                <div className="flex items-center gap-2">
                  <div className="w-10 h-1.5 rounded-full overflow-hidden" style={{ background: '#e2e8f0' }}>
                    <div className="h-full rounded-full" style={{
                      width: `${Math.min((s.value || 0) / s.maxV * 100, 100)}%`,
                      background: (s.value || 0) > 0.5 ? '#16a34a' : '#d97706'
                    }} />
                  </div>
                  <span className="font-semibold tabular-nums w-[44px] text-right" style={{ fontSize: 13, color: '#1e293b' }}>
                    {s.value?.toFixed(3)}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Flip Triggers */}
        <div className="rounded-xl p-3.5" style={{ background: 'rgba(255,255,255,0.7)', border: '1px solid rgba(226,232,240,0.6)' }}>
          <SL><InfoTip content={<>
            <TipTitle>Flip Triggers</TipTitle>
            <TipDesc>Conditions that would change the current decision.</TipDesc>
            <TipVal label="Red" color="#dc2626">Current value</TipVal>
            <TipVal label="Green" color="#16a34a">Target to flip</TipVal>
          </>}>Flip Triggers</InfoTip></SL>
          <div className="mt-3 space-y-3">
            {decision.flipTriggers?.map((ft, i) => (
              <div key={i}>
                <div className="text-body font-medium" style={{ color: '#475569', fontSize: 13 }}>{ft.condition}</div>
                <div className="flex items-center gap-1.5 mt-0.5">
                  <span className="font-bold tabular-nums" style={{ color: '#dc2626', fontSize: 12 }}>{ft.current}</span>
                  <ChevronRight className="w-3 h-3" style={{ color: '#cbd5e1' }} />
                  <span className="font-bold tabular-nums" style={{ color: '#16a34a', fontSize: 12 }}>{ft.target}</span>
                </div>
              </div>
            ))}
            {(!decision.flipTriggers || decision.flipTriggers.length === 0) && (
              <span className="text-hint italic">Stable</span>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

/* ═══════════ DECISION TRACE (collapsible) ═══════════ */

function DecisionTrace({ trace }) {
  const [open, setOpen] = useState(false);
  if (!trace) return null;
  return (
    <Card testId="decision-trace">
      <button onClick={() => setOpen(!open)} className="w-full flex items-center justify-between" data-testid="trace-toggle">
        <div className="flex items-center gap-2">
          <GitBranch className="w-4 h-4" style={{ color: '#6366f1' }} />
          <SL>Decision Trace</SL>
          {!open && (
            <span className="text-hint font-bold tabular-nums ml-2" style={{ color: '#6366f1' }}>
              Dir: {trace.steps?.[trace.steps.length - 1]?.value} → Size: {trace.sizeSteps?.[trace.sizeSteps.length - 1]?.value}
            </span>
          )}
        </div>
        <ChevronDown className="w-4 h-4 transition-transform" style={{ color: '#94a3b8', transform: open ? 'rotate(180deg)' : '' }} />
      </button>

      <div className="overflow-hidden transition-all duration-200" style={{ maxHeight: open ? 300 : 0, opacity: open ? 1 : 0, marginTop: open ? 12 : 0 }}>
      {/* Direction path */}
      <div className="flex items-center gap-1 flex-wrap mb-3">
        {trace.steps?.map((step, i) => {
          const isResult = step.name.startsWith('=');
          const c = isResult ? '#6366f1' : '#475569';
          return (
            <div key={i} className="flex items-center gap-1">
              {i > 0 && !isResult && <ArrowRight className="w-3 h-3 flex-shrink-0" style={{ color: '#cbd5e1' }} />}
              <div className="rounded-lg px-2.5 py-1.5 text-center"
                style={{ background: isResult ? 'rgba(99,102,241,0.06)' : '#f8fafc', border: `1px solid ${isResult ? 'rgba(99,102,241,0.15)' : '#e2e8f0'}` }}>
                <div className="text-hint" style={{ fontSize: 10 }}>{step.name}</div>
                <div className="font-bold tabular-nums" style={{ color: c, fontSize: 14 }}>{step.value}</div>
              </div>
            </div>
          );
        })}
      </div>

      {/* Size math */}
      <div className="rounded-lg p-3" style={{ background: '#f8fafc', border: '1px solid #e2e8f0' }}>
        <div className="text-hint uppercase font-semibold tracking-wide mb-2">Position Size Path</div>
        <div className="flex items-center gap-1 flex-wrap">
          {trace.sizeSteps?.map((step, i) => {
            const isResult = step.name.startsWith('=');
            return (
              <div key={i} className="flex items-center gap-1">
                {i > 0 && !isResult && <span className="font-bold" style={{ color: '#cbd5e1', fontSize: 12 }}>×</span>}
                {isResult && <span className="font-bold" style={{ color: '#6366f1', fontSize: 12 }}>=</span>}
                <div className="text-center group relative">
                  <div className="rounded-md px-2 py-1" style={{ background: isResult ? 'rgba(99,102,241,0.06)' : 'transparent' }}>
                    <div className="text-hint" style={{ fontSize: 10 }}>{step.name.replace('= ', '')}</div>
                    <div className="font-bold tabular-nums" style={{ color: isResult ? '#6366f1' : '#475569', fontSize: 13 }}>{step.value}</div>
                  </div>
                  <div className="hidden group-hover:block absolute z-10 bottom-full left-1/2 -translate-x-1/2 mb-1 px-2 py-1 rounded-md shadow-lg whitespace-nowrap"
                    style={{ background: '#1e293b', color: '#e2e8f0', fontSize: 10 }}>{step.formula}</div>
                </div>
              </div>
            );
          })}
        </div>
      </div>
      </div>
    </Card>
  );
}

/* ═══════════ CORE SNAPSHOT ═══════════ */

function CoreSnapshotPanel({ core }) {
  if (!core) return null;
  const rc = REGIME_C[core.regime] || '#64748b';
  const bc = core.bias === 'BULLISH' ? '#16a34a' : core.bias === 'BEARISH' ? '#dc2626' : '#64748b';
  const pers = core.persistence;
  return (
    <Card testId="core-snapshot">
      <div className="flex items-center justify-between mb-1">
        <SL><InfoTip content={<>
          <TipTitle>Market State</TipTitle>
          <TipDesc>Current price structure type.</TipDesc>
          <TipVal label="Accumulation" color="#16a34a">Base building. Smart money enters</TipVal>
          <TipVal label="Markup" color="#059669">Uptrend. Follow momentum</TipVal>
          <TipVal label="Distribution" color="#dc2626">Topping. Reduce exposure</TipVal>
          <TipVal label="Markdown" color="#b91c1c">Downtrend. Short bias</TipVal>
        </>}>Market State</InfoTip></SL>
        {pers && !pers.isNew && (
          <span className="text-badge font-medium" style={{ color: '#94a3b8' }}>
            {pers.periods} cycles
          </span>
        )}
      </div>
      <div className="flex items-center justify-between mb-3 mt-2">
        <div className="flex items-center gap-2">
          <span className="text-badge font-bold" style={{ color: rc }}>{core.regime}</span>
          <span className="text-hint tabular-nums">{(core.regimeProb * 100).toFixed(0)}%</span>
          <span className="text-badge font-bold" style={{ color: bc }}>{core.bias}</span>
        </div>
        <span className="text-value-sm tabular-nums" style={{ color: bc }}>
          Edge {core.edgeScore > 0 ? '+' : ''}{core.edgeScore.toFixed(2)}
        </span>
      </div>
      {/* Outcome bar */}
      <div className="flex gap-0.5 rounded-lg overflow-hidden h-2.5">
        <div style={{ width: `${core.outcomes.bull * 100}%`, background: '#16a34a', borderRadius: '6px 0 0 6px' }} />
        <div style={{ width: `${core.outcomes.base * 100}%`, background: '#94a3b8' }} />
        <div style={{ width: `${core.outcomes.bear * 100}%`, background: '#dc2626', borderRadius: '0 6px 6px 0' }} />
      </div>
      <div className="flex justify-between mt-1.5">
        <span className="text-hint font-medium" style={{ color: '#16a34a' }}>Bull {(core.outcomes.bull * 100).toFixed(0)}%</span>
        <span className="text-hint font-medium" style={{ color: '#94a3b8' }}>Base {(core.outcomes.base * 100).toFixed(0)}%</span>
        <span className="text-hint font-medium" style={{ color: '#dc2626' }}>Bear {(core.outcomes.bear * 100).toFixed(0)}%</span>
      </div>
    </Card>
  );
}

/* ═══════════ SIGNALS SUMMARY ═══════════ */

function SignalsSummaryPanel({ signals }) {
  if (!signals) return null;
  const bc = signals.bias === 'BULLISH_PRESSURE' ? '#16a34a' : signals.bias === 'BEARISH_PRESSURE' ? '#dc2626' : '#64748b';
  return (
    <Card testId="signals-summary">
      <div className="flex items-center justify-between mb-1">
        <SL><InfoTip content={<>
          <TipTitle>Signals</TipTitle>
          <TipDesc>Aggregate of on-chain, exchange flows, acc/dist.</TipDesc>
          <TipVal label="Ex">Exchange flows</TipVal>
          <TipVal label="AD">Accumulation / Distribution</TipVal>
          <TipVal label="OC">On-chain activity</TipVal>
        </>}>Signals</InfoTip></SL>
        <span className="text-badge font-medium" style={{ color: '#94a3b8' }}>{signals.activityMode}</span>
      </div>
      <div className="flex items-baseline gap-2 mb-2 mt-2">
        <span className="text-value-md tabular-nums" style={{ color: bc }}>
          {signals.executionScore > 0 ? '+' : ''}{signals.executionScore.toFixed(2)}
        </span>
        <span className="text-badge font-bold" style={{ color: bc }}>
          {signals.bias?.replace('_', ' ')}
        </span>
      </div>
      {/* Score bar */}
      <div className="h-1.5 w-full rounded-full overflow-hidden relative" style={{ background: '#e2e8f0' }}>
        {(() => {
          const pct = Math.min(Math.abs(signals.executionScore) * 100, 100);
          const isPos = signals.executionScore >= 0;
          return <div className="absolute top-0 h-full rounded-full transition-all duration-500"
            style={{ width: `${pct / 2}%`, left: isPos ? '50%' : `${50 - pct / 2}%`, background: isPos ? '#16a34a' : '#dc2626' }} />;
        })()}
        <div className="absolute top-0 left-1/2 w-px h-full" style={{ background: '#cbd5e1' }} />
      </div>
      {/* Contributors */}
      <div className="mt-3 flex gap-4">
        {Object.entries(signals.contributors || {}).map(([k, v]) => {
          const c = v > 0.001 ? '#16a34a' : v < -0.001 ? '#dc2626' : '#64748b';
          return (
            <div key={k} className="flex items-center gap-1.5">
              <span className="text-hint font-medium">{{ exchange: 'Ex', accDist: 'AD', onchain: 'OC' }[k]}</span>
              <span className="font-semibold tabular-nums" style={{ color: c, fontSize: 13 }}>{v > 0 ? '+' : ''}{v.toFixed(3)}</span>
            </div>
          );
        })}
      </div>
      {signals.topEvents?.length > 0 && (
        <div className="mt-3 pt-3 space-y-1.5" style={{ borderTop: '1px solid #f1f5f9' }}>
          {signals.topEvents.map((ev, i) => (
            <div key={i} className="flex items-center justify-between">
              <div className="flex items-center gap-1.5">
                <span className="text-badge font-bold" style={{ color: LAYER_C[ev.source]?.color || '#94a3b8' }}>{ev.source}</span>
                <span className="text-hint font-medium" style={{ color: '#475569' }}>{ev.title}</span>
              </div>
              <span className="text-hint font-semibold" style={{ color: ev.impact < 0 ? '#dc2626' : ev.impact > 0 ? '#16a34a' : '#64748b' }}>
                {ev.impact > 0 ? '+' : ''}{ev.impact.toFixed(2)}
              </span>
            </div>
          ))}
        </div>
      )}
    </Card>
  );
}

/* ═══════════ HYBRID PANEL ═══════════ */

function HybridPanel({ hybrid }) {
  if (!hybrid) return (
    <Card testId="hybrid-panel">
      <SL><InfoTip content={<>
        <TipTitle>BTC ↔ SPX Hybrid</TipTitle>
        <TipDesc>Cross-market correlation model. Modifies amplitude only.</TipDesc>
        <TipVal label="Beta">BTC sensitivity to SPX</TipVal>
        <TipVal label="Corr">Current correlation</TipVal>
        <TipVal label="Spillover">Cross-market spillover effect</TipVal>
      </>}>BTC ↔ SPX Hybrid</InfoTip></SL>
      <div className="rounded-lg px-3 py-5 text-center mt-2" style={{ background: '#f8fafc' }}>
        <Layers className="w-5 h-5 mx-auto mb-1.5" style={{ color: '#cbd5e1' }} />
        <p className="text-hint">No live SPX data available</p>
      </div>
    </Card>
  );

  const sc = hybrid.hybridScore;
  const hc = sc > 0.25 ? '#16a34a' : sc < -0.25 ? '#dc2626' : '#64748b';
  return (
    <Card testId="hybrid-panel">
      <SL><InfoTip content={<>
        <TipTitle>BTC ↔ SPX Hybrid</TipTitle>
        <TipDesc>Cross-market correlation model. Modifies amplitude only.</TipDesc>
        <TipVal label="Beta">BTC sensitivity to SPX</TipVal>
        <TipVal label="Corr">Current correlation</TipVal>
        <TipVal label="Spillover">Cross-market spillover effect</TipVal>
      </>}>BTC ↔ SPX Hybrid</InfoTip></SL>
      <div className="grid grid-cols-4 gap-3 mt-3 mb-3">
        {[
          { l: 'Beta', v: hybrid.beta.toFixed(2) },
          { l: 'Corr', v: hybrid.correlation.toFixed(3) },
          { l: 'Spillover', v: hybrid.spillover.toFixed(3) },
          { l: 'Impact', v: (sc > 0 ? '+' : '') + sc.toFixed(2), c: hc },
        ].map(k => (
          <div key={k.l} className="text-center">
            <div className="text-hint mb-0.5">{k.l}</div>
            <div className="font-bold tabular-nums" style={{ color: k.c || '#0f172a', fontSize: 16 }}>{k.v}</div>
          </div>
        ))}
      </div>
      <div className="rounded-lg px-3 py-1.5 text-hint font-semibold text-center" style={{ background: `${hc}08`, color: hc }}>{hybrid.interpretation}</div>
      <div className="text-center mt-1.5 italic" style={{ color: '#cbd5e1', fontSize: 11 }}>Modifies amplitude only</div>
    </Card>
  );
}

/* ═══════════ ALT OUTLOOK ═══════════ */

function AltOutlookPanel({ alt }) {
  if (!alt) return null;
  const ac = ALT_C[alt.status] || ALT_C.ALT_NEUTRAL;
  return (
    <Card testId="alt-outlook">
      <SL><InfoTip content={<>
        <TipTitle>Altcoin Outlook</TipTitle>
        <TipDesc>Aggregate alt market assessment. Drives alt allocation.</TipDesc>
        <TipVal label="ALT_BULLISH" color="#16a34a">Rotation into alts</TipVal>
        <TipVal label="ALT_BEARISH" color="#dc2626">Flight to BTC / stables</TipVal>
      </>}>Altcoin Outlook</InfoTip></SL>
      <div className="flex items-center justify-between mt-2 mb-3">
        <div className="flex items-center gap-2">
          <span className="text-badge font-bold" style={{ color: ac }}>
            {alt.status.replace(/_/g, ' ')}
          </span>
          {alt.phase && alt.phase !== 'NEUTRAL' && (
            <span className="text-badge font-bold" style={{
              color: alt.phase === 'ACCELERATION' ? '#16a34a' : '#dc2626',
            }}>{alt.phase}</span>
          )}
          <span className="text-hint tabular-nums">Rotation {(alt.rotationProb * 100).toFixed(0)}%</span>
        </div>
        <span className="text-value-sm tabular-nums" style={{ color: ac }}>
          {alt.score > 0 ? '+' : ''}{alt.score.toFixed(2)}
        </span>
      </div>
      {/* Score bar */}
      <div className="h-1.5 w-full rounded-full overflow-hidden relative" style={{ background: '#e2e8f0' }}>
        {(() => {
          const pct = Math.min(Math.abs(alt.score) * 100, 100);
          const isPos = alt.score >= 0;
          return <div className="absolute top-0 h-full rounded-full transition-all duration-500"
            style={{ width: `${pct / 2}%`, left: isPos ? '50%' : `${50 - pct / 2}%`, background: isPos ? '#16a34a' : '#dc2626' }} />;
        })()}
        <div className="absolute top-0 left-1/2 w-px h-full" style={{ background: '#cbd5e1' }} />
      </div>
      <div className="mt-3 grid grid-cols-2 gap-x-4 gap-y-2">
        {[
          { l: 'BTC.D shift', v: alt.raw?.btcDelta7d, unit: '%', inv: true },
          { l: 'Stable shift', v: alt.raw?.stableDelta7d, unit: '%' },
          { l: 'LMI', v: alt.raw?.lmiScore },
          { l: 'Risk-Off', v: alt.raw?.riskOff, pct: true },
        ].map(d => {
          const val = d.v || 0;
          const display = d.pct ? `${(val * 100).toFixed(0)}%` : (d.unit ? `${val > 0 ? '+' : ''}${val.toFixed(2)}${d.unit}` : val.toFixed(3));
          const c = d.inv ? (val < 0 ? '#16a34a' : val > 0 ? '#dc2626' : '#64748b') : (val > 0.01 ? '#16a34a' : val < -0.01 ? '#dc2626' : '#64748b');
          return (
            <div key={d.l} className="flex items-center justify-between">
              <span className="text-hint">{d.l}</span>
              <span className="font-semibold tabular-nums" style={{ color: c, fontSize: 13 }}>{display}</span>
            </div>
          );
        })}
      </div>
    </Card>
  );
}

/* ═══════════ SIDEBAR: Macro ═══════════ */

function MacroPanel({ macro }) {
  if (!macro) return null;
  return (
    <Card testId="macro-context">
      <SL><InfoTip content={<>
        <TipTitle>Macro Context</TipTitle>
        <TipDesc>Macro conditions. High Risk-Off triggers gate blocks.</TipDesc>
        <TipVal label="Risk-Off">Probability of risk-off. >65% = blocked</TipVal>
        <TipVal label="Macro Mult">Size multiplier (0.4–1.05)</TipVal>
        <TipVal label="F&G">Fear & Greed (0–100)</TipVal>
      </>}>Macro Context</InfoTip></SL>
      <div className="mt-3 space-y-3">
        {[
          { l: 'Regime', v: macro.regime?.replace(/_/g, ' '), bold: true },
          { l: 'Risk-Off', v: `${(macro.riskOffProb * 100).toFixed(0)}%`, c: macro.riskOffProb > 0.6 ? '#dc2626' : '#64748b' },
          { l: 'Macro Mult', v: macro.macroMult?.toFixed(2) },
          { l: 'F&G', v: macro.fearGreed, c: macro.fearGreed < 25 ? '#dc2626' : macro.fearGreed > 75 ? '#16a34a' : '#64748b' },
          { l: 'LMI', v: macro.lmi?.toFixed(2) },
        ].map(r => (
          <div key={r.l} className="flex justify-between">
            <span className="text-hint font-medium">{r.l}</span>
            <span className={`tabular-nums ${r.bold ? 'font-bold' : 'font-semibold'}`} style={{ color: r.c || '#0f172a', fontSize: 14 }}>{r.v}</span>
          </div>
        ))}
        {macro.blocked && (
          <div className="flex items-center gap-1.5">
            <Lock className="w-3 h-3" style={{ color: '#dc2626' }} />
            <span className="text-badge font-bold" style={{ color: '#dc2626' }}>ACTIONS BLOCKED</span>
          </div>
        )}
      </div>
    </Card>
  );
}

/* ═══════════ SIDEBAR: Risk ═══════════ */

function RiskPanel({ risk }) {
  if (!risk) return null;
  const tc = risk.total > 60 ? '#dc2626' : risk.total > 40 ? '#d97706' : '#16a34a';
  return (
    <Card testId="risk-split">
      <SL><InfoTip content={<>
        <TipTitle>Risk Decomposition</TipTitle>
        <TipDesc>Total risk split into components. Affects position riskFactor.</TipDesc>
        <TipVal label="Structural (60%)">Long-term: volatility, liquidity, macro</TipVal>
        <TipVal label="Tactical (40%)">Short-term: F&G, spikes, flows</TipVal>
      </>}>Risk Decomposition</InfoTip></SL>
      <div className="mt-3">
        {[{ l: 'Structural', v: risk.structural, w: '60%' }, { l: 'Tactical', v: risk.tactical, w: '40%' }].map(r => (
          <div key={r.l} className="mb-3">
            <div className="flex justify-between mb-1">
              <span className="text-hint">{r.l} <span style={{ fontSize: 11 }}>({r.w})</span></span>
              <span className="font-semibold tabular-nums" style={{ color: r.v > 60 ? '#dc2626' : '#64748b', fontSize: 14 }}>{r.v}</span>
            </div>
            <div className="h-1.5 rounded-full overflow-hidden" style={{ background: '#e2e8f0' }}>
              <div className="h-full rounded-full transition-all duration-500" style={{ width: `${r.v}%`, background: r.v > 60 ? '#dc2626' : r.v > 40 ? '#d97706' : '#16a34a' }} />
            </div>
          </div>
        ))}
        <div className="pt-3" style={{ borderTop: '1px solid #f1f5f9' }}>
          <div className="flex justify-between">
            <span className="font-semibold" style={{ color: '#475569', fontSize: 14 }}>Total</span>
            <span className="font-bold tabular-nums" style={{ color: tc, fontSize: 18 }}>{risk.total.toFixed(0)}</span>
          </div>
          <div className="h-2 rounded-full overflow-hidden mt-1.5" style={{ background: '#e2e8f0' }}>
            <div className="h-full rounded-full transition-all duration-500" style={{ width: `${risk.total}%`, background: tc }} />
          </div>
        </div>
      </div>
    </Card>
  );
}

/* ═══════════ ALT ROTATION PANEL ═══════════ */

const ACTION_COLOR = { BUY: '#16a34a', SELL: '#dc2626', HOLD: '#d97706' };
const SECTOR_COLOR = { L1: '#6366f1', L2: '#8b5cf6', DeFi: '#059669', AI: '#0ea5e9', INFRA: '#d97706', MEME: '#f43f5e' };

function AltRotationPanel({ altData }) {
  const [expanded, setExpanded] = useState(false);
  if (!altData || !altData.ok) return null;

  const displayAlts = expanded ? altData.alts : altData.alts?.slice(0, 10);

  return (
    <div className="overflow-hidden p-5" data-testid="alt-rotation-panel" style={{ background: '#fff' }}>
      <div className="flex items-center justify-between mb-3">
        <SL><InfoTip content={<>
          <TipTitle>Alt Rotation</TipTitle>
          <TipDesc>Ranked altcoins by composite score. Updates every 5 min.</TipDesc>
          <TipVal label="Mom">Trend momentum</TipVal>
          <TipVal label="Vol">Trading volume activity</TipVal>
          <TipVal label="Flow">Capital inflow / outflow</TipVal>
        </>}>Alt Rotation</InfoTip></SL>
        <div className="flex items-center gap-4">
          <InfoTip content={<>
            <TipTitle>Rotation Index</TipTitle>
            <TipDesc>Avg score of top-5 alts. Strength of alt rotation.</TipDesc>
          </>}>
            <div className="flex items-center gap-1.5">
              <span className="text-hint">Index</span>
              <span className="font-semibold tabular-nums" data-testid="rotation-index" style={{ color: '#0f172a', fontSize: 14 }}>
                {(altData.rotationIndex * 100).toFixed(0)}
              </span>
            </div>
          </InfoTip>
          <div className="flex items-center gap-2 text-xs tabular-nums" style={{ color: '#64748b' }}>
            <span><span className="font-semibold" style={{ color: '#16a34a' }}>{altData.meta?.buyCount}</span> buy</span>
            <span><span className="font-semibold" style={{ color: '#64748b' }}>{altData.meta?.holdCount}</span> hold</span>
            <span><span className="font-semibold" style={{ color: '#dc2626' }}>{altData.meta?.sellCount}</span> sell</span>
          </div>
        </div>
      </div>

      {/* Sector Strength */}
      <div className="flex flex-wrap gap-2 mb-3" data-testid="sector-strength">
        {Object.entries(altData.sectorStrength || {}).map(([sector, score]) => (
          <div key={sector} className="flex items-center gap-1.5">
            <span className="text-xs font-semibold" style={{ color: '#0f172a' }}>{sector}</span>
            <span className="text-xs font-bold tabular-nums" style={{ color: score > 0.1 ? '#16a34a' : score < -0.1 ? '#dc2626' : '#64748b' }}>
              {(score * 100).toFixed(0)}
            </span>
          </div>
        ))}
      </div>

      {/* Table */}
      <div className="overflow-x-auto">
        <table className="w-full text-sm" data-testid="alt-rotation-table">
          <thead>
            <tr className="text-hint text-left" style={{ borderBottom: '1px solid #f1f5f9' }}>
              <th className="py-1.5 font-medium w-8">#</th>
              <th className="py-1.5 font-medium">Asset</th>
              <th className="py-1.5 font-medium text-center">Sector</th>
              <th className="py-1.5 font-medium text-right">Mom</th>
              <th className="py-1.5 font-medium text-right">Vol</th>
              <th className="py-1.5 font-medium text-right">Flow</th>
              <th className="py-1.5 font-medium text-center">Action</th>
            </tr>
          </thead>
          <tbody>
            {displayAlts?.map(alt => (
              <tr key={alt.symbol} className="transition-colors hover:bg-slate-50" style={{ borderBottom: '1px solid #f8fafc' }}
                data-testid={`alt-row-${alt.symbol}`}>
                <td className="py-2 text-xs text-slate-400 tabular-nums">{alt.rank}</td>
                <td className="py-2">
                  <span className="font-semibold text-slate-900">{alt.symbol}</span>
                  <span className="text-xs text-slate-400 ml-1 hidden sm:inline">{alt.name}</span>
                </td>
                <td className="py-2 text-center">
                  <span className="text-xs font-medium" style={{ color: SECTOR_COLOR[alt.sector] || '#64748b' }}>
                    {alt.sector}
                  </span>
                </td>
                <td className="py-2 text-right tabular-nums font-medium" style={{ color: alt.momentum > 0 ? '#16a34a' : alt.momentum < 0 ? '#dc2626' : '#64748b', fontSize: 13 }}>
                  {alt.momentum > 0 ? '+' : ''}{(alt.momentum * 100).toFixed(0)}
                </td>
                <td className="py-2 text-right tabular-nums font-medium" style={{ color: '#6366f1', fontSize: 13 }}>
                  {(alt.volume * 100).toFixed(0)}
                </td>
                <td className="py-2 text-right tabular-nums font-medium" style={{ color: alt.flow > 0 ? '#16a34a' : alt.flow < 0 ? '#dc2626' : '#64748b', fontSize: 13 }}>
                  {alt.flow > 0 ? '+' : ''}{(alt.flow * 100).toFixed(0)}
                </td>
                <td className="py-2 text-center">
                  <span className="text-xs font-bold" style={{
                    color: ACTION_COLOR[alt.action],
                  }}>{alt.action}</span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {altData.alts?.length > 10 && (
        <button onClick={() => setExpanded(!expanded)} data-testid="alt-rotation-expand"
          className="w-full text-center text-xs font-medium py-2 mt-1 rounded-lg transition-colors text-indigo-600 hover:bg-indigo-50">
          {expanded ? 'Show less' : `Show all ${altData.alts.length} alts`}
        </button>
      )}
    </div>
  );
}

/* ═══════════ SIDEBAR: Alerts ═══════════ */

function AlertsPanel({ alerts }) {
  if (!alerts) return null;
  return (
    <Card testId="alerts-panel">
      <SL>Alerts</SL>
      <div className="mt-3 flex gap-5 mb-3">
        <div>
          <div className="text-value-md tabular-nums" style={{ color: alerts.active > 0 ? '#d97706' : '#94a3b8' }}>{alerts.active}</div>
          <div className="text-hint">Active</div>
        </div>
        <div>
          <div className="text-value-md tabular-nums" style={{ color: alerts.highPriority > 0 ? '#dc2626' : '#94a3b8' }}>{alerts.highPriority}</div>
          <div className="text-hint">High</div>
        </div>
      </div>
      {alerts.triggers?.length > 0 && (
        <div>
          <div className="text-hint uppercase font-semibold tracking-wide mb-2">Watch Triggers</div>
          {alerts.triggers.map((t, i) => (
            <div key={i} className="flex items-center gap-1.5 mb-1.5" style={{ color: '#475569', fontSize: 13 }}>
              <Target className="w-3.5 h-3.5 flex-shrink-0" style={{ color: '#6366f1' }} /> {t}
            </div>
          ))}
        </div>
      )}
    </Card>
  );
}

/* ═══════════ MAIN PAGE ═══════════ */

export default function OverviewV2Page() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [refreshing, setRefreshing] = useState(false);
  const [wsConnected, setWsConnected] = useState(false);
  const [wsChanged, setWsChanged] = useState(null);
  const [labsOpen, setLabsOpen] = useState(false);
  const [altRotation, setAltRotation] = useState(null);
  const [tactical, setTactical] = useState(null);

  const fetchAltRotation = useCallback(async () => {
    try {
      const res = await fetch(`${API}/api/overview/alt-rotation?asset=BTCUSDT&tf=1h`);
      const json = await res.json();
      if (json.ok) setAltRotation(json);
    } catch {}
  }, []);

  const fetchTactical = useCallback(async () => {
    try {
      const res = await fetch(`${API}/api/tactical/1d?asset=BTC`);
      const json = await res.json();
      if (json.ok) setTactical(json);
    } catch {}
  }, []);

  const fetchData = useCallback(async (isRefresh = false) => {
    if (isRefresh) setRefreshing(true); else setLoading(true);
    try {
      const res = await fetch(`${API}/api/overview?asset=BTCUSDT&tf=1h`);
      const json = await res.json();
      if (json.ok) { setData(json); setError(null); }
      else setError('Failed to load');
    } catch (e) { setError(e.message); }
    finally { setLoading(false); setRefreshing(false); }
  }, []);

  useEffect(() => {
    let ws = null;
    let reconnectTimer = null;
    let fallbackTimer = null;

    const connect = () => {
      const wsUrl = API.replace('https://', 'wss://').replace('http://', 'ws://');
      try {
        ws = new WebSocket(`${wsUrl}/api/overview/ws`);
        ws.onopen = () => {
          setWsConnected(true);
          ws.send(JSON.stringify({ asset: 'BTCUSDT', tf: '1h' }));
          if (fallbackTimer) { clearInterval(fallbackTimer); fallbackTimer = null; }
        };
        ws.onmessage = (ev) => {
          try {
            const json = JSON.parse(ev.data);
            if (json.ok) {
              setData(json);
              setError(null);
              setLoading(false);
              if (json._ws?.changed) {
                setWsChanged({ action: json.decision?.action, regime: json.macro?.regime, ts: Date.now() });
                setTimeout(() => setWsChanged(null), 5000);
              }
            }
          } catch {}
        };
        ws.onclose = () => {
          setWsConnected(false);
          if (!fallbackTimer) fallbackTimer = setInterval(() => fetchData(true), 60000);
          reconnectTimer = setTimeout(connect, 10000);
        };
        ws.onerror = () => ws.close();
      } catch {
        setWsConnected(false);
        if (!fallbackTimer) fallbackTimer = setInterval(() => fetchData(true), 60000);
        reconnectTimer = setTimeout(connect, 10000);
      }
    };

    fetchData();
    fetchAltRotation();
    fetchTactical();
    connect();

    return () => {
      if (ws) ws.close();
      if (reconnectTimer) clearTimeout(reconnectTimer);
      if (fallbackTimer) clearInterval(fallbackTimer);
    };
  }, [fetchData, fetchAltRotation, fetchTactical]);

  if (loading && !data) return <div className="flex items-center justify-center h-64"><Loader2 className="w-6 h-6 animate-spin" style={{ color: '#94a3b8' }} /></div>;
  if (error && !data) return <div className="flex items-center justify-center h-64"><div className="text-center"><AlertTriangle className="w-8 h-8 mx-auto mb-2" style={{ color: '#dc2626' }} /><p className="text-body" style={{ color: '#64748b' }}>{error}</p></div></div>;

  const { decision, core, signals, macro, risk, hybrid, altOutlook, alerts, positionHistory } = data || {};

  return (
    <div data-testid="overview-v2-page">
      <div className="flex items-center justify-end gap-3 px-6 pt-3 pb-1">
        <div className="flex items-center gap-1.5" data-testid="ws-status">
          <div className="w-1.5 h-1.5 rounded-full" style={{ background: wsConnected ? '#16a34a' : '#94a3b8' }} />
          <span className="text-hint">{wsConnected ? 'Live' : 'Polling'}</span>
        </div>
        {wsChanged && (
          <div className="flex items-center gap-1.5 animate-pulse"
            data-testid="ws-change-alert"
            style={{ color: '#6366f1' }}>
            <Zap className="w-3 h-3" /> Regime changed
          </div>
        )}
        <button onClick={() => setLabsOpen(true)} data-testid="labs-btn"
          className="flex items-center gap-1.5 transition-colors text-xs font-medium"
          style={{ color: '#6366f1' }}
          onMouseEnter={e => e.currentTarget.style.opacity = '0.7'}
          onMouseLeave={e => e.currentTarget.style.opacity = '1'}>
          <FlaskConical className="w-3 h-3" /> LABS
        </button>
        <button onClick={() => fetchData(true)} disabled={refreshing} data-testid="overview-refresh-btn"
          className="p-1.5 rounded-lg transition-colors disabled:opacity-30"
          style={{ background: refreshing ? '#f1f5f9' : 'transparent' }}
          onMouseEnter={e => e.currentTarget.style.background = '#f1f5f9'}
          onMouseLeave={e => { if (!refreshing) e.currentTarget.style.background = 'transparent'; }}>
          <RefreshCw className={`w-4 h-4 ${refreshing ? 'animate-spin' : ''}`} style={{ color: '#94a3b8' }} />
        </button>
      </div>

      <div className="px-6 pb-6 grid grid-cols-1 lg:grid-cols-[1fr_280px] gap-5">
        <div className="space-y-5">
          <FadeIn delay={0}>
            <DecisionConsole decision={decision} positionHistory={positionHistory} />
          </FadeIn>
          <FadeIn delay={80}>
            <DecisionTrace trace={decision?.trace} />
          </FadeIn>
          <FadeIn delay={110}>
            <TacticalPanel data={tactical} />
          </FadeIn>
          <FadeIn delay={140}>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <CoreSnapshotPanel core={core} />
              <SignalsSummaryPanel signals={signals} />
            </div>
          </FadeIn>
          <FadeIn delay={200}>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <HybridPanel hybrid={hybrid} />
              <AltOutlookPanel alt={altOutlook} />
            </div>
          </FadeIn>
          <FadeIn delay={230}>
            <AltRotationPanel altData={altRotation} />
          </FadeIn>
          <FadeIn delay={260}>
            <Suspense fallback={null}>
              <PositionHistoryPanel />
            </Suspense>
          </FadeIn>
        </div>

        <div className="space-y-5">
          <FadeIn delay={40}><MacroPanel macro={macro} /></FadeIn>
          <FadeIn delay={120}><RiskPanel risk={risk} /></FadeIn>
          <FadeIn delay={200}><AlertsPanel alerts={alerts} /></FadeIn>
        </div>
      </div>

      <Suspense fallback={null}>
        <LabsDrawer isOpen={labsOpen} onClose={() => setLabsOpen(false)} />
      </Suspense>
    </div>
  );
}
