/**
 * Market Brain Engine — Phase 13: Engine Integration (Platform Style)
 * Uses IntelligenceBlock pattern from CEX Flow / Token Intelligence
 */
import { useState, useEffect, useCallback } from 'react';
import {
  Brain, TrendingUp, TrendingDown, Activity, Shield, Zap,
  Eye, Target, BarChart3, Layers, Clock, Radio, ChevronRight,
  AlertTriangle, CheckCircle2, XCircle, Minus, RefreshCw,
  Package, ArrowLeftRight, Gauge
} from 'lucide-react';
import { IntelligenceBlock } from '../components/intelligence';

const API = process.env.REACT_APP_BACKEND_URL;

const DECISION_CONFIG = {
  BUY: { color: 'text-emerald-400', label: 'BUY', icon: TrendingUp },
  SELL: { color: 'text-red-400', label: 'SELL', icon: TrendingDown },
  NEUTRAL: { color: 'text-amber-400', label: 'NEUTRAL', icon: Minus },
};

const CONF_COLORS = { HIGH: 'text-emerald-400', MODERATE: 'text-amber-400', LOW: 'text-orange-400', INSUFFICIENT: 'text-red-400' };

const PHASE_CONFIG = {
  detected: { text: 'text-blue-600', bg: 'bg-blue-50', label: 'Detected' },
  confirmed: { text: 'text-emerald-600', bg: 'bg-emerald-50', label: 'Confirmed' },
  expansion: { text: 'text-amber-600', bg: 'bg-amber-50', label: 'Expansion' },
  exhaustion: { text: 'text-red-600', bg: 'bg-red-50', label: 'Exhaustion' },
};

const SRC_COLORS = { entities: 'text-violet-500', smart_money: 'text-emerald-500', cex: 'text-cyan-500', token: 'text-amber-500' };
const MOD_LABELS = { entities: 'Entities', smart_money: 'Smart Money', cex: 'CEX Flow', token: 'Token Intel' };
const MOD_ICONS = { entities: Layers, smart_money: Eye, cex: BarChart3, token: Zap };

function Skeleton({ dark }) {
  return (
    <IntelligenceBlock dark={dark}>
      <div className="flex items-center justify-center py-10">
        <div className={`animate-spin w-5 h-5 border-2 ${dark ? 'border-violet-400' : 'border-gray-400'} border-t-transparent rounded-full`} />
      </div>
    </IntelligenceBlock>
  );
}

// ═══════════════════════════════════════════
// HERO: DECISION TERMINAL (dark)
// ═══════════════════════════════════════════
function DecisionHero({ data }) {
  const decision = data?.decision || 'NEUTRAL';
  const conf = data?.confidence || {};
  const setup = data?.setup || {};
  const win = data?.window || '—';
  const scores = data?.scores || {};
  const hero = data?.hero_summary || {};
  const prob = data?.probability_layer || {};
  const regimeEng = data?.regime_engine?.primary || {};
  const setupEng = data?.setup_engine?.primary || {};
  const dc = DECISION_CONFIG[decision] || DECISION_CONFIG.NEUTRAL;
  const DecIcon = dc.icon;

  const REGIME_LABELS = { bull_trend: 'Bull Trend', bear_trend: 'Bear Trend', accumulation: 'Accumulation', distribution: 'Distribution', rotation: 'Rotation', neutral_chop: 'Neutral Chop' };
  const REGIME_COLORS = { bull_trend: 'text-emerald-400', bear_trend: 'text-red-400', accumulation: 'text-cyan-400', distribution: 'text-orange-400', rotation: 'text-violet-400', neutral_chop: 'text-gray-400' };
  const STATUS_COLORS = { confirmed: 'text-emerald-400', active: 'text-cyan-400', forming: 'text-amber-400', weakening: 'text-orange-400', weak: 'text-gray-500' };

  return (
    <IntelligenceBlock dark testId="decision-terminal">
      <div className="text-[10px] font-bold text-gray-500 uppercase tracking-[0.2em] mb-3">Decision Terminal</div>
      <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-6">
        <div className="flex items-center gap-6">
          <div className="text-center">
            <DecIcon className={`w-8 h-8 ${dc.color} mx-auto mb-1`} />
            <div className={`text-2xl font-black ${dc.color}`} data-testid="decision-badge">{decision}</div>
            <div className="text-[9px] text-gray-500 mt-1">DECISION</div>
          </div>
          <div className="text-center">
            <div className={`text-3xl font-black tabular-nums ${CONF_COLORS[conf.level] || 'text-gray-400'}`} data-testid="confidence-display">{conf.score || 0}</div>
            <div className="text-[9px] text-gray-500 mt-0.5">CONFIDENCE</div>
            <div className={`text-[9px] ${CONF_COLORS[conf.level] || 'text-gray-500'}`}>{conf.level || '—'}</div>
          </div>
          <div className="text-center">
            <div className={`text-sm font-bold ${REGIME_COLORS[regimeEng.type] || 'text-gray-400'}`} data-testid="regime-display">{REGIME_LABELS[regimeEng.type] || regimeEng.type || '—'}</div>
            <div className="text-[9px] text-gray-500">REGIME</div>
            <div className={`text-[9px] ${STATUS_COLORS[regimeEng.status] || 'text-gray-500'}`}>{regimeEng.status || '—'}</div>
          </div>
          <div className="text-center">
            <div className="text-sm font-bold text-white" data-testid="setup-display">{setupEng.type ? setupEng.type.replace(/_/g, ' ') : setup.type || '—'}</div>
            <div className="text-[9px] text-gray-500">SETUP</div>
            <div className={`text-[9px] ${STATUS_COLORS[setupEng.status] || 'text-gray-500'}`}>{setupEng.status || '—'} · {setupEng.window || win}</div>
          </div>
          <div className="text-center">
            <div className={`text-4xl font-black tabular-nums ${scores.composite >= 60 ? 'text-emerald-400' : scores.composite <= 40 ? 'text-red-400' : 'text-amber-400'}`} data-testid="composite-score">
              {scores.composite || 50}
            </div>
            <div className="text-[9px] text-gray-500 uppercase tracking-wider mt-1">Composite</div>
          </div>
        </div>
        {/* Probability strip */}
        <div className="flex items-center gap-4" data-testid="probability-strip">
          {[
            { label: 'Continue', value: prob.continuation, color: 'text-emerald-400' },
            { label: 'Failure', value: prob.failure, color: 'text-red-400' },
            { label: 'Upgrade', value: prob.upgrade, color: 'text-cyan-400' },
          ].map(({ label, value, color }) => (
            <div key={label} className="text-center">
              <div className={`text-lg font-black tabular-nums ${color}`}>{value != null ? `${Math.round(value * 100)}%` : '—'}</div>
              <div className="text-[9px] text-gray-500">{label}</div>
            </div>
          ))}
        </div>
      </div>

      {/* Hero summary lines */}
      {hero.reason && (
        <div className="mt-3 pt-3 border-t border-gray-800 space-y-1.5" data-testid="hero-summary">
          <div className="text-[11px] text-gray-300 italic">{hero.reason}</div>
          {hero.primary_blocker && (
            <div className="text-[10px] text-orange-400 flex items-start gap-1.5">
              <AlertTriangle className="w-3 h-3 mt-0.5 shrink-0" />
              <span>Primary blocker: {hero.primary_blocker}</span>
            </div>
          )}
          {hero.primary_trigger && (
            <div className="text-[10px] text-cyan-400 flex items-start gap-1.5">
              <Zap className="w-3 h-3 mt-0.5 shrink-0" />
              <span>Upgrade trigger: {hero.primary_trigger}</span>
            </div>
          )}
        </div>
      )}

      {/* Score bars */}
      <div className="grid grid-cols-4 gap-4 mt-4 pt-3 border-t border-gray-800">
        {[
          { key: 'smart_money_score', label: 'Smart Money', color: 'bg-emerald-400' },
          { key: 'cex_score', label: 'CEX Flow', color: 'bg-cyan-400' },
          { key: 'entities_score', label: 'Entities', color: 'bg-violet-400' },
          { key: 'token_score', label: 'Token', color: 'bg-amber-400' },
        ].map(({ key, label, color }) => {
          const val = scores[key] || 50;
          return (
            <div key={key} data-testid={`score-${key}`}>
              <div className="flex items-center justify-between mb-0.5">
                <span className="text-[9px] font-bold text-gray-500 uppercase tracking-wider">{label}</span>
                <span className="text-[10px] font-black text-gray-300 tabular-nums">{val}</span>
              </div>
              <div className="h-1 bg-gray-800 rounded-full overflow-hidden">
                <div className={`h-full rounded-full ${color}`} style={{ width: `${val}%` }} />
              </div>
            </div>
          );
        })}
      </div>
    </IntelligenceBlock>
  );
}

// ═══════════════════════════════════════════
// ZONE 2: DECISION EXPLANATION (light) — E1
// ═══════════════════════════════════════════
const EXPLANATION_SECTIONS = [
  { key: 'bullish_drivers', label: 'Supports', icon: TrendingUp, color: 'text-emerald-600', dot: 'bg-emerald-400' },
  { key: 'bearish_or_contradictions', label: 'Contradictions', icon: AlertTriangle, color: 'text-red-500', dot: 'bg-red-400' },
  { key: 'decision_blockers', label: 'Decision Blockers', icon: XCircle, color: 'text-orange-500', dot: 'bg-orange-400' },
  { key: 'upgrade_triggers', label: 'Upgrade Triggers', icon: Zap, color: 'text-cyan-600', dot: 'bg-cyan-400' },
];

function ExplanationBlock({ explanation }) {
  return (
    <IntelligenceBlock testId="decision-explanation">
      <div className="flex items-center gap-2 mb-4">
        <Brain className="w-4 h-4 text-gray-400" />
        <h3 className="text-xs font-bold text-gray-400 uppercase tracking-[0.15em]">Decision Explanation</h3>
      </div>
      <div className="grid grid-cols-2 gap-5">
        {EXPLANATION_SECTIONS.map(({ key, label, icon: SIcon, color, dot }) => {
          const items = explanation?.[key] || [];
          return (
            <div key={key} data-testid={`explanation-${key}`}>
              <div className="flex items-center gap-2 mb-2">
                <SIcon className={`w-3.5 h-3.5 ${color}`} />
                <span className={`text-xs font-bold ${color}`}>{label}</span>
                <span className="text-[9px] text-gray-400 ml-auto">{items.length}</span>
              </div>
              {items.length > 0 ? (
                <div className="space-y-1.5">
                  {items.map((item, i) => (
                    <div key={i} className="flex items-start gap-2 text-[11px] text-gray-600">
                      <div className={`w-1.5 h-1.5 rounded-full ${dot} mt-1.5 shrink-0`} />
                      {item}
                    </div>
                  ))}
                </div>
              ) : (
                <div className="text-[11px] text-gray-400 italic">None</div>
              )}
            </div>
          );
        })}
      </div>
    </IntelligenceBlock>
  );
}

// ═══════════════════════════════════════════
// GATES (dark)
// ═══════════════════════════════════════════
function GatesBlock({ gates, risks }) {
  const gateList = [
    { key: 'evidence', label: 'Evidence', icon: CheckCircle2 },
    { key: 'risk', label: 'Risk', icon: AlertTriangle },
    { key: 'coverage', label: 'Coverage', icon: Shield },
  ];
  const statusColor = (s) => {
    if (s === 'PASS' || s === 'FULL' || s === 'LOW') return 'text-emerald-400';
    if (s === 'WEAK' || s === 'PARTIAL' || s === 'MEDIUM') return 'text-amber-400';
    return 'text-red-400';
  };

  return (
    <IntelligenceBlock dark testId="gates-panel">
      <div className="flex items-center gap-2 mb-3">
        <Shield className="w-4 h-4 text-gray-400" />
        <h3 className="text-xs font-bold text-gray-400 uppercase tracking-[0.15em]">Engine Gates</h3>
      </div>
      <div className="space-y-3">
        {gateList.map(({ key, label, icon: GIcon }) => {
          const g = gates?.[key] || {};
          return (
            <div key={key} className="py-2 border-b border-gray-800 last:border-0" data-testid={`gate-${key}`}>
              <div className="flex items-center justify-between mb-1">
                <div className="flex items-center gap-1.5">
                  <GIcon className={`w-3 h-3 ${statusColor(g.status)}`} />
                  <span className="text-[11px] text-gray-400 font-bold">{label}</span>
                </div>
                <span className={`text-[10px] font-black ${statusColor(g.status)}`}>{g.status || '—'}</span>
              </div>
              {key === 'evidence' && g.verdicts && (
                <div className="flex gap-2 mt-1">
                  {Object.entries(g.verdicts).map(([mod, verdict]) => (
                    <span key={mod} className={`text-[9px] ${verdict === 'supports' ? 'text-emerald-500' : verdict === 'contradicts' ? 'text-red-500' : 'text-gray-600'}`}>
                      {MOD_LABELS[mod]?.slice(0, 3)}: {verdict === 'supports' ? '+' : verdict === 'contradicts' ? '−' : '~'}
                    </span>
                  ))}
                </div>
              )}
              {key === 'risk' && g.factors?.length > 0 && <div className="mt-1 space-y-0.5">{g.factors.map((f, i) => <div key={i} className="text-[10px] text-gray-500">{f}</div>)}</div>}
              {key === 'coverage' && g.issues?.length > 0 && <div className="mt-1 space-y-0.5">{g.issues.map((iss, i) => <div key={i} className="text-[10px] text-gray-500">{iss}</div>)}</div>}
            </div>
          );
        })}
      </div>
      {risks?.length > 0 && (
        <div className="mt-3 pt-2 border-t border-gray-800">
          <div className="text-[9px] text-gray-500 uppercase tracking-wider mb-1.5">Active Risks</div>
          {risks.map((r, i) => (
            <div key={i} className="text-[10px] text-gray-400 flex items-start gap-1.5 mt-0.5">
              <AlertTriangle className="w-2.5 h-2.5 text-orange-400 mt-0.5 shrink-0" />{r}
            </div>
          ))}
        </div>
      )}
    </IntelligenceBlock>
  );
}

// ═══════════════════════════════════════════
// ZONE 3: CONTEXT MATRIX (light)
// ═══════════════════════════════════════════
function ContextBlock({ matrix, scores }) {
  const modules = [
    { key: 'entities', label: 'Entities', icon: Layers, color: 'text-violet-600',
      metrics: (ctx) => [{ l: 'Entities', v: ctx.entity_count || 0 }, { l: 'Dominant', v: ctx.dominant_behaviour || '—' }, { l: 'Volume', v: ctx.total_volume_fmt || '$0' }, { l: 'Clusters', v: ctx.cluster_wallets || 0 }] },
    { key: 'smart_money', label: 'Smart Money', icon: Eye, color: 'text-emerald-600',
      metrics: (ctx) => [{ l: 'Net Flow', v: ctx.net_flow_fmt || '$0' }, { l: 'Conviction', v: `${ctx.conviction || 0}%` }, { l: 'Clusters', v: ctx.clusters || 0 }, { l: 'Signals', v: ctx.signal_count || 0 }] },
    { key: 'cex', label: 'CEX Flow', icon: BarChart3, color: 'text-cyan-600',
      metrics: (ctx) => [{ l: 'Bias', v: ctx.market_bias || '—' }, { l: 'Shock', v: (ctx.liquidity_shock || '—').replace(/_/g, ' ') }, { l: 'Inventory', v: ctx.inventory_state || '—' }, { l: 'Stablecoin', v: ctx.stablecoin_bias || '—' }] },
    { key: 'token', label: 'Token Intel', icon: Zap, color: 'text-amber-600',
      metrics: (ctx) => [{ l: 'Regime', v: ctx.regime || '—' }, { l: 'Pattern', v: (ctx.pattern || '—').replace(/_/g, ' ') }, { l: 'Confidence', v: `${ctx.confidence || 0}%` }, { l: 'Tokens', v: ctx.token_count || 0 }] },
  ];

  return (
    <IntelligenceBlock testId="context-matrix">
      <div className="flex items-center gap-2 mb-4">
        <Shield className="w-4 h-4 text-gray-400" />
        <h3 className="text-xs font-bold text-gray-400 uppercase tracking-[0.15em]">Context Matrix</h3>
      </div>
      <div className="grid grid-cols-2 gap-4">
        {modules.map(({ key, label, icon: MIcon, color, metrics }) => {
          const ctx = matrix?.[key] || {};
          const score = scores?.[`${key}_score`] || 50;
          return (
            <div key={key} className="p-3 rounded-xl bg-gray-50" data-testid={`context-${key}`}>
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-2">
                  <MIcon className={`w-3.5 h-3.5 ${color}`} />
                  <span className={`text-xs font-bold ${color}`}>{label}</span>
                </div>
                <span className={`text-sm font-black tabular-nums ${score >= 60 ? color : score <= 40 ? 'text-red-600' : 'text-gray-500'}`}>{score}</span>
              </div>
              <div className="space-y-1">
                {metrics(ctx).map((m, i) => (
                  <div key={i} className="flex items-center justify-between text-[11px]">
                    <span className="text-gray-400">{m.l}</span>
                    <span className="text-gray-700 font-medium">{m.v}</span>
                  </div>
                ))}
              </div>
            </div>
          );
        })}
      </div>
    </IntelligenceBlock>
  );
}

// ═══════════════════════════════════════════
// ZONE 4: SIGNAL FEED (light)
// ═══════════════════════════════════════════
const IMPACT_CONFIG = {
  bullish_driver: { text: 'text-emerald-600', bg: 'bg-emerald-50', label: 'Bullish' },
  contradiction: { text: 'text-red-600', bg: 'bg-red-50', label: 'Contra' },
  discovery: { text: 'text-violet-600', bg: 'bg-violet-50', label: 'New' },
  neutral: { text: 'text-gray-500', bg: 'bg-gray-50', label: '' },
};

function SignalsBlock({ signals }) {
  const phases = ['detected', 'confirmed', 'expansion', 'exhaustion'];
  const grouped = {};
  phases.forEach(p => { grouped[p] = []; });
  (signals || []).forEach(s => { const p = s.phase || 'detected'; if (grouped[p]) grouped[p].push(s); });

  return (
    <IntelligenceBlock testId="signal-feed">
      <div className="flex items-center gap-2 mb-4">
        <Radio className="w-4 h-4 text-gray-400" />
        <h3 className="text-xs font-bold text-gray-400 uppercase tracking-[0.15em]">Signal Feed</h3>
      </div>
      <div className="flex gap-2 mb-4">
        {phases.map(p => {
          const count = grouped[p]?.length || 0;
          const pc = PHASE_CONFIG[p];
          return (
            <div key={p} className={`flex-1 text-center p-2 rounded-xl ${pc.bg}`} data-testid={`phase-${p}`}>
              <div className={`text-lg font-black ${pc.text}`}>{count}</div>
              <div className={`text-[9px] font-bold ${pc.text}`}>{pc.label}</div>
            </div>
          );
        })}
      </div>
      <div className="space-y-1.5 max-h-[280px] overflow-y-auto">
        {(signals || []).map((s, i) => {
          const pc = PHASE_CONFIG[s.phase] || PHASE_CONFIG.detected;
          const srcColor = SRC_COLORS[s.source] || 'text-gray-500';
          const imp = IMPACT_CONFIG[s.impact] || IMPACT_CONFIG.neutral;
          return (
            <div key={i} className="flex items-center gap-2 py-1.5 border-b border-gray-100 last:border-0" data-testid={`signal-${i}`}>
              <span className={`text-[9px] font-bold shrink-0 ${pc.text}`}>{pc.label}</span>
              <span className={`text-[10px] font-bold shrink-0 ${srcColor}`}>{MOD_LABELS[s.source] || s.source}</span>
              <span className="text-[11px] text-gray-600 truncate flex-1">{(s.description || '').replace(/_/g, ' ')}</span>
              {imp.label && <span className={`text-[8px] font-bold px-1.5 py-0.5 rounded ${imp.bg} ${imp.text} shrink-0`}>{imp.label}</span>}
              <span className="text-[10px] text-gray-400 tabular-nums shrink-0">{s.confidence ? `${(s.confidence * 100).toFixed(0)}%` : ''}</span>
            </div>
          );
        })}
      </div>
    </IntelligenceBlock>
  );
}

// ═══════════════════════════════════════════
// ZONE: REGIME + SETUP STRUCTURE (light)
// ═══════════════════════════════════════════
const REGIME_LABELS = { bull_trend: 'Bull Trend', bear_trend: 'Bear Trend', accumulation: 'Accumulation', distribution: 'Distribution', rotation: 'Rotation', neutral_chop: 'Neutral Chop' };
const REGIME_COLORS_FG = { bull_trend: 'text-emerald-600', bear_trend: 'text-red-600', accumulation: 'text-cyan-600', distribution: 'text-orange-600', rotation: 'text-violet-600', neutral_chop: 'text-gray-500' };
const SETUP_LABELS = { liquidity_shock: 'Liquidity Shock', smart_money_accumulation: 'SM Accumulation', distribution_risk: 'Distribution Risk', exchange_drain: 'Exchange Drain', rotation: 'Rotation', actor_conflict: 'Actor Conflict', otc_transfer: 'OTC Transfer', mixed: 'Mixed / Unclear' };
const STATUS_DOT = { confirmed: 'bg-emerald-400', active: 'bg-cyan-400', forming: 'bg-amber-400', weakening: 'bg-orange-400', weak: 'bg-gray-400' };

function RegimeBlock({ regime }) {
  const primary = regime?.primary || {};
  const secondary = regime?.secondary || [];
  const rgColor = REGIME_COLORS_FG[primary.type] || 'text-gray-500';
  return (
    <IntelligenceBlock testId="regime-engine">
      <div className="flex items-center gap-2 mb-3">
        <Layers className="w-4 h-4 text-gray-400" />
        <h3 className="text-xs font-bold text-gray-400 uppercase tracking-[0.15em]">Market Regime</h3>
      </div>
      <div className="flex items-center gap-3 mb-3">
        <div className={`w-2.5 h-2.5 rounded-full ${STATUS_DOT[primary.status] || 'bg-gray-400'}`} />
        <span className={`text-lg font-black ${rgColor}`} data-testid="regime-primary">{REGIME_LABELS[primary.type] || primary.type || '—'}</span>
        <span className="text-xs font-bold text-gray-400 tabular-nums">{primary.confidence != null ? `${Math.round(primary.confidence * 100)}%` : ''}</span>
        <span className="text-[10px] text-gray-400 capitalize">{primary.status || ''}</span>
      </div>
      {primary.drivers?.length > 0 && (
        <div className="space-y-1 mb-3">
          {primary.drivers.map((d, i) => (
            <div key={i} className="flex items-start gap-2 text-[11px] text-gray-600">
              <CheckCircle2 className="w-3 h-3 text-emerald-500 mt-0.5 shrink-0" />{d}
            </div>
          ))}
        </div>
      )}
      {primary.invalidation?.length > 0 && (
        <div className="pt-2 border-t border-gray-100 space-y-1">
          <div className="text-[9px] font-bold text-gray-400 uppercase tracking-wider mb-1">Invalidation</div>
          {primary.invalidation.map((iv, i) => (
            <div key={i} className="flex items-start gap-2 text-[10px] text-red-500">
              <XCircle className="w-3 h-3 mt-0.5 shrink-0" />{iv}
            </div>
          ))}
        </div>
      )}
      {secondary.length > 0 && (
        <div className="pt-2 border-t border-gray-100 mt-2">
          <div className="text-[9px] font-bold text-gray-400 uppercase tracking-wider mb-1">Secondary</div>
          <div className="flex gap-3">
            {secondary.map((s, i) => (
              <div key={i} className="flex items-center gap-1.5 text-[11px]">
                <div className={`w-1.5 h-1.5 rounded-full ${STATUS_DOT[s.status] || 'bg-gray-400'}`} />
                <span className={`font-bold ${REGIME_COLORS_FG[s.type] || 'text-gray-500'}`}>{REGIME_LABELS[s.type] || s.type}</span>
                <span className="text-gray-400 tabular-nums">{Math.round(s.confidence * 100)}%</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </IntelligenceBlock>
  );
}

function SetupBlock({ setupEngine }) {
  const primary = setupEngine?.primary || {};
  const secondary = setupEngine?.secondary || [];
  return (
    <IntelligenceBlock testId="setup-engine">
      <div className="flex items-center gap-2 mb-3">
        <Target className="w-4 h-4 text-gray-400" />
        <h3 className="text-xs font-bold text-gray-400 uppercase tracking-[0.15em]">Setup Structure</h3>
      </div>
      <div className="flex items-center gap-3 mb-3">
        <div className={`w-2.5 h-2.5 rounded-full ${STATUS_DOT[primary.status] || 'bg-gray-400'}`} />
        <span className="text-lg font-black text-gray-900" data-testid="setup-primary">{SETUP_LABELS[primary.type] || primary.type || '—'}</span>
        <span className="text-xs font-bold text-gray-400 tabular-nums">{primary.confidence != null ? `${Math.round(primary.confidence * 100)}%` : ''}</span>
        <span className="text-[10px] text-gray-400 capitalize">{primary.status || ''}</span>
        {primary.window && <span className="text-[10px] text-gray-400 ml-auto">{primary.window}</span>}
      </div>
      {primary.supports?.length > 0 && (
        <div className="space-y-1 mb-2">
          {primary.supports.map((s, i) => (
            <div key={i} className="flex items-start gap-2 text-[11px] text-gray-600">
              <TrendingUp className="w-3 h-3 text-emerald-500 mt-0.5 shrink-0" />{s}
            </div>
          ))}
        </div>
      )}
      {primary.contradictions?.length > 0 && (
        <div className="space-y-1 mb-2">
          {primary.contradictions.map((c, i) => (
            <div key={i} className="flex items-start gap-2 text-[11px] text-red-500">
              <AlertTriangle className="w-3 h-3 mt-0.5 shrink-0" />{c}
            </div>
          ))}
        </div>
      )}
      {primary.invalidation?.length > 0 && (
        <div className="pt-2 border-t border-gray-100 space-y-1">
          <div className="text-[9px] font-bold text-gray-400 uppercase tracking-wider mb-1">Invalidation</div>
          {primary.invalidation.map((iv, i) => (
            <div key={i} className="flex items-start gap-2 text-[10px] text-orange-500">
              <XCircle className="w-3 h-3 mt-0.5 shrink-0" />{iv}
            </div>
          ))}
        </div>
      )}
      {secondary.length > 0 && (
        <div className="pt-2 border-t border-gray-100 mt-2">
          <div className="text-[9px] font-bold text-gray-400 uppercase tracking-wider mb-1">Secondary Setups</div>
          <div className="flex gap-3">
            {secondary.map((s, i) => (
              <div key={i} className="flex items-center gap-1.5 text-[11px]">
                <div className={`w-1.5 h-1.5 rounded-full ${STATUS_DOT[s.status] || 'bg-gray-400'}`} />
                <span className="font-bold text-gray-700">{SETUP_LABELS[s.type] || s.type}</span>
                <span className="text-gray-400 tabular-nums">{Math.round(s.confidence * 100)}%</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </IntelligenceBlock>
  );
}

// ═══════════════════════════════════════════
// ZONE: TRADE PROBABILITY (dark)
// ═══════════════════════════════════════════
function ProbabilityBlock({ prob }) {
  if (!prob) return null;
  const bars = [
    { label: 'Continuation', value: prob.continuation, color: 'bg-emerald-400', textColor: 'text-emerald-400' },
    { label: 'Failure Risk', value: prob.failure, color: 'bg-red-400', textColor: 'text-red-400' },
    { label: prob.upgrade > 0 ? 'Upgrade' : 'Status', value: prob.upgrade, color: 'bg-cyan-400', textColor: 'text-cyan-400' },
  ];
  return (
    <IntelligenceBlock dark testId="probability-layer">
      <div className="flex items-center gap-2 mb-4">
        <BarChart3 className="w-4 h-4 text-gray-400" />
        <h3 className="text-xs font-bold text-gray-400 uppercase tracking-[0.15em]">Trade Probability</h3>
      </div>
      <div className="grid grid-cols-3 gap-6 mb-3">
        {bars.map(({ label, value, color, textColor }) => (
          <div key={label} data-testid={`prob-${label.toLowerCase().replace(/\s/g, '-')}`}>
            <div className="flex items-center justify-between mb-1">
              <span className="text-[9px] font-bold text-gray-500 uppercase tracking-wider">{label}</span>
              <span className={`text-sm font-black tabular-nums ${textColor}`}>{value != null ? `${Math.round(value * 100)}%` : '—'}</span>
            </div>
            <div className="h-2 bg-gray-800 rounded-full overflow-hidden">
              <div className={`h-full rounded-full ${color} transition-all`} style={{ width: `${(value || 0) * 100}%` }} />
            </div>
          </div>
        ))}
      </div>
      {prob.summary && (
        <div className="text-[11px] text-gray-400 italic pt-2 border-t border-gray-800" data-testid="prob-summary">{prob.summary}</div>
      )}
    </IntelligenceBlock>
  );
}

// ═══════════════════════════════════════════
// ZONE 5: OTC DETECTIONS (dark)
// ═══════════════════════════════════════════
function OTCBlock({ otcData }) {
  const trades = otcData?.trades || [];
  const confColor = (c) => c >= 0.6 ? 'text-red-400' : c >= 0.4 ? 'text-amber-400' : 'text-gray-400';

  return (
    <IntelligenceBlock dark testId="otc-detections">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <Package className="w-4 h-4 text-amber-400" />
          <h3 className="text-xs font-bold text-gray-400 uppercase tracking-[0.15em]">OTC Detections</h3>
        </div>
        <span className="text-[10px] font-bold text-amber-400" data-testid="otc-total-count">{otcData?.count || 0} found</span>
      </div>
      {trades.length === 0 ? (
        <p className="text-[11px] text-gray-500 text-center py-4">No OTC trades detected</p>
      ) : (
        <div className="space-y-2">
          {trades.slice(0, 6).map((t, i) => (
            <div key={i} className="py-2 border-b border-gray-800 last:border-0" data-testid={`engine-otc-${i}`}>
              <div className="flex items-center justify-between mb-1">
                <div className="flex items-center gap-2">
                  <span className="text-xs font-black text-white">{t.asset}</span>
                  <ArrowLeftRight className="w-3 h-3 text-gray-500" />
                  <span className="text-xs font-black text-cyan-400">{t.stablecoin}</span>
                </div>
                <span className="text-sm font-black text-amber-400 tabular-nums">{t.usd_value_fmt}</span>
              </div>
              <div className="flex items-center justify-between text-[10px]">
                <span className="text-gray-500">{t.source_entity}</span>
                <span className={`font-bold ${confColor(t.confidence)}`}>{(t.confidence * 100).toFixed(0)}%</span>
              </div>
            </div>
          ))}
        </div>
      )}
    </IntelligenceBlock>
  );
}

// ═══════════════════════════════════════════
// ZONE 5: MARKET MAKERS (dark)
// ═══════════════════════════════════════════
function MarketMakersBlock({ mmData }) {
  const makers = mmData?.market_makers || [];
  const typeColor = (t) => t === 'market_maker' ? 'text-red-400' : t === 'probable_mm' ? 'text-amber-400' : 'text-gray-500';
  const typeLabel = (t) => t === 'market_maker' ? 'Confirmed MM' : t === 'probable_mm' ? 'Probable MM' : 'Unlikely';

  return (
    <IntelligenceBlock dark testId="market-makers">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <Gauge className="w-4 h-4 text-violet-400" />
          <h3 className="text-xs font-bold text-gray-400 uppercase tracking-[0.15em]">Market Makers</h3>
        </div>
        <span className="text-[10px] font-bold text-violet-400" data-testid="mm-total-count">{mmData?.count || 0} detected</span>
      </div>
      {makers.length === 0 ? (
        <p className="text-[11px] text-gray-500 text-center py-4">No market makers detected</p>
      ) : (
        <div className="space-y-2">
          {makers.slice(0, 6).map((m, i) => (
            <div key={i} className="py-2 border-b border-gray-800 last:border-0" data-testid={`engine-mm-${i}`}>
              <div className="flex items-center justify-between mb-1">
                <div className="flex items-center gap-2">
                  <span className="text-xs font-black text-white">{m.name}</span>
                  <span className={`text-[9px] font-bold ${typeColor(m.type)}`}>{typeLabel(m.type)}</span>
                </div>
                <span className={`text-sm font-black tabular-nums ${m.score >= 0.7 ? 'text-red-400' : m.score >= 0.5 ? 'text-amber-400' : 'text-gray-400'}`} data-testid={`mm-score-${i}`}>
                  {(m.score * 100).toFixed(0)}%
                </span>
              </div>
              <div className="grid grid-cols-4 gap-2 mt-1">
                {[
                  { l: 'Bidir', v: m.signals?.bidirectional_flow },
                  { l: 'Exch', v: m.signals?.exchange_density },
                  { l: 'Stable', v: m.signals?.stablecoin_recycling },
                  { l: 'Vel', v: m.signals?.velocity },
                ].map(({ l, v }) => (
                  <div key={l} className="text-center">
                    <div className="text-[9px] text-gray-600">{l}</div>
                    <div className={`text-[10px] font-bold tabular-nums ${(v || 0) >= 0.5 ? 'text-gray-300' : 'text-gray-600'}`}>
                      {v != null ? (v * 100).toFixed(0) + '%' : '-'}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </IntelligenceBlock>
  );
}

// ═══════════════════════════════════════════
// MAIN PAGE
// ═══════════════════════════════════════════
export default function MarketBrainEngine() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [win, setWin] = useState('30d');
  const [otcData, setOtcData] = useState(null);
  const [mmData, setMmData] = useState(null);

  const fetchData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [engineRes, otcRes, mmRes] = await Promise.allSettled([
        fetch(`${API}/api/engine/context?window=${win}`).then(r => r.json()),
        fetch(`${API}/api/intelligence/otc`).then(r => r.json()),
        fetch(`${API}/api/intelligence/market-makers`).then(r => r.json()),
      ]);
      if (engineRes.status === 'fulfilled') {
        if (!engineRes.value.ok) throw new Error(engineRes.value.error || 'API error');
        setData(engineRes.value);
      } else {
        throw engineRes.reason;
      }
      setOtcData(otcRes.status === 'fulfilled' ? otcRes.value : null);
      setMmData(mmRes.status === 'fulfilled' ? mmRes.value : null);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, [win]);

  useEffect(() => { fetchData(); }, [fetchData]);

  return (
    <div className="space-y-4" data-testid="market-brain-engine">
      {/* Header */}
      <div className="flex items-center justify-end gap-3">
        <div className="flex items-center gap-1">
          {['24h', '7d', '30d'].map(w => (
            <button key={w} onClick={() => setWin(w)}
              className={`px-3 py-1.5 text-xs font-bold transition-colors ${win === w ? 'text-gray-900' : 'text-gray-400 hover:text-gray-700'}`}
              data-testid={`window-${w}`}>{w.toUpperCase()}</button>
          ))}
        </div>
        <button onClick={fetchData} disabled={loading}
          className="p-2 text-gray-400 hover:text-gray-700 transition-colors disabled:opacity-50" data-testid="refresh-btn">
          <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
        </button>
      </div>

      {error && !loading && (
        <IntelligenceBlock dark testId="engine-error">
          <div className="flex items-center justify-between py-4">
            <div>
              <div className="text-sm font-bold text-red-400 mb-1">Failed to load engine data</div>
              <p className="text-xs text-gray-500">{error}</p>
            </div>
            <button onClick={fetchData} className="px-3 py-1.5 text-xs font-bold text-white bg-gray-800 rounded hover:bg-gray-700">Retry</button>
          </div>
        </IntelligenceBlock>
      )}

      {loading && !data ? <Skeleton dark /> : data && (
        <>
          {/* Zone 1: Decision Terminal */}
          <DecisionHero data={data} />

          {/* Zone 1.5: Regime + Setup Structure */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <RegimeBlock regime={data.regime_engine} />
            <SetupBlock setupEngine={data.setup_engine} />
          </div>

          {/* Zone 1.7: Trade Probability */}
          <ProbabilityBlock prob={data.probability_layer} />

          {/* Zone 2: Decision Explanation + Gates */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
            <div className="lg:col-span-2"><ExplanationBlock explanation={data.decision_explanation} /></div>
            <GatesBlock gates={data.gates} risks={data.risks} />
          </div>

          {/* Zone 3: Context Matrix + Signal Feed */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <ContextBlock matrix={data.context_matrix} scores={data.scores} />
            <SignalsBlock signals={data.signals} />
          </div>

          {/* Zone 4: OTC Detections + Market Makers */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <OTCBlock otcData={otcData} />
            <MarketMakersBlock mmData={mmData} />
          </div>

          {/* Meta */}
          <div className="text-[10px] text-gray-400 text-right">
            Engine v{data.meta?.version || '13.0'} — {data.meta?.modules?.join(' + ')}
          </div>
        </>
      )}
    </div>
  );
}
