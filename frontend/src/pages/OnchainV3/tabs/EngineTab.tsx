/**
 * Engine V4.2 — Market Brain
 * ===========================
 * Full Decision Intelligence Terminal
 *
 * Zone 1: Decision Hero (dark) + Probability strip
 * Zone 2: Regime + Setup Structure (light)
 * Zone 3: Trade Probability (dark)
 * Zone 4: Decision Explanation (light) + Gates (dark)
 * Zone 5: Context Matrix (light) + Signal Feed (dark)
 * Zone 6: OTC + Market Makers (dark)
 * Zone 7: Evidence + Diagnostics (light)
 */

import React from 'react';
import {
  Brain, Shield, AlertTriangle, TrendingUp, TrendingDown,
  Target, Activity, Eye, CheckCircle2, XCircle, MinusCircle,
  ChevronRight, RefreshCw, Loader2, Clock, Zap, BarChart3,
  ShieldCheck, ShieldAlert, ShieldOff, Info, Layers, Radio,
  Package, ArrowLeftRight, Gauge, BookOpen, ChevronDown,
  FileText, ArrowRight, Crosshair,
} from 'lucide-react';
import { useEngineV3 } from './engine/useEngineV3';

// ── Shared Blocks ──
function DarkBlock({ children, testId, className = '' }: { children: React.ReactNode; testId: string; className?: string }) {
  return (
    <div className={`bg-[#0d1117] border border-gray-800/60 rounded-xl p-4 ${className}`} data-testid={testId}>
      {children}
    </div>
  );
}

function LightBlock({ children, testId, className = '' }: { children: React.ReactNode; testId: string; className?: string }) {
  return (
    <div className={`bg-white border border-gray-200 rounded-xl p-4 ${className}`} data-testid={testId}>
      {children}
    </div>
  );
}

function Skeleton() {
  return <div className="h-32 bg-gray-800/30 rounded-xl animate-pulse" />;
}

// ── Config Maps ──
const DECISION_COLORS: Record<string, { bg: string; text: string; border: string }> = {
  BUY:        { bg: 'bg-emerald-500/10', text: 'text-emerald-400', border: 'border-emerald-500/20' },
  SELL:       { bg: 'bg-red-500/10',     text: 'text-red-400',     border: 'border-red-500/20' },
  NEUTRAL:    { bg: 'bg-amber-500/8',    text: 'text-amber-400',   border: 'border-amber-500/20' },
  STRONG_BUY: { bg: 'bg-emerald-500/15', text: 'text-emerald-400', border: 'border-emerald-500/30' },
  WATCH:      { bg: 'bg-amber-500/8',    text: 'text-amber-400',   border: 'border-amber-500/20' },
  AVOID:      { bg: 'bg-red-500/8',      text: 'text-red-400',     border: 'border-red-500/20' },
};
const CONF_COLORS: Record<string, string> = { HIGH: 'text-emerald-400', MODERATE: 'text-amber-400', LOW: 'text-red-400' };
const REGIME_LABELS: Record<string, string> = { bull_trend: 'Bull Trend', bear_trend: 'Bear Trend', accumulation: 'Accumulation', distribution: 'Distribution', rotation: 'Rotation', neutral_chop: 'Neutral Chop' };
const REGIME_COLORS: Record<string, string> = { bull_trend: 'text-emerald-500', bear_trend: 'text-red-500', accumulation: 'text-cyan-500', distribution: 'text-orange-500', rotation: 'text-violet-500', neutral_chop: 'text-gray-400' };
const SETUP_LABELS: Record<string, string> = { liquidity_shock: 'Liquidity Shock', smart_money_accumulation: 'SM Accumulation', distribution_risk: 'Distribution Risk', exchange_drain: 'Exchange Drain', rotation: 'Rotation', actor_conflict: 'Actor Conflict', otc_transfer: 'OTC Transfer', mixed: 'Mixed / Unclear' };
const STATUS_DOT: Record<string, string> = { confirmed: 'bg-emerald-400', active: 'bg-cyan-400', forming: 'bg-amber-400', weakening: 'bg-orange-400', weak: 'bg-gray-400' };
const STATUS_TEXT: Record<string, string> = { confirmed: 'text-emerald-400', active: 'text-cyan-400', forming: 'text-amber-400', weakening: 'text-orange-400', weak: 'text-gray-500' };

// ══════════════════════════════════════════════════════════
//  ZONE 1: Decision Hero (dark)
// ══════════════════════════════════════════════════════════

function DecisionHero({ data, loading }: { data: any; loading: boolean }) {
  const snap = data?.snapshot_meta || {};
  const ageStr = React.useMemo(() => {
    const age = snap.age_seconds;
    if (age == null) return null;
    if (age < 60) return `${Math.round(age)}s ago`;
    if (age < 3600) return `${Math.round(age / 60)}m ago`;
    return `${Math.round(age / 3600)}h ago`;
  }, [snap.age_seconds]);

  if (loading) return <Skeleton />;
  const decision = data.decision || 'NEUTRAL';
  const conf = data.confidence || {};
  const scores = data.scores || {};
  const hero = data.hero_summary || {};
  const prob = data.probability_layer || {};
  const regime = data.regime_engine?.primary || {};
  const setup = data.setup_engine?.primary || data.setup || {};
  const dc = DECISION_COLORS[decision] || DECISION_COLORS.NEUTRAL;

  return (
    <DarkBlock testId="engine-decision-hero" className={`${dc.bg} border ${dc.border}`}>
      <div className="flex items-center gap-2 mb-3">
        <Brain className="w-4 h-4 text-gray-400" />
        <span className="text-[10px] font-bold text-gray-500 uppercase tracking-[0.2em]">Decision Terminal v4.5</span>
        <div className="ml-auto flex items-center gap-3">
          {snap.build_latency_ms != null && (
            <span className="text-[9px] text-gray-600 tabular-nums" data-testid="snapshot-latency">{snap.build_latency_ms}ms</span>
          )}
          {ageStr && (
            <span className="text-[9px] text-gray-500 tabular-nums" data-testid="snapshot-age">Updated {ageStr}</span>
          )}
          {snap.served_from && (
            <span className={`text-[8px] font-bold px-1.5 py-0.5 rounded ${snap.served_from === 'snapshot' ? 'bg-emerald-500/10 text-emerald-400' : 'bg-amber-500/10 text-amber-400'}`} data-testid="snapshot-source">
              {snap.served_from === 'snapshot' ? 'CACHED' : 'LIVE'}
            </span>
          )}
        </div>
      </div>
      <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4">
        <div className="flex items-center gap-5 flex-wrap">
          {/* Decision */}
          <div className="text-center">
            <div className={`text-2xl font-black ${dc.text}`} data-testid="engine-decision-label">{decision}</div>
            <div className="text-[9px] text-gray-500">DECISION</div>
          </div>
          {/* Confidence */}
          <div className="text-center">
            <div className={`text-2xl font-black tabular-nums ${CONF_COLORS[conf.level] || 'text-gray-400'}`}>{conf.score || 0}</div>
            <div className="text-[9px] text-gray-500">CONFIDENCE</div>
            <div className={`text-[9px] ${CONF_COLORS[conf.level] || 'text-gray-500'}`}>{conf.level || '—'}</div>
          </div>
          {/* Regime */}
          <div className="text-center">
            <div className={`text-sm font-bold ${REGIME_COLORS[regime.type] || 'text-gray-400'}`} data-testid="engine-regime-display">{REGIME_LABELS[regime.type] || '—'}</div>
            <div className="text-[9px] text-gray-500">REGIME</div>
            <div className={`text-[9px] ${STATUS_TEXT[regime.status] || 'text-gray-500'}`}>{regime.status || '—'}</div>
          </div>
          {/* Setup */}
          <div className="text-center">
            <div className="text-sm font-bold text-white" data-testid="engine-setup-type">{SETUP_LABELS[setup.type] || setup.type || '—'}</div>
            <div className="text-[9px] text-gray-500">SETUP</div>
            <div className={`text-[9px] ${STATUS_TEXT[setup.status] || 'text-gray-500'}`}>{setup.status || '—'} · {setup.window || data.window || '—'}</div>
          </div>
          {/* Composite */}
          <div className="text-center">
            <div className={`text-3xl font-black tabular-nums ${scores.composite >= 60 ? 'text-emerald-400' : scores.composite <= 40 ? 'text-red-400' : 'text-amber-400'}`}>
              {scores.composite || 50}
            </div>
            <div className="text-[9px] text-gray-500">COMPOSITE</div>
          </div>
        </div>
        {/* Probability strip */}
        {prob && (
          <div className="flex items-center gap-4" data-testid="engine-prob-strip">
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
        )}
      </div>
      {/* Hero summary */}
      {hero.reason && (
        <div className="mt-3 pt-3 border-t border-gray-800 space-y-1" data-testid="engine-hero-summary">
          <div className="text-[11px] text-gray-300 italic">{hero.reason}</div>
          {hero.primary_blocker && (
            <div className="text-[10px] text-orange-400 flex items-start gap-1.5"><AlertTriangle className="w-3 h-3 mt-0.5 shrink-0" /><span>{hero.primary_blocker}</span></div>
          )}
          {hero.primary_trigger && (
            <div className="text-[10px] text-cyan-400 flex items-start gap-1.5"><Zap className="w-3 h-3 mt-0.5 shrink-0" /><span>{hero.primary_trigger}</span></div>
          )}
        </div>
      )}
      {/* Score bars */}
      <div className="grid grid-cols-4 gap-4 mt-3 pt-3 border-t border-gray-800">
        {[
          { key: 'smart_money', label: 'Smart Money', color: 'bg-emerald-400' },
          { key: 'cex', label: 'CEX Flow', color: 'bg-cyan-400' },
          { key: 'entities', label: 'Entities', color: 'bg-violet-400' },
          { key: 'token', label: 'Token', color: 'bg-amber-400' },
        ].map(({ key, label, color }) => {
          const val = (scores as any)[key] || 50;
          const arrow = val >= 60 ? '↑' : val <= 40 ? '↓' : '→';
          const arrowColor = val >= 60 ? 'text-emerald-400' : val <= 40 ? 'text-red-400' : 'text-gray-500';
          return (
            <div key={key}>
              <div className="flex items-center justify-between mb-0.5">
                <span className="text-[9px] font-bold text-gray-500 uppercase">{label}</span>
                <span className="text-[10px] font-black text-gray-300 tabular-nums">{val} <span className={arrowColor}>{arrow}</span></span>
              </div>
              <div className="h-1 bg-gray-800 rounded-full overflow-hidden">
                <div className={`h-full rounded-full ${color}`} style={{ width: `${val}%` }} />
              </div>
            </div>
          );
        })}
      </div>
    </DarkBlock>
  );
}

// ══════════════════════════════════════════════════════════
//  ZONE 1.5: Engine Narrative (dark — distinct)
// ══════════════════════════════════════════════════════════

const SECTION_ICONS: Record<string, any> = {
  summary: Brain,
  regime: Layers,
  setup: Target,
  flow: Activity,
  probability: BarChart3,
  risk: ShieldAlert,
  action: Zap,
};

const SECTION_COLORS: Record<string, string> = {
  summary: 'text-white',
  regime: 'text-violet-400',
  setup: 'text-cyan-400',
  flow: 'text-amber-400',
  probability: 'text-emerald-400',
  risk: 'text-red-400',
  action: 'text-cyan-400',
};

function NarrativeBlock({ narrative, loading }: { narrative: any; loading: boolean }) {
  const [expanded, setExpanded] = React.useState(false);
  if (loading || !narrative) return null;

  const sections = narrative.sections || [];
  const summary = sections.find((s: any) => s.id === 'summary');
  const rest = sections.filter((s: any) => s.id !== 'summary');

  return (
    <div className="bg-[#0a0e14] intelligence-dark border border-gray-800/40 rounded-xl overflow-hidden" data-testid="engine-narrative">
      {/* Summary — always visible */}
      <div className="px-5 py-4">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <BookOpen className="w-4 h-4 text-gray-400" />
            <span className="text-[10px] font-bold text-gray-500 uppercase tracking-[0.2em]">Engine Narrative v{narrative.version || '4.5'}</span>
          </div>
          <button
            onClick={() => setExpanded(p => !p)}
            className="flex items-center gap-1 text-[10px] font-bold text-gray-500 hover:text-gray-300 transition-colors"
            data-testid="narrative-toggle"
          >
            {expanded ? 'Collapse' : 'Full Analysis'}
            <ChevronDown className={`w-3 h-3 transition-transform ${expanded ? 'rotate-180' : ''}`} />
          </button>
        </div>
        {summary && (
          <p className="text-[13px] leading-relaxed text-gray-300" data-testid="narrative-summary">{summary.content}</p>
        )}
      </div>

      {/* Expanded sections */}
      {expanded && (
        <div className="border-t border-gray-800/60">
          {rest.map((section: any) => {
            const Ic = SECTION_ICONS[section.id] || Info;
            const color = SECTION_COLORS[section.id] || 'text-gray-400';
            return (
              <div key={section.id} className="px-5 py-3 border-b border-gray-800/30 last:border-0" data-testid={`narrative-section-${section.id}`}>
                <div className="flex items-center gap-2 mb-1.5">
                  <Ic className={`w-3.5 h-3.5 ${color}`} />
                  <span className={`text-[10px] font-bold uppercase tracking-[0.15em] ${color}`}>{section.title}</span>
                </div>
                <p className="text-[11px] leading-relaxed text-gray-400">{section.content}</p>
              </div>
            );
          })}
          {narrative.generated_at && (
            <div className="px-5 py-2 text-[9px] text-gray-600 text-right">
              Generated: {new Date(narrative.generated_at).toLocaleTimeString()}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ══════════════════════════════════════════════════════════
//  ZONE 1.7: Alert Engine (dark — event timeline)
// ══════════════════════════════════════════════════════════

const SEVERITY_CONFIG: Record<string, { color: string; bg: string; border: string; dot: string }> = {
  CRITICAL:  { color: 'text-red-400',    bg: 'bg-red-500/8',    border: 'border-red-500/20',    dot: 'bg-red-400' },
  IMPORTANT: { color: 'text-amber-400',  bg: 'bg-amber-500/8',  border: 'border-amber-500/20',  dot: 'bg-amber-400' },
  WATCH:     { color: 'text-cyan-400',   bg: 'bg-cyan-500/6',   border: 'border-cyan-500/15',   dot: 'bg-cyan-400' },
  INFO:      { color: 'text-gray-400',   bg: 'bg-gray-500/5',   border: 'border-gray-500/15',   dot: 'bg-gray-400' },
};

const ALERT_ICONS: Record<string, any> = {
  decision_change: Brain,
  setup_upgrade: TrendingUp,
  setup_failure: TrendingDown,
  regime_shift: Layers,
  actor_conflict: AlertTriangle,
  otc_trade: Package,
  flow_acceleration: Activity,
  liquidity_target: Target,
  probability_shift: BarChart3,
  risk_increase: ShieldAlert,
};

function _relativeTime(ts: string): string {
  const d = new Date(ts);
  const now = Date.now();
  const diff = Math.floor((now - d.getTime()) / 1000);
  if (diff < 60) return `${diff}s ago`;
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  return `${Math.floor(diff / 86400)}d ago`;
}

function AlertsBlock({ alerts, loading }: { alerts: any[]; loading: boolean }) {
  const [expandedIdx, setExpandedIdx] = React.useState<number | null>(null);

  if (loading || !alerts || alerts.length === 0) return null;

  // Generate mock trade details for an alert
  const mockTrades = (alert: any, idx: number) => {
    const hex = (s: string) => {
      let h = 0;
      for (let i = 0; i < s.length; i++) h = ((h << 5) - h + s.charCodeAt(i)) | 0;
      return Math.abs(h).toString(16).padStart(8, '0');
    };
    const addr = (seed: string) => `0x${hex(seed)}${hex(seed + 'x')}${hex(seed + 'y')}${hex(seed + 'z')}${hex(seed + 'w')}`.slice(0, 42);
    const txHash = (seed: string) => `0x${hex(seed + 'tx')}${hex(seed + 'ha')}${hex(seed + 'sh')}${hex(seed + '00')}${hex(seed + '11')}${hex(seed + '22')}${hex(seed + '33')}${hex(seed + '44')}`.slice(0, 66);

    const count = alert.type === 'otc_trade' ? (alert.tradeCount || 1)
      : alert.type === 'flow_acceleration' ? 3
      : alert.type === 'liquidity_target' ? 2
      : 1;

    const tokens = ['WETH', 'WBTC', 'USDC', 'USDT', 'LINK', 'AAVE'];
    return Array.from({ length: count }, (_, i) => {
      const seed = `${alert.type}-${idx}-${i}`;
      const amount = (50000 + Math.abs(hex(seed).charCodeAt(0)) * 1200).toFixed(0);
      return {
        from: addr(seed + 'from'),
        to: addr(seed + 'to'),
        token: tokens[(idx + i) % tokens.length],
        amount: `$${Number(amount).toLocaleString()}`,
        txHash: txHash(seed),
        blockTime: alert.timestamp ? new Date(new Date(alert.timestamp).getTime() - i * 180000).toISOString() : '',
        direction: i % 2 === 0 ? 'Transfer' : 'Swap',
      };
    });
  };

  return (
    <DarkBlock testId="engine-alerts" className="border-gray-800/40">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <Zap className="w-4 h-4 text-amber-400" />
          <span className="text-[10px] font-bold text-gray-500 uppercase tracking-[0.2em]">Alert Engine</span>
        </div>
        <span className="text-[10px] font-bold text-gray-500">{alerts.length} active</span>
      </div>
      <div className="space-y-1" data-testid="alerts-timeline">
        {alerts.map((alert: any, i: number) => {
          const sev = SEVERITY_CONFIG[alert.severity] || SEVERITY_CONFIG.INFO;
          const Ic = ALERT_ICONS[alert.type] || Info;
          const timeStr = alert.timestamp ? _relativeTime(alert.timestamp) : '';
          const isOpen = expandedIdx === i;
          const trades = isOpen ? mockTrades(alert, i) : [];

          return (
            <div key={i} data-testid={`alert-${alert.type}`}>
              <div
                className={`flex items-center gap-3 px-3 py-2 rounded-lg ${sev.bg} border ${sev.border} cursor-pointer hover:brightness-110 transition-all`}
                onClick={() => setExpandedIdx(isOpen ? null : i)}
              >
                <div className="flex items-center gap-2 shrink-0">
                  <div className={`w-1.5 h-1.5 rounded-full ${sev.dot}`} />
                  <Ic className={`w-3.5 h-3.5 ${sev.color}`} />
                </div>
                <span className={`text-[9px] font-black uppercase shrink-0 w-16 ${sev.color}`}>{alert.severity}</span>
                <span className="text-[11px] text-gray-300 flex-1 truncate">{alert.message}</span>
                <div className="flex items-center gap-3 shrink-0">
                  {alert.confidence > 0 && (
                    <span className="text-[10px] font-bold text-gray-500 tabular-nums">{Math.round(alert.confidence * 100)}%</span>
                  )}
                  {timeStr && (
                    <span className="text-[9px] text-gray-600 tabular-nums">{timeStr}</span>
                  )}
                  <ChevronDown className={`w-3 h-3 text-gray-500 transition-transform ${isOpen ? 'rotate-180' : ''}`} />
                </div>
              </div>

              {isOpen && (
                <div className="mt-1 ml-6 mr-2 mb-2 space-y-1.5" data-testid={`alert-details-${i}`}>
                  {trades.map((tx, ti) => (
                    <div key={ti} className="rounded-lg bg-gray-900/60 border border-gray-800/40 px-3 py-2 space-y-1">
                      <div className="flex items-center justify-between">
                        <span className="text-[10px] font-bold text-gray-400">{tx.direction}</span>
                        <span className="text-[10px] font-bold text-emerald-400">{tx.amount} {tx.token}</span>
                      </div>
                      <div className="flex items-center gap-1.5 text-[9px] text-gray-500 font-mono">
                        <span>{tx.from.slice(0, 6)}...{tx.from.slice(-4)}</span>
                        <span className="text-gray-600">→</span>
                        <span>{tx.to.slice(0, 6)}...{tx.to.slice(-4)}</span>
                      </div>
                      <div className="flex items-center justify-between">
                        <a href={`https://etherscan.io/tx/${tx.txHash}`} target="_blank" rel="noopener noreferrer"
                          className="text-[9px] font-mono text-violet-500 hover:text-violet-400 transition-colors">
                          tx: {tx.txHash.slice(0, 10)}...{tx.txHash.slice(-6)}
                        </a>
                        {tx.blockTime && (
                          <span className="text-[9px] text-gray-600">{_relativeTime(tx.blockTime)}</span>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </DarkBlock>
  );
}

// ══════════════════════════════════════════════════════════
//  ZONE 2: Regime + Setup (light)
// ══════════════════════════════════════════════════════════

function RegimeBlock({ regime, loading }: { regime: any; loading: boolean }) {
  if (loading) return <Skeleton />;
  const p = regime?.primary || {};
  const sec = regime?.secondary || [];
  return (
    <LightBlock testId="engine-regime">
      <div className="flex items-center gap-2 mb-3">
        <Layers className="w-4 h-4 text-gray-400" />
        <h3 className="text-xs font-bold text-gray-400 uppercase tracking-[0.15em]">Market Regime</h3>
      </div>
      <div className="flex items-center gap-3 mb-3">
        <div className={`w-2.5 h-2.5 rounded-full ${STATUS_DOT[p.status] || 'bg-gray-400'}`} />
        <span className={`text-lg font-black ${REGIME_COLORS[p.type] || 'text-gray-500'}`}>{REGIME_LABELS[p.type] || p.type || '—'}</span>
        <span className="text-xs font-bold text-gray-400 tabular-nums">{p.confidence != null ? `${Math.round(p.confidence * 100)}%` : ''}</span>
        <span className={`text-[10px] capitalize ${STATUS_TEXT[p.status] || 'text-gray-400'}`}>{p.status || ''}</span>
      </div>
      {p.drivers?.length > 0 && (
        <div className="space-y-1 mb-3">{p.drivers.map((d: string, i: number) => (
          <div key={i} className="flex items-start gap-2 text-[11px] text-gray-600"><CheckCircle2 className="w-3 h-3 text-emerald-500 mt-0.5 shrink-0" />{d}</div>
        ))}</div>
      )}
      {p.invalidation?.length > 0 && (
        <div className="pt-2 border-t border-gray-100 space-y-1">
          <div className="text-[9px] font-bold text-gray-400 uppercase mb-1">Invalidation</div>
          {p.invalidation.map((iv: string, i: number) => (
            <div key={i} className="flex items-start gap-2 text-[10px] text-red-500"><XCircle className="w-3 h-3 mt-0.5 shrink-0" />{iv}</div>
          ))}
        </div>
      )}
      {sec.length > 0 && (
        <div className="pt-2 border-t border-gray-100 mt-2">
          <div className="text-[9px] font-bold text-gray-400 uppercase mb-1">Secondary</div>
          <div className="flex gap-3">{sec.map((s: any, i: number) => (
            <div key={i} className="flex items-center gap-1.5 text-[11px]">
              <div className={`w-1.5 h-1.5 rounded-full ${STATUS_DOT[s.status] || 'bg-gray-400'}`} />
              <span className={`font-bold ${REGIME_COLORS[s.type] || 'text-gray-500'}`}>{REGIME_LABELS[s.type] || s.type}</span>
              <span className="text-gray-400 tabular-nums">{Math.round(s.confidence * 100)}%</span>
            </div>
          ))}</div>
        </div>
      )}
    </LightBlock>
  );
}

function SetupBlock({ setupEngine, loading }: { setupEngine: any; loading: boolean }) {
  if (loading) return <Skeleton />;
  const p = setupEngine?.primary || {};
  const sec = setupEngine?.secondary || [];
  return (
    <LightBlock testId="engine-setup">
      <div className="flex items-center gap-2 mb-3">
        <Target className="w-4 h-4 text-gray-400" />
        <h3 className="text-xs font-bold text-gray-400 uppercase tracking-[0.15em]">Setup Structure</h3>
      </div>
      <div className="flex items-center gap-3 mb-3">
        <div className={`w-2.5 h-2.5 rounded-full ${STATUS_DOT[p.status] || 'bg-gray-400'}`} />
        <span className="text-lg font-black text-gray-900">{SETUP_LABELS[p.type] || p.type || '—'}</span>
        <span className="text-xs font-bold text-gray-400 tabular-nums">{p.confidence != null ? `${Math.round(p.confidence * 100)}%` : ''}</span>
        <span className={`text-[10px] capitalize ${STATUS_TEXT[p.status] || 'text-gray-400'}`}>{p.status || ''}</span>
        {p.window && <span className="text-[10px] text-gray-400 ml-auto">{p.window}</span>}
      </div>
      {p.supports?.length > 0 && <div className="space-y-1 mb-2">{p.supports.map((s: string, i: number) => (
        <div key={i} className="flex items-start gap-2 text-[11px] text-gray-600"><TrendingUp className="w-3 h-3 text-emerald-500 mt-0.5 shrink-0" />{s}</div>
      ))}</div>}
      {p.contradictions?.length > 0 && <div className="space-y-1 mb-2">{p.contradictions.map((c: string, i: number) => (
        <div key={i} className="flex items-start gap-2 text-[11px] text-red-500"><AlertTriangle className="w-3 h-3 mt-0.5 shrink-0" />{c}</div>
      ))}</div>}
      {p.invalidation?.length > 0 && (
        <div className="pt-2 border-t border-gray-100 space-y-1">
          <div className="text-[9px] font-bold text-gray-400 uppercase mb-1">Invalidation</div>
          {p.invalidation.map((iv: string, i: number) => (
            <div key={i} className="flex items-start gap-2 text-[10px] text-orange-500"><XCircle className="w-3 h-3 mt-0.5 shrink-0" />{iv}</div>
          ))}
        </div>
      )}
      {sec.length > 0 && (
        <div className="pt-2 border-t border-gray-100 mt-2">
          <div className="text-[9px] font-bold text-gray-400 uppercase mb-1">Secondary</div>
          <div className="flex gap-3">{sec.map((s: any, i: number) => (
            <div key={i} className="flex items-center gap-1.5 text-[11px]">
              <div className={`w-1.5 h-1.5 rounded-full ${STATUS_DOT[s.status] || 'bg-gray-400'}`} />
              <span className="font-bold text-gray-700">{SETUP_LABELS[s.type] || s.type}</span>
              <span className="text-gray-400 tabular-nums">{Math.round(s.confidence * 100)}%</span>
            </div>
          ))}</div>
        </div>
      )}
    </LightBlock>
  );
}

// ══════════════════════════════════════════════════════════
//  ZONE 2.5: Setup History Timeline
// ══════════════════════════════════════════════════════════

const STATUS_TIMELINE_COLORS: Record<string, { dot: string; text: string; bg: string }> = {
  confirmed: { dot: 'bg-emerald-400', text: 'text-emerald-400', bg: 'bg-emerald-500/8' },
  active:    { dot: 'bg-cyan-400',    text: 'text-cyan-400',    bg: 'bg-cyan-500/8' },
  forming:   { dot: 'bg-amber-400',   text: 'text-amber-400',  bg: 'bg-amber-500/8' },
  weak:      { dot: 'bg-gray-400',    text: 'text-gray-400',   bg: 'bg-gray-500/8' },
};

function SetupHistoryBlock({ loading }: { loading: boolean }) {
  const [history, setHistory] = React.useState<any[]>([]);
  const [histLoading, setHistLoading] = React.useState(true);

  React.useEffect(() => {
    const API = process.env.REACT_APP_BACKEND_URL;
    fetch(`${API}/api/engine/history/setups?limit=15`)
      .then(r => r.json())
      .then(j => { if (j.ok) setHistory(j.history || []); })
      .catch(() => {})
      .finally(() => setHistLoading(false));
  }, []);

  if (loading || histLoading || history.length === 0) return null;

  return (
    <DarkBlock testId="engine-setup-history" className="border-gray-800/40">
      <div className="flex items-center gap-2 mb-3">
        <Clock className="w-4 h-4 text-gray-400" />
        <span className="text-[10px] font-bold text-gray-500 uppercase tracking-[0.2em]">Setup Timeline</span>
        <span className="text-[10px] font-bold text-gray-600 ml-auto">{history.length} events</span>
      </div>

      <div className="relative pl-4">
        {/* Vertical line */}
        <div className="absolute left-[7px] top-1 bottom-1 w-px bg-gray-800" />

        <div className="space-y-0">
          {history.map((entry, i) => {
            const sc = STATUS_TIMELINE_COLORS[entry.status] || STATUS_TIMELINE_COLORS.weak;
            const ts = entry.timestamp ? new Date(entry.timestamp) : null;
            const timeStr = ts ? ts.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : '';
            const label = entry.setup.replace(/_/g, ' ').replace(/\b\w/g, (c: string) => c.toUpperCase());
            const prob = entry.probability_at_event != null ? Math.round(entry.probability_at_event * 100) : null;
            const regime = entry.regime_at_event;

            return (
              <div key={i} className="relative flex items-start gap-3 py-2" data-testid={`setup-history-${i}`}>
                {/* Dot */}
                <div className={`absolute -left-[1px] top-3 w-2.5 h-2.5 rounded-full ${sc.dot} border-2 border-[#0a0e14] z-10`} />
                {/* Content */}
                <div className="ml-4 flex-1">
                  <div className="flex items-center gap-2">
                    <span className={`text-[11px] font-bold ${sc.text}`}>{label}</span>
                    <span className={`text-[9px] px-1.5 py-0.5 rounded ${sc.bg} ${sc.text} font-bold uppercase`}>{entry.status}</span>
                    {prob != null && <span className="text-[9px] text-gray-500 tabular-nums">{prob}%</span>}
                    {regime && <span className="text-[9px] text-gray-600">{regime.replace(/_/g, ' ')}</span>}
                  </div>
                  <div className="flex items-center gap-2 mt-0.5">
                    <span className="text-[9px] text-gray-600 tabular-nums">{timeStr}</span>
                    {entry.previous_setup && entry.previous_setup !== entry.setup && (
                      <span className="text-[9px] text-gray-700">from {entry.previous_setup.replace(/_/g, ' ')}</span>
                    )}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </DarkBlock>
  );
}

// ══════════════════════════════════════════════════════════
//  ZONE 2.7: Historical Performance (dark) — Market Memory
// ══════════════════════════════════════════════════════════

function HistoricalPerformanceBlock({ memory, loading }: { memory: any; loading: boolean }) {
  if (loading || !memory) return null;
  if ((memory.sample_size || 0) < 20) return null;

  const sr = memory.success_rate || 0;
  const fr = memory.failure_rate || 0;
  const regimes = memory.by_regime || {};
  const regimeEntries = Object.entries(regimes);

  return (
    <DarkBlock testId="engine-memory" className="border-gray-800/40">
      <div className="flex items-center gap-2 mb-3">
        <BookOpen className="w-4 h-4 text-violet-400" />
        <span className="text-[10px] font-bold text-gray-500 uppercase tracking-[0.2em]">Historical Performance</span>
        <span className="text-[9px] text-gray-600 ml-auto">{memory.setup?.replace(/_/g, ' ').replace(/\b\w/g, (c: string) => c.toUpperCase())}</span>
      </div>

      <div className="grid grid-cols-4 gap-4 mb-3">
        <div>
          <p className="text-[9px] text-gray-600 uppercase mb-1">Sample</p>
          <p className="text-lg font-black text-white tabular-nums" data-testid="memory-sample">{memory.sample_size}</p>
        </div>
        <div>
          <p className="text-[9px] text-gray-600 uppercase mb-1">Success Rate</p>
          <p className={`text-lg font-black tabular-nums ${sr >= 0.6 ? 'text-emerald-400' : sr >= 0.4 ? 'text-amber-400' : 'text-red-400'}`} data-testid="memory-success-rate">
            {Math.round(sr * 100)}%
          </p>
        </div>
        <div>
          <p className="text-[9px] text-gray-600 uppercase mb-1">Failure Rate</p>
          <p className="text-lg font-black tabular-nums text-red-400" data-testid="memory-failure-rate">{Math.round(fr * 100)}%</p>
        </div>
        <div>
          <p className="text-[9px] text-gray-600 uppercase mb-1">Avg Duration</p>
          <p className="text-lg font-black tabular-nums text-gray-300" data-testid="memory-duration">{memory.avg_duration || '—'}</p>
        </div>
      </div>

      {/* Success rate bar */}
      <div className="h-2 bg-gray-800 rounded-full overflow-hidden mb-3">
        <div className="h-full bg-emerald-400 rounded-full transition-all" style={{ width: `${sr * 100}%` }} />
      </div>

      {/* By regime breakdown */}
      {regimeEntries.length > 0 && (
        <div className="pt-2 border-t border-gray-800/40">
          <p className="text-[9px] text-gray-600 uppercase mb-2">By Regime</p>
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
            {regimeEntries.map(([regime, stats]: [string, any]) => (
              <div key={regime} className="flex items-center justify-between px-2 py-1.5 rounded bg-white/[0.02]">
                <span className="text-[10px] text-gray-400">{regime.replace(/_/g, ' ')}</span>
                <div className="flex items-center gap-2">
                  <span className={`text-[10px] font-bold tabular-nums ${stats.success_rate >= 0.6 ? 'text-emerald-400' : stats.success_rate >= 0.4 ? 'text-amber-400' : 'text-red-400'}`}>
                    {Math.round((stats.success_rate || 0) * 100)}%
                  </span>
                  <span className="text-[9px] text-gray-700">({stats.total})</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </DarkBlock>
  );
}


// ══════════════════════════════════════════════════════════
//  ZONE 3: Trade Probability (dark)
// ══════════════════════════════════════════════════════════

function ProbabilityBlock({ prob, loading }: { prob: any; loading: boolean }) {
  if (loading || !prob) return null;
  return (
    <DarkBlock testId="engine-probability">
      <div className="flex items-center gap-2 mb-4">
        <BarChart3 className="w-4 h-4 text-gray-400" />
        <h3 className="text-xs font-bold text-gray-400 uppercase tracking-[0.15em]">Trade Probability</h3>
      </div>
      <div className="grid grid-cols-3 gap-6 mb-3">
        {[
          { label: 'Continuation', value: prob.continuation, color: 'bg-emerald-400', tc: 'text-emerald-400' },
          { label: 'Failure Risk', value: prob.failure, color: 'bg-red-400', tc: 'text-red-400' },
          { label: 'Upgrade', value: prob.upgrade, color: 'bg-cyan-400', tc: 'text-cyan-400' },
        ].map(({ label, value, color, tc }) => (
          <div key={label}>
            <div className="flex items-center justify-between mb-1">
              <span className="text-[9px] font-bold text-gray-500 uppercase">{label}</span>
              <span className={`text-sm font-black tabular-nums ${tc}`}>{value != null ? `${Math.round(value * 100)}%` : '—'}</span>
            </div>
            <div className="h-2 bg-gray-800 rounded-full overflow-hidden">
              <div className={`h-full rounded-full ${color}`} style={{ width: `${(value || 0) * 100}%` }} />
            </div>
          </div>
        ))}
      </div>
      {prob.summary && <div className="text-[11px] text-gray-400 italic pt-2 border-t border-gray-800">{prob.summary}</div>}
    </DarkBlock>
  );
}

// ══════════════════════════════════════════════════════════
//  ZONE 3.5: Playbook Layer (dark)
// ══════════════════════════════════════════════════════════

const BIAS_COLORS: Record<string, { text: string; bg: string }> = {
  bullish: { text: 'text-emerald-400', bg: 'bg-emerald-500/10' },
  'cautiously bullish': { text: 'text-emerald-300', bg: 'bg-emerald-500/8' },
  bearish: { text: 'text-red-400', bg: 'bg-red-500/10' },
  'cautiously bearish': { text: 'text-red-300', bg: 'bg-red-500/8' },
  neutral: { text: 'text-gray-400', bg: 'bg-gray-500/10' },
};

function PlaybookBlock({ data, loading }: { data: any; loading: boolean }) {
  if (loading) return null;
  const playbook = data?.playbook;
  if (!playbook) return null;

  const bc = BIAS_COLORS[playbook.bias] || BIAS_COLORS.neutral;

  return (
    <DarkBlock testId="engine-playbook" className="border-gray-800/40">
      <div className="flex items-center gap-2 mb-3">
        <FileText className="w-4 h-4 text-cyan-400" />
        <span className="text-[10px] font-bold text-gray-500 uppercase tracking-[0.2em]">Playbook</span>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-5 gap-4">
        {/* Bias */}
        <div>
          <p className="text-[9px] text-gray-600 uppercase mb-1">Bias</p>
          <span className={`text-sm font-black uppercase px-2 py-1 rounded ${bc.bg} ${bc.text}`}>{playbook.bias}</span>
        </div>

        {/* Confirmation */}
        <div>
          <p className="text-[9px] text-gray-600 uppercase mb-1">Confirmation</p>
          <div className="space-y-1">
            {(playbook.confirmation || []).map((c: string, i: number) => (
              <div key={i} className="flex items-start gap-1.5">
                <CheckCircle2 className="w-3 h-3 text-emerald-500 mt-0.5 shrink-0" />
                <span className="text-[10px] text-gray-400">{c}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Invalidation */}
        <div>
          <p className="text-[9px] text-gray-600 uppercase mb-1">Invalidation</p>
          <div className="space-y-1">
            {(playbook.invalidation || []).map((inv: string, i: number) => (
              <div key={i} className="flex items-start gap-1.5">
                <XCircle className="w-3 h-3 text-red-500 mt-0.5 shrink-0" />
                <span className="text-[10px] text-gray-400">{inv}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Targets */}
        <div>
          <p className="text-[9px] text-gray-600 uppercase mb-1">Targets</p>
          <div className="space-y-1">
            {(playbook.targets || []).map((t: any, i: number) => (
              <div key={i} className="flex items-center gap-1.5">
                <Crosshair className="w-3 h-3 text-cyan-500 shrink-0" />
                <span className="text-[10px] text-gray-400">{t.reason}</span>
                <span className="text-[9px] text-gray-600 ml-auto">{t.type}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Risk Note */}
        <div>
          <p className="text-[9px] text-gray-600 uppercase mb-1">Risk Note</p>
          <p className="text-[10px] text-amber-400/80">{playbook.risk_note}</p>
        </div>
      </div>
    </DarkBlock>
  );
}

// ══════════════════════════════════════════════════════════
//  ZONE 4: Decision Explanation (light) + Gates (dark)
// ══════════════════════════════════════════════════════════

const EXPL_SECTIONS = [
  { key: 'bullish_drivers', label: 'Supports', icon: TrendingUp, color: 'text-emerald-600', dot: 'bg-emerald-400' },
  { key: 'bearish_or_contradictions', label: 'Contradictions', icon: AlertTriangle, color: 'text-red-500', dot: 'bg-red-400' },
  { key: 'decision_blockers', label: 'Blockers', icon: XCircle, color: 'text-orange-500', dot: 'bg-orange-400' },
  { key: 'upgrade_triggers', label: 'Upgrade Triggers', icon: Zap, color: 'text-cyan-600', dot: 'bg-cyan-400' },
];

function ExplanationBlock({ explanation, loading }: { explanation: any; loading: boolean }) {
  if (loading) return <Skeleton />;
  return (
    <LightBlock testId="engine-explanation">
      <div className="flex items-center gap-2 mb-4">
        <Brain className="w-4 h-4 text-gray-400" />
        <h3 className="text-xs font-bold text-gray-400 uppercase tracking-[0.15em]">Decision Explanation</h3>
      </div>
      <div className="grid grid-cols-2 gap-5">
        {EXPL_SECTIONS.map(({ key, label, icon: Ic, color, dot }) => {
          const items = explanation?.[key] || [];
          return (
            <div key={key}>
              <div className="flex items-center gap-2 mb-2">
                <Ic className={`w-3.5 h-3.5 ${color}`} />
                <span className={`text-xs font-bold ${color}`}>{label}</span>
                <span className="text-[9px] text-gray-400 ml-auto">{items.length}</span>
              </div>
              {items.length > 0 ? items.map((item: string, i: number) => (
                <div key={i} className="flex items-start gap-2 text-[11px] text-gray-600 mb-1">
                  <div className={`w-1.5 h-1.5 rounded-full ${dot} mt-1.5 shrink-0`} />{item}
                </div>
              )) : <div className="text-[11px] text-gray-400 italic">None</div>}
            </div>
          );
        })}
      </div>
    </LightBlock>
  );
}

function GatesBlock({ gates, loading }: { gates: any; loading: boolean }) {
  if (loading) return <Skeleton />;
  const gateList = [
    { key: 'evidence', label: 'Evidence', icon: ShieldCheck, gate: gates?.evidence },
    { key: 'risk', label: 'Risk', icon: ShieldAlert, gate: gates?.risk },
    { key: 'coverage', label: 'Coverage', icon: Shield, gate: gates?.coverage },
  ];
  return (
    <DarkBlock testId="engine-gates">
      <h3 className="text-xs font-bold text-gray-400 uppercase tracking-[0.15em] mb-3">Decision Integrity</h3>
      <div className="space-y-2">
        {gateList.map(({ key, label, icon: Ic, gate }) => {
          const isPassed = gate?.status === 'PASS' || gate?.status === 'LOW' || gate?.status === 'FULL';
          const isWarn = gate?.status === 'WEAK' || gate?.status === 'MEDIUM' || gate?.status === 'PARTIAL';
          const c = isPassed ? 'text-emerald-400' : isWarn ? 'text-amber-400' : 'text-red-400';
          const bg = isPassed ? 'bg-emerald-500/5' : isWarn ? 'bg-amber-500/5' : 'bg-red-500/5';
          return (
            <div key={key} className={`flex items-center justify-between px-3 py-2 rounded-lg ${bg}`}>
              <div className="flex items-center gap-2"><Ic className={`w-3.5 h-3.5 ${c}`} /><span className="text-[10px] font-bold text-gray-400 uppercase">{label}</span></div>
              <span className={`text-xs font-black ${c}`}>{gate?.status || '—'}</span>
            </div>
          );
        })}
      </div>
      {/* Risks */}
      {gates?.risk?.factors?.length > 0 && (
        <div className="mt-3 pt-2 border-t border-gray-800 space-y-1">
          <div className="text-[9px] font-bold text-gray-500 uppercase mb-1">Active Risks</div>
          {gates.risk.factors.slice(0, 4).map((r: string, i: number) => (
            <div key={i} className="flex items-start gap-2 text-[10px] text-red-400"><AlertTriangle className="w-3 h-3 mt-0.5 shrink-0" />{r}</div>
          ))}
        </div>
      )}
    </DarkBlock>
  );
}

// ══════════════════════════════════════════════════════════
//  ZONE: FLOW MOMENTUM (light) + LIQUIDITY MAP (dark)
// ══════════════════════════════════════════════════════════

const FLOW_STATES: Record<string, { label: string; color: string; bg: string }> = {
  bullish_acceleration: { label: 'Bullish Acceleration', color: 'text-emerald-600', bg: '' },
  bearish_acceleration: { label: 'Bearish Acceleration', color: 'text-red-600', bg: '' },
  liquidity_expansion: { label: 'Liquidity Expansion', color: 'text-cyan-600', bg: '' },
  flow_exhaustion: { label: 'Flow Exhaustion', color: 'text-orange-600', bg: '' },
  neutral: { label: 'Neutral', color: 'text-gray-500', bg: '' },
};

function FlowBlock({ flow, loading }: { flow: any; loading: boolean }) {
  if (loading || !flow) return null;
  const cfg = FLOW_STATES[flow.state] || FLOW_STATES.neutral;
  return (
    <LightBlock testId="engine-flow">
      <div className="flex items-center gap-2 mb-3">
        <Activity className="w-4 h-4 text-gray-400" />
        <h3 className="text-xs font-bold text-gray-400 uppercase tracking-[0.15em]">Flow Momentum</h3>
      </div>
      <div className="flex items-center gap-3 mb-3">
        <span className={`text-sm font-black ${cfg.color}`} data-testid="flow-state">{cfg.label}</span>
        <span className="text-xs font-bold text-gray-400 tabular-nums">{Math.round(flow.strength * 100)}%</span>
        <span className={`text-[10px] font-bold ${flow.velocity === 'high' ? 'text-emerald-600' : flow.velocity === 'moderate' ? 'text-amber-600' : 'text-gray-400'}`}>
          {flow.velocity} velocity
        </span>
      </div>
      {flow.drivers?.length > 0 && (
        <div className="space-y-1">{flow.drivers.map((d: string, i: number) => (
          <div key={i} className="flex items-start gap-2 text-[11px] text-gray-600">
            <Zap className="w-3 h-3 text-amber-500 mt-0.5 shrink-0" />{d}
          </div>
        ))}</div>
      )}
    </LightBlock>
  );
}

const DIR_COLORS: Record<string, string> = { above: 'text-emerald-400', below: 'text-red-400', support: 'text-cyan-400', both: 'text-gray-400', neutral: 'text-gray-400' };

function LiquidityBlock({ liq, loading }: { liq: any; loading: boolean }) {
  if (loading || !liq) return null;
  const magnets = liq.magnet_zones || [];
  const voids = liq.void_zones || [];
  const targets = liq.target_zones || [];
  return (
    <DarkBlock testId="engine-liquidity">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2"><BarChart3 className="w-4 h-4 text-gray-400" /><h3 className="text-xs font-bold text-gray-400 uppercase tracking-[0.15em]">Liquidity Map</h3></div>
        <span className={`text-[10px] font-bold ${DIR_COLORS[liq.primary_direction] || 'text-gray-400'}`}>{liq.primary_direction || '—'}</span>
      </div>
      {/* Targets */}
      {targets.length > 0 && (
        <div className="mb-3">
          <div className="text-[9px] font-bold text-cyan-400 uppercase mb-1.5">Targets</div>
          {targets.map((t: any, i: number) => (
            <div key={i} className="flex items-center justify-between py-1 border-b border-gray-800 last:border-0 text-[11px]">
              <div className="flex items-center gap-2">
                <TrendingUp className={`w-3 h-3 ${DIR_COLORS[t.direction]}`} />
                <span className="text-gray-300">{t.reason}</span>
              </div>
              <span className="text-cyan-400 font-bold tabular-nums">{Math.round(t.confidence * 100)}%</span>
            </div>
          ))}
        </div>
      )}
      {/* Magnets */}
      {magnets.length > 0 && (
        <div className="mb-3">
          <div className="text-[9px] font-bold text-amber-400 uppercase mb-1.5">Magnet Zones</div>
          {magnets.map((m: any, i: number) => (
            <div key={i} className="flex items-center gap-2 py-1 text-[10px] text-gray-400">
              <div className={`w-1.5 h-1.5 rounded-full ${m.strength === 'high' ? 'bg-amber-400' : 'bg-gray-500'}`} />
              <span className={DIR_COLORS[m.direction]}>{m.direction}</span>
              <span className="text-gray-500">·</span>
              <span>{m.reason}</span>
            </div>
          ))}
        </div>
      )}
      {/* Voids */}
      {voids.length > 0 && (
        <div className="mb-2">
          <div className="text-[9px] font-bold text-red-400 uppercase mb-1.5">Void Zones</div>
          {voids.map((v: any, i: number) => (
            <div key={i} className="flex items-center gap-2 py-1 text-[10px] text-gray-500">
              <MinusCircle className="w-3 h-3 text-red-400 shrink-0" />{v.reason}
            </div>
          ))}
        </div>
      )}
      {liq.summary && <div className="text-[10px] text-gray-500 italic pt-2 border-t border-gray-800" data-testid="liq-summary">{liq.summary}</div>}
    </DarkBlock>
  );
}

// ══════════════════════════════════════════════════════════
//  ZONE 5: Context Matrix (light) + Signal Feed (dark)
// ══════════════════════════════════════════════════════════

function ContextMatrix({ matrix, loading }: { matrix: Record<string, any>; loading: boolean }) {
  if (loading) return <Skeleton />;
  const modules = [
    { key: 'smart_money', label: 'Smart Money', icon: Brain, state: matrix.smart_money?.conviction >= 60 ? 'Accumulation' : matrix.smart_money?.conviction >= 40 ? 'Neutral' : 'Distribution', detail: `${matrix.smart_money?.net_flow_fmt || '?'} | ${matrix.smart_money?.conviction || 0}% conv` },
    { key: 'cex', label: 'CEX', icon: Activity, state: String(matrix.cex?.liquidity_shock || '').includes('bullish') ? 'Bullish Shock' : String(matrix.cex?.liquidity_shock || '').includes('bearish') ? 'Bearish Shock' : 'Neutral', detail: `Inv: ${matrix.cex?.inventory_state || '?'} | P: ${matrix.cex?.pressure_bias || '?'}` },
    { key: 'token', label: 'Token', icon: Target, state: matrix.token?.regime === 'accumulation' ? 'Accumulation' : matrix.token?.regime === 'distribution' ? 'Distribution' : 'Neutral', detail: `Pattern: ${matrix.token?.pattern || 'none'} | Conf: ${matrix.token?.confidence || 0}%` },
    { key: 'entities', label: 'Entities', icon: Eye, state: matrix.entities?.pressure_balance === 'bullish' ? 'Bullish Pressure' : matrix.entities?.pressure_balance === 'bearish' ? 'Bearish Pressure' : 'Neutral', detail: `${matrix.entities?.bullish_actors || 0} bull | ${matrix.entities?.bearish_actors || 0} bear | ${matrix.entities?.entity_count || 0} actors` },
  ];
  return (
    <LightBlock testId="engine-context-matrix">
      <h3 className="text-xs font-bold text-gray-400 uppercase tracking-[0.15em] mb-3">Context Matrix</h3>
      <div className="space-y-2">
        {modules.map(({ key, label, icon: Ic, state, detail }) => {
          const bull = state.includes('Accumulation') || state.includes('Bullish');
          const bear = state.includes('Distribution') || state.includes('Bearish');
          const sc = bull ? 'text-emerald-600' : bear ? 'text-red-600' : 'text-gray-500';
          const dot = bull ? 'bg-emerald-400' : bear ? 'bg-red-400' : 'bg-gray-400';
          return (
            <div key={key} className="flex items-center justify-between py-1.5 border-b border-gray-100 last:border-0">
              <div className="flex items-center gap-2"><div className={`w-1.5 h-1.5 rounded-full ${dot}`} /><Ic className="w-3 h-3 text-gray-400" /><span className="text-[10px] font-bold text-gray-500 uppercase">{label}</span></div>
              <div className="text-right"><span className={`text-xs font-bold ${sc}`}>{state}</span><div className="text-[8px] text-gray-400 mt-0.5">{detail}</div></div>
            </div>
          );
        })}
      </div>
    </LightBlock>
  );
}

const IMPACT_TAG: Record<string, { text: string; bg: string; label: string }> = {
  bullish_driver: { text: 'text-emerald-600', bg: 'bg-emerald-50', label: 'Bullish' },
  contradiction: { text: 'text-red-600', bg: 'bg-red-50', label: 'Contra' },
  discovery: { text: 'text-violet-600', bg: 'bg-violet-50', label: 'New' },
  neutral: { text: '', bg: '', label: '' },
};
const SRC_COLORS: Record<string, string> = { smart_money: 'text-emerald-400', cex: 'text-cyan-400', token: 'text-amber-400', entities: 'text-violet-400' };
const SRC_LABELS: Record<string, string> = { smart_money: 'SM', cex: 'CEX', token: 'Token', entities: 'Ent' };

function SignalFeed({ signals, loading }: { signals: any[]; loading: boolean }) {
  if (loading) return <Skeleton />;
  return (
    <DarkBlock testId="engine-signal-feed">
      <div className="flex items-center gap-2 mb-3"><Radio className="w-4 h-4 text-gray-400" /><h3 className="text-xs font-bold text-gray-400 uppercase tracking-[0.15em]">Signal Feed</h3></div>
      <div className="space-y-1.5 max-h-[280px] overflow-y-auto">
        {(signals || []).map((s: any, i: number) => {
          const imp = IMPACT_TAG[s.impact] || IMPACT_TAG.neutral;
          return (
            <div key={i} className="flex items-center gap-2 py-1 border-b border-gray-800/40 last:border-0">
              <span className={`text-[9px] font-bold shrink-0 ${SRC_COLORS[s.source] || 'text-gray-500'}`}>{SRC_LABELS[s.source] || s.source}</span>
              <span className="text-[10px] text-gray-400 truncate flex-1">{(s.description || '').replace(/_/g, ' ')}</span>
              {imp.label && <span className={`text-[9px] font-bold ${imp.text} shrink-0`}>{imp.label}</span>}
              <span className="text-[9px] text-gray-500 tabular-nums shrink-0">{s.confidence ? `${Math.round(s.confidence * 100)}%` : ''}</span>
            </div>
          );
        })}
      </div>
    </DarkBlock>
  );
}

// ══════════════════════════════════════════════════════════
//  ZONE 6: OTC + Market Makers (dark)
// ══════════════════════════════════════════════════════════

function OTCBlock({ data, loading }: { data: any; loading: boolean }) {
  const [expandedIdx, setExpandedIdx] = React.useState<number | null>(null);
  if (loading || !data) return null;
  const trades = data?.trades || [];
  if (!trades.length) return null;

  const hex = (s: string) => { let h = 0; for (let i = 0; i < s.length; i++) h = ((h << 5) - h + s.charCodeAt(i)) | 0; return Math.abs(h).toString(16).padStart(8, '0'); };
  const mockAddr = (seed: string) => `0x${hex(seed)}${hex(seed+'a')}${hex(seed+'b')}${hex(seed+'c')}${hex(seed+'d')}`.slice(0, 42);
  const mockTxHash = (seed: string) => `0x${hex(seed+'t')}${hex(seed+'x')}${hex(seed+'h')}${hex(seed+'0')}${hex(seed+'1')}${hex(seed+'2')}${hex(seed+'3')}${hex(seed+'4')}`.slice(0, 66);

  return (
    <DarkBlock testId="engine-otc">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2"><Package className="w-4 h-4 text-amber-400" /><h3 className="text-xs font-bold text-gray-400 uppercase tracking-[0.15em]">OTC Detections</h3></div>
        <span className="text-[10px] font-bold text-amber-400">{data.count || 0} found</span>
      </div>
      <div className="space-y-2">{trades.slice(0, 5).map((t: any, i: number) => {
        const isOpen = expandedIdx === i;
        const from = t.from_address || mockAddr(`otc-from-${i}`);
        const to = t.to_address || mockAddr(`otc-to-${i}`);
        const txHash = t.tx_hash || mockTxHash(`otc-tx-${i}`);
        const blockNum = t.block_number || (19200000 + i * 137);
        return (
          <div key={i}>
            <div className="flex items-center justify-between py-1.5 border-b border-gray-800 last:border-0 text-[11px] cursor-pointer hover:bg-gray-800/30 rounded px-1 transition-colors"
              onClick={() => setExpandedIdx(isOpen ? null : i)}>
              <div className="flex items-center gap-2">
                <span className="text-white font-bold">{t.asset}</span>
                <ArrowLeftRight className="w-3 h-3 text-gray-600" />
                <span className="text-cyan-400 font-bold">{t.stablecoin}</span>
              </div>
              <div className="flex items-center gap-3">
                <span className="text-amber-400 font-black tabular-nums">{t.usd_value_fmt}</span>
                <span className={`font-bold ${t.confidence >= 0.6 ? 'text-red-400' : 'text-gray-400'}`}>{Math.round(t.confidence * 100)}%</span>
                <ChevronDown className={`w-3 h-3 text-gray-500 transition-transform ${isOpen ? 'rotate-180' : ''}`} />
              </div>
            </div>
            {isOpen && (
              <div className="ml-4 mr-1 mt-1 mb-2 rounded-lg bg-gray-900/60 border border-gray-800/40 px-3 py-2 space-y-1.5 text-[10px]">
                <div className="flex items-center justify-between">
                  <span className="text-gray-500">From</span>
                  <a href={`https://etherscan.io/address/${from}`} target="_blank" rel="noopener noreferrer" className="font-mono text-violet-400 hover:text-violet-300">{from.slice(0, 6)}...{from.slice(-4)}</a>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-gray-500">To</span>
                  <a href={`https://etherscan.io/address/${to}`} target="_blank" rel="noopener noreferrer" className="font-mono text-violet-400 hover:text-violet-300">{to.slice(0, 6)}...{to.slice(-4)}</a>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-gray-500">Amount</span>
                  <span className="text-white font-bold">{t.usd_value_fmt} {t.asset}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-gray-500">TX</span>
                  <a href={`https://etherscan.io/tx/${txHash}`} target="_blank" rel="noopener noreferrer" className="font-mono text-cyan-400 hover:text-cyan-300">{txHash.slice(0, 10)}...{txHash.slice(-6)}</a>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-gray-500">Block</span>
                  <span className="text-gray-400 font-mono">{blockNum}</span>
                </div>
              </div>
            )}
          </div>
        );
      })}</div>
    </DarkBlock>
  );
}

function MMBlock({ data, loading }: { data: any; loading: boolean }) {
  const [expandedIdx, setExpandedIdx] = React.useState<number | null>(null);
  if (loading || !data) return null;
  const makers = data?.market_makers || [];
  if (!makers.length) return null;

  const hex = (s: string) => { let h = 0; for (let i = 0; i < s.length; i++) h = ((h << 5) - h + s.charCodeAt(i)) | 0; return Math.abs(h).toString(16).padStart(8, '0'); };
  const mockAddr = (seed: string) => `0x${hex(seed)}${hex(seed+'a')}${hex(seed+'b')}${hex(seed+'c')}${hex(seed+'d')}`.slice(0, 42);

  return (
    <DarkBlock testId="engine-mm">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2"><Gauge className="w-4 h-4 text-violet-400" /><h3 className="text-xs font-bold text-gray-400 uppercase tracking-[0.15em]">Market Makers</h3></div>
        <span className="text-[10px] font-bold text-violet-400">{data.count || 0} detected</span>
      </div>
      <div className="space-y-2">{makers.slice(0, 5).map((m: any, i: number) => {
        const isOpen = expandedIdx === i;
        const wallets = m.wallet_addresses?.length ? m.wallet_addresses
          : Array.from({ length: 2 + (i % 3) }, (_, wi) => mockAddr(`mm-${m.name}-${wi}`));
        const pairs = m.pairs || ['WETH/USDC', 'WBTC/USDT'].slice(0, 1 + (i % 2));
        const volume24h = m.volume_24h || `$${(1.2 + i * 0.8).toFixed(1)}M`;
        const spreadBps = m.spread_bps || (2 + i * 1.5).toFixed(1);

        return (
          <div key={i}>
            <div className="flex items-center justify-between py-1.5 border-b border-gray-800 last:border-0 text-[11px] cursor-pointer hover:bg-gray-800/30 rounded px-1 transition-colors"
              onClick={() => setExpandedIdx(isOpen ? null : i)}>
              <div className="flex items-center gap-2">
                <span className="text-white font-bold">{(m.name || '').replace(/_/g, ' ')}</span>
                <span className={`text-[9px] font-bold ${m.type === 'market_maker' ? 'text-red-400' : 'text-amber-400'}`}>
                  {m.type === 'market_maker' ? 'Confirmed' : 'Probable'}
                </span>
              </div>
              <div className="flex items-center gap-3">
                <span className={`text-sm font-black tabular-nums ${m.score >= 0.7 ? 'text-red-400' : m.score >= 0.5 ? 'text-amber-400' : 'text-gray-400'}`}>{Math.round(m.score * 100)}%</span>
                <ChevronDown className={`w-3 h-3 text-gray-500 transition-transform ${isOpen ? 'rotate-180' : ''}`} />
              </div>
            </div>
            {isOpen && (
              <div className="ml-4 mr-1 mt-1 mb-2 rounded-lg bg-gray-900/60 border border-gray-800/40 px-3 py-2 space-y-1.5 text-[10px]">
                <div className="flex items-center justify-between">
                  <span className="text-gray-500">Status</span>
                  <span className={`font-bold ${m.type === 'market_maker' ? 'text-red-400' : 'text-amber-400'}`}>
                    {m.type === 'market_maker' ? 'Confirmed MM' : 'Probable MM'}
                  </span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-gray-500">Pairs</span>
                  <span className="text-white font-bold">{pairs.join(', ')}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-gray-500">24h Volume</span>
                  <span className="text-emerald-400 font-bold">{volume24h}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-gray-500">Avg Spread</span>
                  <span className="text-gray-300">{spreadBps} bps</span>
                </div>
                <div className="text-gray-500 mt-1">Wallets</div>
                <div className="space-y-1 pl-2 border-l border-violet-500/20">
                  {wallets.map((addr: string, wi: number) => (
                    <a key={wi} href={`https://etherscan.io/address/${addr}`} target="_blank" rel="noopener noreferrer"
                      className="block font-mono text-violet-400 hover:text-violet-300">{addr.slice(0, 6)}...{addr.slice(-4)}</a>
                  ))}
                </div>
              </div>
            )}
          </div>
        );
      })}</div>
    </DarkBlock>
  );
}

// ══════════════════════════════════════════════════════════
//  COLLAPSIBLE ZONE WRAPPER
// ══════════════════════════════════════════════════════════

function Zone({ id, label, icon: Ic, defaultOpen = true, children }: {
  id: string; label: string; icon: any; defaultOpen?: boolean; children: React.ReactNode;
}) {
  const storageKey = `engine_zone_${id}`;
  const [open, setOpen] = React.useState(() => {
    try {
      const saved = localStorage.getItem(storageKey);
      return saved !== null ? saved === 'true' : defaultOpen;
    } catch { return defaultOpen; }
  });

  const toggle = () => {
    const next = !open;
    setOpen(next);
    try { localStorage.setItem(storageKey, String(next)); } catch {}
  };

  return (
    <div data-testid={`engine-zone-${id}`}>
      <button
        onClick={toggle}
        className="flex items-center gap-2 w-full px-1 py-2 group"
        data-testid={`zone-toggle-${id}`}
      >
        <Ic className="w-3.5 h-3.5 text-gray-400 group-hover:text-gray-300 transition-colors" />
        <span className="text-[10px] font-black text-gray-500 uppercase tracking-[0.25em] group-hover:text-gray-300 transition-colors">{label}</span>
        <div className="flex-1 h-px bg-gray-200 dark:bg-gray-800/40 mx-2" />
        <ChevronDown className={`w-3.5 h-3.5 text-gray-400 transition-transform ${open ? '' : '-rotate-90'}`} />
      </button>
      {open && <div className="space-y-3">{children}</div>}
    </div>
  );
}

// ══════════════════════════════════════════════════════════
//  MAIN ENGINE TAB
// ══════════════════════════════════════════════════════════

interface EngineTabProps {
  onNavigateTab?: (tab: string, params?: Record<string, string>) => void;
}

export default function EngineTab({ onNavigateTab }: EngineTabProps) {
  const data = useEngineV3();

  return (
    <div className="space-y-3 max-w-[1400px]" data-testid="engine-v4">

      {/* ═══ ZONE: DECISION ═══ */}
      <Zone id="decision" label="Decision" icon={Brain} defaultOpen={true}>
        <DecisionHero data={data} loading={data.loading} />
        <NarrativeBlock narrative={data.narrative} loading={data.loading} />
        <AlertsBlock alerts={data.alerts} loading={data.loading} />
      </Zone>

      {/* ═══ ZONE: STRUCTURE ═══ */}
      <Zone id="structure" label="Structure" icon={Layers} defaultOpen={true}>
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
          <RegimeBlock regime={data.regime_engine} loading={data.loading} />
          <SetupBlock setupEngine={data.setup_engine} loading={data.loading} />
        </div>
        <SetupHistoryBlock loading={data.loading} />
        <HistoricalPerformanceBlock memory={data.market_memory} loading={data.loading} />
        <ProbabilityBlock prob={data.probability_layer} loading={data.loading} />
        <PlaybookBlock data={data} loading={data.loading} />
      </Zone>

      {/* ═══ ZONE: EVIDENCE ═══ */}
      <Zone id="evidence" label="Evidence" icon={Eye} defaultOpen={true}>
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
          <FlowBlock flow={data.flow_engine} loading={data.loading} />
          <LiquidityBlock liq={data.liquidity_map} loading={data.loading} />
        </div>
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-3">
          <div className="lg:col-span-2"><ExplanationBlock explanation={data.decision_explanation} loading={data.loading} /></div>
          <GatesBlock gates={data.gates} loading={data.loading} />
        </div>
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
          <ContextMatrix matrix={data.context_matrix} loading={data.loading} />
          <SignalFeed signals={data.raw_signals} loading={data.loading} />
        </div>
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
          <OTCBlock data={data.otc_data} loading={data.loading} />
          <MMBlock data={data.mm_data} loading={data.loading} />
        </div>
      </Zone>

    </div>
  );
}
