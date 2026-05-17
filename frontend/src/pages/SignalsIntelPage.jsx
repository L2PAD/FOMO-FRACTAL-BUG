/**
 * Signal Intelligence Layer — VFinal
 *
 * 3-level hierarchy:
 *   L1: Execution Signal (top card) + Core Alignment
 *   L2: Structural Contributors (Exchange, AccDist, OnChain)
 *   L3: Event Feed — grouped by source (Macro Constraints / Structural Events)
 *   Sidebar: Signal Stats
 *
 * No header (embedded in Exchange tabs). Light theme.
 */

import { useState, useEffect, useCallback } from 'react';
import { RefreshCw, Loader2, TrendingUp, TrendingDown, Minus, Activity, ArrowUpRight, BarChart3, Clock, Zap, AlertTriangle, ShieldAlert, Link2, Unlink2 } from 'lucide-react';

const API = process.env.REACT_APP_BACKEND_URL;

const BIAS_CONFIG = {
  bullish_pressure: { color: '#16a34a', bg: 'rgba(22,163,74,0.06)', label: 'BULLISH PRESSURE', icon: TrendingUp },
  bearish_pressure: { color: '#dc2626', bg: 'rgba(220,38,38,0.06)', label: 'BEARISH PRESSURE', icon: TrendingDown },
  balanced:         { color: '#64748b', bg: 'rgba(100,116,139,0.06)', label: 'BALANCED', icon: Minus },
};

const DIR_CONFIG = {
  bullish: { color: '#16a34a', bg: 'rgba(22,163,74,0.06)' },
  bearish: { color: '#dc2626', bg: 'rgba(220,38,38,0.06)' },
  neutral: { color: '#64748b', bg: 'rgba(100,116,139,0.06)' },
};

const ALIGNMENT_CONFIG = {
  ALIGNED:   { color: '#16a34a', bg: 'rgba(22,163,74,0.06)', icon: Link2, label: 'Aligned' },
  MIXED:     { color: '#d97706', bg: 'rgba(217,119,6,0.06)', icon: Minus, label: 'Mixed' },
  DIVERGING: { color: '#dc2626', bg: 'rgba(220,38,38,0.06)', icon: Unlink2, label: 'Diverging' },
};

const EVENT_ICONS = {
  EXTREME_FEAR: AlertTriangle, EXTREME_GREED: TrendingUp,
  RISKOFF_SPIKE: ShieldAlert, ACTIONS_BLOCKED: ShieldAlert,
  CAPITAL_EXIT_REGIME: TrendingDown, REGIME_INSTABILITY: Activity,
  HIGH_RISK: AlertTriangle, BTC_DOMINANCE_SHIFT: BarChart3,
};

/* ═══════════ Shared ═══════════ */

function SL({ children }) {
  return <div className="text-[11px] uppercase tracking-wider font-semibold mb-3" style={{ color: '#94a3b8' }}>{children}</div>;
}

function ScoreBar({ score, maxAbs = 1 }) {
  const pct = Math.min(Math.abs(score) / maxAbs * 100, 100);
  const isPos = score >= 0;
  return (
    <div className="h-1.5 w-full rounded-full overflow-hidden relative" style={{ background: '#e2e8f0' }}>
      <div className="absolute top-0 h-full rounded-full transition-all duration-500"
        style={{
          width: `${pct / 2}%`,
          left: isPos ? '50%' : `${50 - pct / 2}%`,
          background: isPos ? '#16a34a' : '#dc2626',
        }} />
      <div className="absolute top-0 left-1/2 w-px h-full" style={{ background: '#cbd5e1' }} />
    </div>
  );
}

function Tip({ text, children }) {
  const [show, setShow] = useState(false);
  if (!text) return children;
  return (
    <span className="relative inline-flex" onMouseEnter={() => setShow(true)} onMouseLeave={() => setShow(false)}>
      {children}
      {show && (
        <span className="absolute z-50 left-0 top-full mt-1.5 w-56 px-3 py-2 rounded-lg pointer-events-none text-[11px]"
          style={{ background: '#0f172a', color: '#e2e8f0', boxShadow: '0 8px 24px rgba(0,0,0,0.25)' }}>
          {text}
        </span>
      )}
    </span>
  );
}

/* ═══════════ L1: Execution Card ═══════════ */

function ExecutionCard({ execution, coreAlignment }) {
  if (!execution) return null;
  const cfg = BIAS_CONFIG[execution.bias] || BIAS_CONFIG.balanced;
  const Icon = cfg.icon;
  const align = ALIGNMENT_CONFIG[coreAlignment?.status] || ALIGNMENT_CONFIG.MIXED;
  const AlignIcon = align.icon;

  return (
    <div className="rounded-2xl p-5" data-testid="execution-card"
      style={{ background: '#fff', border: '1px solid #e2e8f0' }}>
      <div className="flex items-start justify-between mb-4">
        <div>
          <SL>Execution Signal</SL>
          <div className="flex items-center gap-2.5 flex-wrap">
            <span className="px-3 py-1.5 rounded-lg text-xs font-bold inline-flex items-center gap-1.5"
              style={{ background: cfg.bg, color: cfg.color }}>
              <Icon className="w-3.5 h-3.5" />
              {cfg.label}
            </span>
            <span className="text-[10px] uppercase tracking-wider font-semibold px-2 py-1 rounded-md"
              style={{ background: '#f1f5f9', color: '#94a3b8' }}>
              {execution.executionMode?.replace(/_/g, ' ')}
            </span>
            {/* Core Alignment chip */}
            <Tip text={coreAlignment?.detail || ''}>
              <span className="px-2 py-1 rounded-md text-[10px] font-bold inline-flex items-center gap-1"
                data-testid="core-alignment"
                style={{ background: align.bg, color: align.color }}>
                <AlignIcon className="w-3 h-3" />
                Core: {align.label}
              </span>
            </Tip>
          </div>
        </div>
        <div className="text-right">
          <div className="text-[32px] font-bold tabular-nums leading-none" style={{ color: cfg.color }}>
            {execution.score > 0 ? '+' : ''}{execution.score.toFixed(2)}
          </div>
          <div className="text-[11px] font-medium mt-1" style={{ color: '#94a3b8' }}>
            Strength: {(execution.strength * 100).toFixed(0)}%
          </div>
        </div>
      </div>

      <ScoreBar score={execution.score} />

      <p className="text-[13px] mt-3.5 mb-4 leading-relaxed" data-testid="execution-narrative"
        style={{ color: '#64748b', fontStyle: 'italic' }}>
        {execution.narrative}
      </p>

      {/* Contributors — only values, weights in tooltip */}
      <div className="rounded-xl p-4" style={{ background: '#f8fafc', border: '1px solid #e2e8f0' }}>
        <SL>Contributors</SL>
        {[
          { name: 'Exchange', key: 'exchange', w: 45 },
          { name: 'Acc/Dist', key: 'accDist', w: 35 },
          { name: 'On-chain', key: 'onchain', w: 20 },
        ].map(({ name, key, w }) => {
          const val = execution.contributors[key] || 0;
          const color = val > 0.001 ? '#16a34a' : val < -0.001 ? '#dc2626' : '#64748b';
          return (
            <div key={key} className="flex items-center justify-between py-1.5" data-testid={`contributor-${key}`}>
              <Tip text={`Aggregation weight: ${w}%`}>
                <span className="text-[13px] font-medium cursor-default" style={{ color: '#0f172a' }}>{name}</span>
              </Tip>
              <span className="text-[13px] font-semibold tabular-nums" style={{ color }}>
                {val > 0 ? '+' : ''}{val.toFixed(4)}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

/* ═══════════ L2: Structural Block ═══════════ */

function StructuralBlock({ title, icon: IconComp, data, executionContribution }) {
  if (!data) return null;
  const dir = DIR_CONFIG[data.direction] || DIR_CONFIG.neutral;

  return (
    <div className="rounded-2xl p-5 h-full flex flex-col" data-testid={`structural-${title.toLowerCase().replace(/[\s/]+/g, '-')}`}
      style={{ background: '#fff', border: '1px solid #e2e8f0' }}>
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <div className="p-1.5 rounded-lg" style={{ background: '#f1f5f9' }}>
            <IconComp className="w-4 h-4" style={{ color: '#64748b' }} />
          </div>
          <span className="text-[13px] font-semibold" style={{ color: '#0f172a' }}>{title}</span>
        </div>
        <span className="px-2 py-0.5 rounded-md text-[10px] font-bold uppercase"
          style={{ background: dir.bg, color: dir.color }}>
          {data.direction}
        </span>
      </div>

      <div className="flex items-baseline justify-between mb-2.5">
        <span className="text-[22px] font-bold tabular-nums" style={{ color: dir.color }}>
          {data.score > 0 ? '+' : ''}{data.score.toFixed(2)}
        </span>
        <div className="text-right">
          <div className="text-[10px] font-medium" style={{ color: '#94a3b8' }}>
            Str: {(data.strength * 100).toFixed(0)}%
          </div>
          <div className="text-[10px] font-medium" style={{ color: '#94a3b8' }}>
            Conf: {(data.confidence * 100).toFixed(0)}%
          </div>
        </div>
      </div>

      <ScoreBar score={data.score} />

      <div className="mt-auto pt-3 border-t" style={{ borderColor: '#f1f5f9' }}>
        <div className="flex items-center justify-between">
          <span className="text-[11px] font-medium" style={{ color: '#94a3b8' }}>Contribution to execution</span>
          <span className="text-[13px] font-semibold tabular-nums"
            style={{ color: executionContribution > 0.001 ? '#16a34a' : executionContribution < -0.001 ? '#dc2626' : '#64748b' }}>
            {executionContribution > 0 ? '+' : ''}{executionContribution.toFixed(4)}
          </span>
        </div>
      </div>
    </div>
  );
}

/* ═══════════ L3: Event Card ═══════════ */

function EventCard({ event }) {
  const Icon = EVENT_ICONS[event.type] || Zap;
  const dir = DIR_CONFIG[event.direction] || DIR_CONFIG.neutral;

  return (
    <div className="rounded-xl p-4 flex items-start gap-3" data-testid={`event-${event.type}`}
      style={{ background: dir.bg, borderLeft: `3px solid ${dir.color}` }}>
      <div className="p-1.5 rounded-lg flex-shrink-0" style={{ background: `${dir.color}10` }}>
        <Icon className="w-4 h-4" style={{ color: dir.color }} />
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center justify-between gap-2 mb-1">
          <span className="text-[13px] font-semibold" style={{ color: '#0f172a' }}>
            {event.type.replace(/_/g, ' ')}
          </span>
          <span className="text-[13px] font-semibold tabular-nums" style={{ color: dir.color }}>
            {event.impactOnExecution > 0 ? '+' : ''}{event.impactOnExecution.toFixed(2)}
          </span>
        </div>
        <p className="text-[12px] mb-2" style={{ color: '#64748b' }}>{event.description}</p>
        <div className="flex items-center gap-3">
          <span className="text-[10px] font-medium flex items-center gap-1" style={{ color: '#94a3b8' }}>
            <Clock className="w-3 h-3" /> {event.ttl}
          </span>
          <span className="text-[10px] font-medium" style={{ color: '#94a3b8' }}>
            Conf: {(event.confidence * 100).toFixed(0)}%
          </span>
          <span className="text-[10px] font-medium" style={{ color: '#94a3b8' }}>
            Str: {(event.strength * 100).toFixed(0)}%
          </span>
        </div>
      </div>
    </div>
  );
}

function EventFeed({ events }) {
  if (!events || events.length === 0) {
    return (
      <div className="rounded-xl p-6 text-center" style={{ background: '#f8fafc', border: '1px dashed #e2e8f0' }}>
        <Activity className="w-5 h-5 mx-auto mb-2" style={{ color: '#cbd5e1' }} />
        <p className="text-[13px] font-medium" style={{ color: '#94a3b8' }}>No significant structural triggers (24h)</p>
        <p className="text-[11px] mt-1" style={{ color: '#cbd5e1' }}>Market structurally balanced</p>
      </div>
    );
  }

  const macroEvents = events.filter(e => e.source === 'macro');
  const structuralEvents = events.filter(e => e.source === 'structural');
  const otherEvents = events.filter(e => e.source !== 'macro' && e.source !== 'structural');

  return (
    <div className="space-y-4">
      {macroEvents.length > 0 && (
        <div>
          <div className="text-[10px] uppercase tracking-wider font-semibold mb-2 flex items-center gap-1.5"
            style={{ color: '#d97706' }}>
            <ShieldAlert className="w-3 h-3" /> Macro Constraints
          </div>
          <div className="space-y-2.5">
            {macroEvents.map((ev, i) => <EventCard key={`m-${i}`} event={ev} />)}
          </div>
        </div>
      )}
      {structuralEvents.length > 0 && (
        <div>
          <div className="text-[10px] uppercase tracking-wider font-semibold mb-2 flex items-center gap-1.5"
            style={{ color: '#6366f1' }}>
            <Activity className="w-3 h-3" /> Structural Events
          </div>
          <div className="space-y-2.5">
            {structuralEvents.map((ev, i) => <EventCard key={`s-${i}`} event={ev} />)}
          </div>
        </div>
      )}
      {otherEvents.length > 0 && (
        <div className="space-y-2.5">
          {otherEvents.map((ev, i) => <EventCard key={`o-${i}`} event={ev} />)}
        </div>
      )}
    </div>
  );
}

/* ═══════════ Stats Sidebar ═══════════ */

function StatsPanel({ stats, structural }) {
  if (!stats) return null;

  const items = [
    { label: 'Execution Score', value: stats.executionScore?.toFixed(2), color: stats.executionScore > 0.1 ? '#16a34a' : stats.executionScore < -0.1 ? '#dc2626' : '#64748b' },
    { label: 'Execution Bias', value: stats.executionBias?.replace('_', ' ').toUpperCase() },
    { label: 'Execution Mode', value: stats.executionMode?.replace(/_/g, ' ') },
    { label: 'Structural Strength', value: `${(stats.structuralStrength * 100).toFixed(0)}%` },
    { label: 'Active Events', value: stats.activeEvents, color: stats.activeEvents > 0 ? '#d97706' : '#94a3b8' },
    { label: 'Bearish Events', value: stats.bearishEvents, color: stats.bearishEvents > 0 ? '#dc2626' : '#94a3b8' },
    { label: 'Bullish Events', value: stats.bullishEvents, color: stats.bullishEvents > 0 ? '#16a34a' : '#94a3b8' },
  ];

  return (
    <div className="rounded-2xl p-5" data-testid="signal-stats"
      style={{ background: '#fff', border: '1px solid #e2e8f0' }}>
      <SL>Signal Stats</SL>
      <div className="space-y-3">
        {items.map((it) => (
          <div key={it.label} className="flex items-center justify-between">
            <span className="text-[12px] font-medium" style={{ color: '#64748b' }}>{it.label}</span>
            <span className="text-[13px] font-semibold tabular-nums"
              style={{ color: it.color || '#0f172a' }}>
              {it.value}
            </span>
          </div>
        ))}
      </div>

      <div className="mt-5 pt-4" style={{ borderTop: '1px solid #e2e8f0' }}>
        <SL>Aggregation Weights</SL>
        <div className="space-y-2">
          {[
            { name: 'Exchange', w: 45, score: structural?.exchange?.score },
            { name: 'Acc/Dist', w: 35, score: structural?.accDist?.score },
            { name: 'On-chain', w: 20, score: structural?.onchain?.score },
          ].map(({ name, w, score }) => (
            <div key={name} className="flex items-center gap-2">
              <span className="text-[11px] font-medium w-14" style={{ color: '#64748b' }}>{name}</span>
              <div className="flex-1 h-1.5 rounded-full overflow-hidden" style={{ background: '#e2e8f0' }}>
                <div className="h-full rounded-full" style={{ width: `${w}%`, background: '#cbd5e1' }} />
              </div>
              <span className="text-[10px] font-medium w-7 text-right" style={{ color: '#94a3b8' }}>{w}%</span>
              <span className="text-[11px] font-semibold tabular-nums w-12 text-right"
                style={{ color: (score || 0) > 0.01 ? '#16a34a' : (score || 0) < -0.01 ? '#dc2626' : '#94a3b8' }}>
                {score != null ? (score > 0 ? '+' : '') + score.toFixed(2) : '--'}
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

/* ═══════════ Main Page ═══════════ */

export default function SignalsIntelPage() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [refreshing, setRefreshing] = useState(false);

  const fetchData = useCallback(async (showRefresh = false) => {
    if (showRefresh) setRefreshing(true);
    else setLoading(true);

    try {
      const res = await fetch(`${API}/api/signals/vfinal?asset=BTCUSDT&tf=1h`);
      const json = await res.json();
      if (json.ok) {
        setData(json);
        setError(null);
      } else {
        setError(json.error || 'Failed to load signals');
      }
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
    const iv = setInterval(() => fetchData(true), 60000);
    return () => clearInterval(iv);
  }, [fetchData]);

  if (loading && !data) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="w-6 h-6 animate-spin" style={{ color: '#94a3b8' }} />
      </div>
    );
  }

  if (error && !data) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-center">
          <AlertTriangle className="w-8 h-8 mx-auto mb-2" style={{ color: '#dc2626' }} />
          <p className="text-sm" style={{ color: '#64748b' }}>{error}</p>
          <button onClick={() => fetchData()} className="mt-3 text-xs hover:underline" style={{ color: '#94a3b8' }}>Retry</button>
        </div>
      </div>
    );
  }

  const { execution, structural, events, coreAlignment, stats } = data || {};

  return (
    <div data-testid="signals-intel-page">
      {/* Refresh button — top-right, compact */}
      <div className="flex justify-end px-6 pt-3 pb-1">
        <button
          onClick={() => fetchData(true)}
          disabled={refreshing}
          data-testid="signals-refresh-btn"
          className="p-1.5 rounded-lg transition-colors disabled:opacity-30"
          style={{ background: refreshing ? '#f1f5f9' : 'transparent' }}
          onMouseEnter={e => e.currentTarget.style.background = '#f1f5f9'}
          onMouseLeave={e => { if (!refreshing) e.currentTarget.style.background = 'transparent'; }}
        >
          <RefreshCw className={`w-4 h-4 ${refreshing ? 'animate-spin' : ''}`} style={{ color: '#94a3b8' }} />
        </button>
      </div>

      {/* Main Grid */}
      <div className="px-6 pb-6 grid grid-cols-1 lg:grid-cols-[1fr_280px] gap-5">
        <div className="space-y-5">
          <ExecutionCard execution={execution} coreAlignment={coreAlignment} />

          <div>
            <SL>Structural Components</SL>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <StructuralBlock title="Exchange Pressure" icon={ArrowUpRight} data={structural?.exchange} executionContribution={execution?.contributors?.exchange || 0} />
              <StructuralBlock title="Accumulation / Distribution" icon={BarChart3} data={structural?.accDist} executionContribution={execution?.contributors?.accDist || 0} />
              <StructuralBlock title="On-chain Activity" icon={Activity} data={structural?.onchain} executionContribution={execution?.contributors?.onchain || 0} />
            </div>
          </div>

          <div>
            <SL>Event Feed</SL>
            <EventFeed events={events} />
          </div>
        </div>

        <div className="space-y-5">
          <StatsPanel stats={stats} structural={structural} />
        </div>
      </div>
    </div>
  );
}
