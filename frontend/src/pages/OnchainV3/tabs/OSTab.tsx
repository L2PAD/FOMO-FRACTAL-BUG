/**
 * Market Intelligence OS — Control Room
 * =======================================
 * State-driven market awareness page. Zero charts.
 * 6 blocks: Market State, Top Opportunity, Market Pressure,
 *           Actor Activity, Liquidity Targets, Alerts Feed.
 * 
 * Reads ONLY from snapshot data — never runs calculations.
 */

import React, { useState, useEffect, useCallback } from 'react';
import {
  Brain, Target, Users, Activity, Zap, Layers,
  TrendingUp, TrendingDown, ShieldAlert, AlertTriangle,
  Package, BarChart3, ArrowRight, RefreshCw, Loader2,
  Radio, Building, Eye, Crosshair, Info, Clock,
  ArrowUpRight, ArrowDownRight, Minus,
} from 'lucide-react';

const API = process.env.REACT_APP_BACKEND_URL;

// ── Dark block wrapper ──
function Block({ children, testId, dark = true }: { children: React.ReactNode; testId: string; dark?: boolean }) {
  return (
    <div
      className={`rounded-xl p-5 ${dark ? 'bg-[#0a0e14] intelligence-dark border border-gray-800/40' : 'bg-white border border-gray-200/60'}`}
      data-testid={testId}
    >
      {children}
    </div>
  );
}

// ── Severity colors for alerts ──
const SEV_COLORS: Record<string, string> = {
  CRITICAL: 'text-red-400',
  IMPORTANT: 'text-amber-400',
  WATCH: 'text-cyan-400',
  INFO: 'text-gray-400',
};

const SEV_DOTS: Record<string, string> = {
  CRITICAL: 'bg-red-400',
  IMPORTANT: 'bg-amber-400',
  WATCH: 'bg-cyan-400',
  INFO: 'bg-gray-400',
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

// ── Decision colors ──
const DEC_COLORS: Record<string, { text: string; bg: string }> = {
  BUY: { text: 'text-emerald-400', bg: 'bg-emerald-500/10' },
  SELL: { text: 'text-red-400', bg: 'bg-red-500/10' },
  NEUTRAL: { text: 'text-gray-400', bg: 'bg-gray-500/10' },
};

// ── Flow state labels ──
const FLOW_LABELS: Record<string, { text: string; color: string }> = {
  bullish_acceleration: { text: 'Bullish Acceleration', color: 'text-emerald-400' },
  bearish_acceleration: { text: 'Bearish Acceleration', color: 'text-red-400' },
  liquidity_expansion: { text: 'Liquidity Expansion', color: 'text-cyan-400' },
  flow_exhaustion: { text: 'Flow Exhaustion', color: 'text-amber-400' },
  neutral: { text: 'Neutral', color: 'text-gray-400' },
};

// ── Action colors for actors ──
const ACTION_COLORS: Record<string, string> = {
  accumulating: 'text-emerald-400',
  distributing: 'text-red-400',
  neutral: 'text-gray-400',
  'outflows (bullish)': 'text-emerald-400',
  'inflows (bearish)': 'text-red-400',
  'neutral flows': 'text-gray-400',
  'bullish structure': 'text-emerald-400',
  'bearish structure': 'text-red-400',
};

// ── Relative time helper ──
function _relTime(ts: string): string {
  const d = new Date(ts);
  const diff = Math.floor((Date.now() - d.getTime()) / 1000);
  if (diff < 60) return `${diff}s ago`;
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  return `${Math.floor(diff / 86400)}d ago`;
}

// ══════════════════════════════════════════════════════════
//  BLOCK 0: Market Control Panel (compact 1-line strip)
// ══════════════════════════════════════════════════════════

const CP_RISK_COLORS: Record<string, string> = { LOW: 'text-emerald-400', MODERATE: 'text-amber-400', ELEVATED: 'text-orange-400', HIGH: 'text-red-400' };
const PULSE_COLORS: Record<string, { text: string; dot: string }> = {
  LOW: { text: 'text-gray-400', dot: 'bg-gray-400' },
  NORMAL: { text: 'text-emerald-400', dot: 'bg-emerald-400' },
  HIGH: { text: 'text-amber-400', dot: 'bg-amber-400' },
  EXTREME: { text: 'text-red-400', dot: 'bg-red-400' },
};

function ControlPanelBlock({ state, risk, pulse }: { state: any; risk: any; pulse: any }) {
  if (!state || !state.regime) return null;
  const riskColor = CP_RISK_COLORS[risk?.risk_level] || 'text-gray-400';
  const flow = FLOW_LABELS[state.flow_state] || FLOW_LABELS.neutral;
  const pc = PULSE_COLORS[pulse?.pulse] || PULSE_COLORS.LOW;

  return (
    <div className="bg-[#060a0f] rounded-xl px-5 py-3 border border-gray-800/50" data-testid="os-control-panel">
      <div className="flex items-center justify-between gap-6">
        <div className="flex items-center gap-1.5">
          <Radio className="w-3 h-3 text-cyan-500" />
          <span className="text-[9px] font-bold text-gray-600 uppercase tracking-[0.2em]">Control Panel</span>
        </div>

        <div className="flex items-center gap-6 flex-1 justify-end">
          {/* Regime */}
          <div className="flex items-center gap-2">
            <span className="text-[9px] text-gray-600 uppercase">Regime</span>
            <span className="text-xs font-bold text-white">{state.regime.replace(/_/g, ' ').replace(/\b\w/g, (c: string) => c.toUpperCase())}</span>
          </div>
          {/* Risk */}
          <div className="flex items-center gap-2">
            <span className="text-[9px] text-gray-600 uppercase">Risk</span>
            <span className={`text-xs font-bold ${riskColor}`}>{risk?.risk_score ?? '—'}</span>
          </div>
          {/* Setup */}
          <div className="flex items-center gap-2">
            <span className="text-[9px] text-gray-600 uppercase">Setup</span>
            <span className="text-xs font-bold text-white">{state.setup.replace(/_/g, ' ').replace(/\b\w/g, (c: string) => c.toUpperCase())}</span>
          </div>
          {/* Flow */}
          <div className="flex items-center gap-2">
            <span className="text-[9px] text-gray-600 uppercase">Flow</span>
            <span className={`text-xs font-bold ${flow.color}`}>{flow.text}</span>
          </div>
          {/* Decision */}
          <div className="flex items-center gap-2">
            <span className="text-[9px] text-gray-600 uppercase">Decision</span>
            <span className={`text-xs font-black ${(DEC_COLORS[state.decision] || DEC_COLORS.NEUTRAL).text}`}>{state.decision}</span>
          </div>
          {/* Pulse */}
          {pulse && (
            <div className="flex items-center gap-2">
              <span className="text-[9px] text-gray-600 uppercase">Pulse</span>
              <div className={`w-1.5 h-1.5 rounded-full ${pc.dot} ${pulse.pulse === 'EXTREME' || pulse.pulse === 'HIGH' ? 'animate-pulse' : ''}`} />
              <span className={`text-xs font-black ${pc.text}`} data-testid="os-pulse-level">{pulse.pulse}</span>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// ══════════════════════════════════════════════════════════
//  BLOCK 1: Market State
// ══════════════════════════════════════════════════════════

function MarketStateBlock({ state }: { state: any }) {
  if (!state || !state.regime) return null;
  const dc = DEC_COLORS[state.decision] || DEC_COLORS.NEUTRAL;
  const flow = FLOW_LABELS[state.flow_state] || FLOW_LABELS.neutral;

  return (
    <Block testId="os-market-state" dark>
      <div className="flex items-center gap-2 mb-4">
        <Brain className="w-4 h-4 text-gray-400" />
        <span className="text-[10px] font-bold text-gray-500 uppercase tracking-[0.2em]">Market State</span>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-4">
        {/* Regime */}
        <div>
          <p className="text-[9px] text-gray-600 uppercase mb-1">Regime</p>
          <p className="text-sm font-bold text-white">{state.regime.replace(/_/g, ' ').replace(/\b\w/g, (c: string) => c.toUpperCase())}</p>
          <p className="text-[10px] text-gray-500">{state.regime_status} / {Math.round((state.regime_confidence || 0) * 100)}%</p>
        </div>
        {/* Setup */}
        <div>
          <p className="text-[9px] text-gray-600 uppercase mb-1">Setup</p>
          <p className="text-sm font-bold text-white">{state.setup.replace(/_/g, ' ').replace(/\b\w/g, (c: string) => c.toUpperCase())}</p>
          <p className="text-[10px] text-gray-500">{state.setup_status} / {Math.round((state.setup_confidence || 0) * 100)}%</p>
        </div>
        {/* Flow */}
        <div>
          <p className="text-[9px] text-gray-600 uppercase mb-1">Flow</p>
          <p className={`text-sm font-bold ${flow.color}`}>{flow.text}</p>
          <p className="text-[10px] text-gray-500">Strength: {Math.round((state.flow_strength || 0) * 100)}%</p>
        </div>
        {/* Decision */}
        <div>
          <p className="text-[9px] text-gray-600 uppercase mb-1">Decision</p>
          <div className="flex items-center gap-2">
            <span className={`text-sm font-black ${dc.text}`}>{state.decision}</span>
            <span className={`text-[9px] px-1.5 py-0.5 rounded ${dc.bg} ${dc.text} font-bold`}>{state.confidence_level}</span>
          </div>
          <p className="text-[10px] text-gray-500">Score: {state.confidence_score} / Composite: {state.composite}</p>
        </div>
        {/* Probability */}
        <div>
          <p className="text-[9px] text-gray-600 uppercase mb-1">Probability</p>
          <div className="flex items-center gap-3">
            <span className="text-sm font-bold text-emerald-400">{Math.round((state.probability_continuation || 0) * 100)}%</span>
            <span className="text-[10px] text-gray-600">cont</span>
            <span className="text-sm font-bold text-red-400">{Math.round((state.probability_failure || 0) * 100)}%</span>
            <span className="text-[10px] text-gray-600">fail</span>
          </div>
        </div>
      </div>
    </Block>
  );
}

// ══════════════════════════════════════════════════════════
//  BLOCK 1.5: Market Risk
// ══════════════════════════════════════════════════════════

const RISK_COLORS: Record<string, { text: string; bg: string; bar: string }> = {
  LOW: { text: 'text-emerald-400', bg: 'bg-emerald-500/10', bar: 'bg-emerald-400' },
  MODERATE: { text: 'text-amber-400', bg: 'bg-amber-500/10', bar: 'bg-amber-400' },
  ELEVATED: { text: 'text-orange-400', bg: 'bg-orange-500/10', bar: 'bg-orange-400' },
  HIGH: { text: 'text-red-400', bg: 'bg-red-500/10', bar: 'bg-red-400' },
};

function RiskBlock({ risk }: { risk: any }) {
  if (!risk || risk.risk_score == null) return null;
  const rc = RISK_COLORS[risk.risk_level] || RISK_COLORS.MODERATE;

  return (
    <Block testId="os-risk" dark>
      <div className="flex items-center gap-2 mb-3">
        <ShieldAlert className="w-4 h-4 text-gray-400" />
        <span className="text-[10px] font-bold text-gray-500 uppercase tracking-[0.2em]">Market Risk</span>
      </div>

      <div className="flex items-center gap-6 mb-4">
        {/* Risk Score */}
        <div>
          <div className="flex items-baseline gap-2">
            <span className={`text-3xl font-black tabular-nums ${rc.text}`}>{risk.risk_score}</span>
            <span className="text-xs text-gray-600">/ 100</span>
          </div>
          <span className={`text-[10px] font-bold px-2 py-0.5 rounded ${rc.bg} ${rc.text}`}>{risk.risk_level}</span>
        </div>

        {/* Risk bar */}
        <div className="flex-1">
          <div className="h-2 bg-gray-800 rounded-full overflow-hidden">
            <div className={`h-full rounded-full ${rc.bar} transition-all`} style={{ width: `${risk.risk_score}%` }} />
          </div>
          {/* Component breakdown */}
          {risk.components && (
            <div className="flex items-center gap-3 mt-2">
              {Object.entries(risk.components).map(([key, val]: [string, any]) => (
                <span key={key} className="text-[9px] text-gray-600 tabular-nums">
                  {key.replace(/_/g, ' ')}: <span className="text-gray-400">{val}</span>
                </span>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Drivers */}
      {risk.drivers?.length > 0 && (
        <div className="space-y-1">
          {risk.drivers.map((d: string, i: number) => (
            <div key={i} className="flex items-center gap-2 py-1">
              <AlertTriangle className="w-3 h-3 text-amber-500 shrink-0" />
              <span className="text-[11px] text-gray-400">{d}</span>
            </div>
          ))}
        </div>
      )}

      {/* Invalidation */}
      {risk.invalidation?.length > 0 && (
        <div className="mt-3 pt-3 border-t border-gray-800/40">
          <p className="text-[9px] text-gray-600 uppercase mb-1">Invalidation Conditions</p>
          {risk.invalidation.map((inv: string, i: number) => (
            <p key={i} className="text-[10px] text-red-400/80">{inv}</p>
          ))}
        </div>
      )}
    </Block>
  );
}

// ══════════════════════════════════════════════════════════
//  BLOCK 2: Opportunities (ranked list)
// ══════════════════════════════════════════════════════════

const OPP_RISK_COLORS: Record<string, string> = { LOW: 'text-emerald-400', MODERATE: 'text-amber-400', ELEVATED: 'text-orange-400', HIGH: 'text-red-400' };
const OPP_STATUS_COLORS: Record<string, { text: string; bg: string }> = {
  confirmed: { text: 'text-emerald-400', bg: 'bg-emerald-500/10' },
  active: { text: 'text-cyan-400', bg: 'bg-cyan-500/10' },
  forming: { text: 'text-amber-400', bg: 'bg-amber-500/10' },
  weakening: { text: 'text-orange-400', bg: 'bg-orange-500/10' },
  weak: { text: 'text-gray-400', bg: 'bg-gray-500/10' },
};

function OpportunitiesBlock({ opportunities }: { opportunities: any[] }) {
  if (!opportunities || opportunities.length === 0) return null;

  return (
    <Block testId="os-opportunities" dark>
      <div className="flex items-center gap-2 mb-3">
        <Target className="w-4 h-4 text-cyan-400" />
        <span className="text-[10px] font-bold text-gray-500 uppercase tracking-[0.2em]">Top Opportunities</span>
        <span className="text-[10px] font-bold text-gray-600 ml-auto">{opportunities.length}</span>
      </div>

      <div className="space-y-2">
        {opportunities.map((opp, i) => {
          const riskColor = OPP_RISK_COLORS[opp.risk_level] || 'text-gray-400';
          const sc = OPP_STATUS_COLORS[opp.status] || OPP_STATUS_COLORS.weak;
          return (
            <div key={i} className="flex items-center gap-4 px-3 py-2.5 rounded-lg bg-white/[0.03] border border-gray-800/20" data-testid={`opportunity-${i}`}>
              {/* Rank */}
              <span className="text-lg font-black text-gray-700 tabular-nums w-6 text-center">{i + 1}</span>
              {/* Setup info */}
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-bold text-white">{opp.setup.replace(/_/g, ' ').replace(/\b\w/g, (c: string) => c.toUpperCase())}</span>
                  <span className="text-[9px] font-bold text-gray-500">— {opp.asset}</span>
                  <span className={`text-[8px] font-black uppercase px-1.5 py-0.5 rounded ${sc.bg} ${sc.text}`} data-testid={`opp-status-${i}`}>{opp.status}</span>
                </div>
                {opp.chains?.length > 0 && (
                  <div className="flex items-center gap-1 mt-0.5">
                    {opp.chains.slice(0, 4).map((ch: string) => (
                      <span key={ch} className="text-[8px] font-bold text-gray-600 bg-gray-800/50 px-1.5 py-0.5 rounded">{ch}</span>
                    ))}
                  </div>
                )}
                {!opp.chains?.length && opp.supports?.length > 0 && (
                  <p className="text-[10px] text-gray-600 truncate mt-0.5">{opp.supports[0]}</p>
                )}
              </div>
              {/* Metrics */}
              <div className="flex items-center gap-4 shrink-0">
                <div className="text-right">
                  <p className="text-[9px] text-gray-600">probability</p>
                  <p className="text-sm font-bold text-emerald-400 tabular-nums">{Math.round(opp.probability * 100)}%</p>
                </div>
                <div className="text-right">
                  <p className="text-[9px] text-gray-600">confidence</p>
                  <p className="text-sm font-bold text-gray-300 tabular-nums">{Math.round(opp.confidence * 100)}%</p>
                </div>
                <div className="text-right">
                  <p className="text-[9px] text-gray-600">risk</p>
                  <p className={`text-[10px] font-bold ${riskColor}`}>{opp.risk_level}</p>
                </div>
                {opp.expected_move && (
                  <div className="text-right">
                    <p className="text-[9px] text-gray-600">move</p>
                    <p className="text-[10px] font-bold text-cyan-400">{opp.expected_move}</p>
                  </div>
                )}
                {opp.timeframe && (
                  <div className="text-right">
                    <p className="text-[9px] text-gray-600">time</p>
                    <p className="text-[10px] font-bold text-gray-400">{opp.timeframe}</p>
                  </div>
                )}
                {opp.liquidity_alignment != null && (
                  <div className="text-right">
                    <p className="text-[9px] text-gray-600">liq.align</p>
                    <p className={`text-[10px] font-bold tabular-nums ${opp.liquidity_alignment >= 0.6 ? 'text-emerald-400' : opp.liquidity_alignment >= 0.4 ? 'text-amber-400' : 'text-gray-500'}`}>{Math.round(opp.liquidity_alignment * 100)}%</p>
                  </div>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </Block>
  );
}

// ══════════════════════════════════════════════════════════
//  BLOCK 3: Market Pressure + Actor Activity
// ══════════════════════════════════════════════════════════

function PressureBlock({ pressure }: { pressure: any }) {
  if (!pressure) return null;

  return (
    <Block testId="os-pressure" dark={false}>
      <div className="flex items-center gap-2 mb-3">
        <Users className="w-4 h-4 text-gray-400" />
        <span className="text-xs font-bold text-gray-400 uppercase tracking-[0.15em]">Market Pressure</span>
      </div>

      {/* Pressure summary */}
      <div className="flex items-center gap-4 mb-4">
        <div className="flex items-center gap-1.5">
          <div className="w-2 h-2 rounded-full bg-emerald-500" />
          <span className="text-sm font-bold text-emerald-600">{pressure.bullish}</span>
          <span className="text-[10px] text-gray-400">Bullish</span>
        </div>
        <div className="flex items-center gap-1.5">
          <div className="w-2 h-2 rounded-full bg-red-500" />
          <span className="text-sm font-bold text-red-600">{pressure.bearish}</span>
          <span className="text-[10px] text-gray-400">Bearish</span>
        </div>
        <div className="flex items-center gap-1.5">
          <div className="w-2 h-2 rounded-full bg-gray-400" />
          <span className="text-sm font-bold text-gray-500">{pressure.neutral}</span>
          <span className="text-[10px] text-gray-400">Neutral</span>
        </div>
      </div>

      {/* Actor Activity */}
      <div className="space-y-1.5">
        {(pressure.actors || []).map((actor: any, i: number) => (
          <div key={i} className="flex items-center justify-between py-1.5 border-b border-gray-100 last:border-0">
            <span className="text-xs font-medium text-gray-700">{actor.name}</span>
            <div className="flex items-center gap-2">
              <span className={`text-[10px] font-bold ${ACTION_COLORS[actor.action] || 'text-gray-500'}`}>
                {actor.action}
              </span>
              <span className="text-[10px] text-gray-400 tabular-nums w-8 text-right">{actor.score}</span>
            </div>
          </div>
        ))}
      </div>
    </Block>
  );
}

// ══════════════════════════════════════════════════════════
//  BLOCK 4: Liquidity Targets
// ══════════════════════════════════════════════════════════

const ZONE_ICONS: Record<string, any> = {
  target: Crosshair,
  magnet: Target,
  void: Eye,
};

const ZONE_COLORS: Record<string, string> = {
  target: 'text-cyan-400',
  magnet: 'text-amber-400',
  void: 'text-red-400',
};

const TREND_CONFIG: Record<string, { arrow: string; color: string; label: string }> = {
  strengthening: { arrow: '↑', color: 'text-emerald-400', label: 'strengthening' },
  weakening: { arrow: '↓', color: 'text-red-400', label: 'weakening' },
  stable: { arrow: '→', color: 'text-gray-500', label: 'stable' },
  new: { arrow: '★', color: 'text-cyan-400', label: 'new' },
};

function LiquidityTargetsBlock({ targets, evolution }: { targets: any[]; evolution: any[] }) {
  if (!targets || targets.length === 0) return null;

  // Build a lookup from evolution dynamics
  const dynamicsMap: Record<string, any> = {};
  if (evolution) {
    for (const d of evolution) {
      dynamicsMap[`${d.type}_${d.direction}`] = d;
    }
  }

  return (
    <Block testId="os-liquidity" dark>
      <div className="flex items-center gap-2 mb-3">
        <Crosshair className="w-4 h-4 text-cyan-400" />
        <span className="text-[10px] font-bold text-gray-500 uppercase tracking-[0.2em]">Liquidity Targets</span>
      </div>

      <div className="space-y-1.5">
        {targets.map((t, i) => {
          const Ic = ZONE_ICONS[t.zone_type] || Target;
          const color = ZONE_COLORS[t.zone_type] || 'text-gray-400';
          const dyn = dynamicsMap[`${t.zone_type}_${t.direction}`];
          const trend = dyn ? TREND_CONFIG[dyn.trend] || TREND_CONFIG.stable : null;
          return (
            <div key={i} className="flex items-center gap-3 px-3 py-2 rounded-lg bg-white/[0.03] border border-gray-800/20" data-testid={`liq-zone-${i}`}>
              <Ic className={`w-3.5 h-3.5 ${color} shrink-0`} />
              <span className={`text-[9px] font-bold uppercase shrink-0 w-14 ${color}`}>{t.zone_type}</span>
              <span className="text-[11px] text-gray-300 flex-1 truncate">{t.reason || t.direction || '—'}</span>
              {trend && (
                <span className={`text-[10px] font-bold shrink-0 ${trend.color}`} data-testid={`liq-trend-${i}`}>
                  {trend.arrow} {trend.label}
                </span>
              )}
              {t.confidence != null && (
                <span className="text-[10px] font-bold text-gray-500 tabular-nums shrink-0">{Math.round(t.confidence * 100)}%</span>
              )}
            </div>
          );
        })}
      </div>
    </Block>
  );
}

// ══════════════════════════════════════════════════════════
//  BLOCK 5: Alerts Feed
// ══════════════════════════════════════════════════════════

function AlertsFeedBlock({ alerts }: { alerts: any[] }) {
  if (!alerts || alerts.length === 0) return null;

  return (
    <Block testId="os-alerts" dark>
      <div className="flex items-center gap-2 mb-3">
        <Zap className="w-4 h-4 text-amber-400" />
        <span className="text-[10px] font-bold text-gray-500 uppercase tracking-[0.2em]">Live Alerts</span>
        <span className="text-[10px] font-bold text-gray-600 ml-auto">{alerts.length}</span>
      </div>

      <div className="space-y-1">
        {alerts.map((a, i) => {
          const Ic = ALERT_ICONS[a.type] || Info;
          const color = SEV_COLORS[a.severity] || 'text-gray-400';
          const dot = SEV_DOTS[a.severity] || 'bg-gray-400';
          const ts = a.timestamp ? _relTime(a.timestamp) : '';
          return (
            <div key={i} className="flex items-center gap-2.5 py-1.5">
              <div className={`w-1.5 h-1.5 rounded-full ${dot} shrink-0`} />
              <Ic className={`w-3 h-3 ${color} shrink-0`} />
              <span className={`text-[9px] font-black uppercase shrink-0 ${color}`}>{a.severity}</span>
              <span className="text-[10px] text-gray-400 flex-1 truncate">{a.message}</span>
              <span className="text-[9px] text-gray-600 tabular-nums shrink-0">{ts}</span>
            </div>
          );
        })}
      </div>
    </Block>
  );
}

// ══════════════════════════════════════════════════════════
//  BLOCK: REGIME TIMELINE
// ══════════════════════════════════════════════════════════

function _relTimeShort(ts: string): string {
  if (!ts) return '';
  const diff = Date.now() - new Date(ts).getTime();
  const m = Math.floor(diff / 60000);
  if (m < 1) return 'now';
  if (m < 60) return `${m}m`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h`;
  return `${Math.floor(h / 24)}d`;
}

function RegimeTimelineBlock({ timeline }: { timeline: any[] }) {
  if (!timeline || timeline.length === 0) return null;

  return (
    <Block testId="os-regime-timeline" dark>
      <div className="flex items-center gap-2 mb-3">
        <Clock className="w-4 h-4 text-violet-400" />
        <span className="text-[10px] font-bold text-gray-500 uppercase tracking-[0.2em]">Market Timeline</span>
        <span className="text-[9px] text-gray-600 ml-auto">last {timeline.length} changes</span>
      </div>

      <div className="space-y-0">
        {timeline.slice(0, 10).map((entry, i) => {
          const prev = entry.previous_regime;
          const cur = entry.regime;
          const driver = entry.driver;
          const conf = entry.confidence;
          const driverLabel = driver ? driver.replace(/_/g, ' ').replace(/\b\w/g, (c: string) => c.toUpperCase()) : '';
          const curLabel = cur.replace(/_/g, ' ').replace(/\b\w/g, (c: string) => c.toUpperCase());
          const prevLabel = prev ? prev.replace(/_/g, ' ').replace(/\b\w/g, (c: string) => c.toUpperCase()) : '';

          return (
            <div key={i} className="flex items-center gap-3 py-2 border-b border-gray-800/30 last:border-0" data-testid={`regime-event-${i}`}>
              <span className="text-[9px] text-gray-600 tabular-nums shrink-0 w-8">{_relTimeShort(entry.timestamp)}</span>
              <div className={`w-1.5 h-1.5 rounded-full shrink-0 ${i === 0 ? 'bg-violet-400 animate-pulse' : 'bg-gray-600'}`} />
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-1.5">
                  {prev && (
                    <>
                      <span className="text-[10px] text-gray-500">{prevLabel}</span>
                      <ArrowRight className="w-2.5 h-2.5 text-gray-600" />
                    </>
                  )}
                  <span className="text-[10px] font-bold text-white">{curLabel}</span>
                </div>
                {driverLabel && (
                  <span className="text-[9px] text-gray-600">driver: {driverLabel}</span>
                )}
              </div>
              <span className="text-[9px] text-gray-500 tabular-nums shrink-0">{Math.round(conf * 100)}%</span>
            </div>
          );
        })}
      </div>
    </Block>
  );
}


// ══════════════════════════════════════════════════════════
//  BLOCK: ACTOR RADAR
// ══════════════════════════════════════════════════════════

const DIR_CONFIG: Record<string, { icon: any; color: string; arrowColor: string }> = {
  up:      { icon: ArrowUpRight,   color: 'text-emerald-400', arrowColor: 'text-emerald-400' },
  down:    { icon: ArrowDownRight, color: 'text-red-400',     arrowColor: 'text-red-400' },
  neutral: { icon: Minus,          color: 'text-gray-500',    arrowColor: 'text-gray-500' },
};

const SUMMARY_COLORS: Record<string, string> = {
  'Net Bullish': 'text-emerald-400',
  'Net Bearish': 'text-red-400',
  'Mixed': 'text-amber-400',
};

function ActorRadarBlock({ radar }: { radar: any }) {
  if (!radar || !radar.actors || radar.actors.length === 0) return null;

  return (
    <Block testId="os-actor-radar" dark>
      <div className="flex items-center gap-2 mb-3">
        <Users className="w-4 h-4 text-cyan-400" />
        <span className="text-[10px] font-bold text-gray-500 uppercase tracking-[0.2em]">Actor Radar</span>
        <span className={`text-[10px] font-bold ml-auto ${SUMMARY_COLORS[radar.summary] || 'text-gray-400'}`}>{radar.summary}</span>
      </div>

      <div className="space-y-1">
        {radar.actors.map((actor: any) => {
          const dir = DIR_CONFIG[actor.direction] || DIR_CONFIG.neutral;
          const DirIcon = dir.icon;
          const strengthPct = actor.strength;
          const barColor = actor.direction === 'up' ? 'bg-emerald-400' : actor.direction === 'down' ? 'bg-red-400' : 'bg-gray-600';

          return (
            <div key={actor.id} className="flex items-center gap-3 px-3 py-2.5 rounded-lg bg-white/[0.03] border border-gray-800/20" data-testid={`actor-${actor.id}`}>
              <DirIcon className={`w-3.5 h-3.5 ${dir.arrowColor} shrink-0`} />
              <span className="text-[11px] font-bold text-white w-28 shrink-0">{actor.name}</span>
              <span className={`text-[10px] font-medium ${dir.color} w-36 shrink-0`}>
                {actor.action.replace(/\b\w/g, (c: string) => c.toUpperCase())}
              </span>
              {/* Strength bar */}
              <div className="flex-1 h-1.5 bg-gray-800 rounded-full overflow-hidden">
                <div className={`h-full ${barColor} rounded-full transition-all`} style={{ width: `${strengthPct}%` }} />
              </div>
              <span className={`text-[10px] font-bold tabular-nums shrink-0 ${dir.color}`} data-testid={`actor-strength-${actor.id}`}>{strengthPct}</span>
            </div>
          );
        })}
      </div>
    </Block>
  );
}

// ══════════════════════════════════════════════════════════
//  MAIN OS PAGE
// ══════════════════════════════════════════════════════════

export function OSTab() {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    try {
      const r = await fetch(`${API}/api/os/state`);
      const j = await r.json();
      if (j.ok) setData(j);
    } catch (e) {
      console.error('OS state fetch error:', e);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 className="w-5 h-5 animate-spin text-gray-400" />
      </div>
    );
  }

  if (!data) {
    return (
      <div className="text-center py-20">
        <p className="text-sm text-gray-400">No market state available. Engine snapshot building...</p>
      </div>
    );
  }

  return (
    <div className="space-y-3" data-testid="os-dashboard">
      {/* Header */}
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-gray-900 flex items-center justify-center">
            <Radio className="w-4 h-4 text-cyan-400" />
          </div>
          <div>
            <h2 className="text-lg font-bold text-gray-900">Market Intelligence OS</h2>
            <p className="text-xs text-gray-500">Real-time market awareness center</p>
          </div>
        </div>
        <button onClick={load} className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-gray-500 hover:text-gray-700 bg-gray-100 rounded-lg" data-testid="os-refresh">
          <RefreshCw className="w-3 h-3" /> Refresh
        </button>
      </div>

      {/* Block 0: Control Panel (compact strip) */}
      <ControlPanelBlock state={data.market_state} risk={data.market_risk} pulse={data.market_pulse} />

      {/* Block 1: Market State */}
      <MarketStateBlock state={data.market_state} />

      {/* Block 1.5: Market Risk */}
      <RiskBlock risk={data.market_risk} />

      {/* Block 1.7: Regime Timeline */}
      <RegimeTimelineBlock timeline={data.regime_timeline} />

      {/* Block 1.8: Actor Radar */}
      <ActorRadarBlock radar={data.actor_radar} />

      {/* Block 2: Opportunities (ranked) */}
      <OpportunitiesBlock opportunities={data.opportunities} />

      {/* Block 3 + 4: Market Pressure + Liquidity Targets */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
        <PressureBlock pressure={data.actor_pressure} />
        <LiquidityTargetsBlock targets={data.liquidity_targets} evolution={data.liquidity_evolution} />
      </div>

      {/* Block 5: Alerts Feed */}
      <AlertsFeedBlock alerts={data.alerts} />
    </div>
  );
}

export default OSTab;
