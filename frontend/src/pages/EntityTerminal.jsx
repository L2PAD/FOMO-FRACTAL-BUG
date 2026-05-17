/**
 * Entity Intelligence Terminal — Phase C: Actor Intelligence Integration
 * Full Actor Terminal with Intelligence Layer
 * Uses IntelligenceBlock pattern from CEX Flow / Token Intelligence
 */
import { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  ChevronLeft, Building, TrendingUp, TrendingDown, Activity,
  ArrowUpRight, ArrowDownRight, PieChart, Users, Coins,
  Target, Zap, Search, Layers, GitBranch, Eye, BarChart3,
  ArrowLeftRight, Shield, Fingerprint, Clock, Radio, RefreshCw,
  Globe, ChevronRight, AlertTriangle, Package, Crosshair, Brain,
  Gauge, BookOpen, Tag, Sparkles
} from 'lucide-react';
import { IntelligenceBlock } from '../components/intelligence';

const API = process.env.REACT_APP_BACKEND_URL;

function fmt(v) {
  if (!v && v !== 0) return '$0';
  const a = Math.abs(v);
  if (a >= 1e9) return `$${(v / 1e9).toFixed(2)}B`;
  if (a >= 1e6) return `$${(v / 1e6).toFixed(2)}M`;
  if (a >= 1e3) return `$${(v / 1e3).toFixed(1)}K`;
  return `$${v.toFixed(0)}`;
}
function pct(v) { return `${(v * 100).toFixed(1)}%`; }
function conf(v) { return `${(v * 100).toFixed(0)}%`; }
function clean(s) { return (s || '').replace(/_/g, ' '); }

const BEH_LIGHT = {
  accumulation: 'text-emerald-600',
  distribution: 'text-red-600',
  market_making: 'text-blue-600',
  liquidity_provision: 'text-cyan-600',
  treasury: 'text-amber-600',
  mixed: 'text-gray-500',
};

const ROLE_LIGHT = {
  liquidity_token: 'text-cyan-600',
  accumulation_token: 'text-emerald-600',
  distribution_token: 'text-red-600',
  neutral_token: 'text-gray-500',
};

const IMPACT_COLORS = {
  SYSTEMIC: 'text-red-400',
  HIGH: 'text-amber-400',
  MEDIUM: 'text-blue-400',
  LOW: 'text-gray-400',
};

const PRESSURE_COLORS = {
  bullish: { text: 'text-emerald-400', bg: 'bg-emerald-400/10' },
  bearish: { text: 'text-red-400', bg: 'bg-red-400/10' },
  neutral: { text: 'text-gray-400', bg: 'bg-gray-700/50' },
};

const CONVICTION_COLORS = {
  extreme: 'text-red-400',
  high: 'text-amber-400',
  moderate: 'text-blue-400',
  low: 'text-gray-400',
};

const REGIME_COLORS = {
  accumulation: 'text-emerald-400',
  distribution: 'text-red-400',
  liquidity: 'text-cyan-400',
  rotation: 'text-amber-400',
  dormant: 'text-gray-500',
};

const TYPE_ICONS = { exchange: Building, protocol: Layers, fund: PieChart, market_maker: Activity, whale: Eye };

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
// ROW 1: PROFILE HERO (dark) — with Quick Tags, Pressure, Strategy
// ═══════════════════════════════════════════
function ProfileHero({ entity, behaviour, clusters, impact, intelligence }) {
  const TypeIcon = TYPE_ICONS[entity?.type] || Building;
  const clusterWallets = clusters?.total_discovered || 0;
  const beh = behaviour?.behaviour_type || 'unknown';
  const behColor = beh !== 'unknown' && beh !== 'mixed' ? (BEH_LIGHT[beh] || 'text-gray-400') : 'text-gray-400';

  const pressure = intelligence?.pressure || 'neutral';
  const pColor = PRESSURE_COLORS[pressure] || PRESSURE_COLORS.neutral;
  const strategy = intelligence?.strategy || '';
  const quickTags = intelligence?.quick_tags || [];
  const actorImpact = intelligence?.actor_impact;

  return (
    <IntelligenceBlock dark testId="entity-profile">
      <div className="flex flex-col lg:flex-row lg:items-start lg:justify-between gap-4">
        <div className="flex items-center gap-4">
          <div className="w-12 h-12 rounded-xl bg-white/10 flex items-center justify-center">
            <TypeIcon className="w-6 h-6 text-gray-300" />
          </div>
          <div>
            <div className="text-xl font-black text-white" data-testid="entity-name">{entity?.name?.replace(/_/g, ' ')}</div>
            <div className="flex items-center gap-2 mt-1">
              <span className="text-[10px] font-bold text-gray-300 uppercase">
                {clean(entity?.type)}
              </span>
              <span className="text-[10px] text-gray-500">
                {entity?.category}
              </span>
              {beh !== 'unknown' && beh !== 'mixed' && (
                <span className={`text-[10px] font-bold capitalize ${behColor}`}>
                  {clean(beh)}
                </span>
              )}
            </div>
            {/* Strategy label */}
            {strategy && strategy !== 'Mixed Strategy' && (
              <div className="mt-1.5 flex items-center gap-1.5">
                <Brain className="w-3 h-3 text-violet-400" />
                <span className="text-[11px] font-bold text-violet-300" data-testid="actor-strategy-label">{strategy}</span>
              </div>
            )}
          </div>
        </div>
        <div className="grid grid-cols-5 gap-5">
          {[
            { label: 'Pressure', value: pressure.charAt(0).toUpperCase() + pressure.slice(1), color: pColor.text },
            { label: 'Actor Impact', value: actorImpact ? `${actorImpact.impact_score}` : '-', color: IMPACT_COLORS[actorImpact?.impact_category] || 'text-gray-400' },
            { label: 'Impact Level', value: actorImpact?.impact_category || '-', color: IMPACT_COLORS[actorImpact?.impact_category] || 'text-gray-400' },
            { label: 'Confidence', value: conf(behaviour?.confidence || 0), color: 'text-amber-400' },
            { label: 'Wallets', value: clusterWallets, color: 'text-cyan-400' },
          ].map(m => (
            <div key={m.label} className="text-right" data-testid={`hero-stat-${m.label.toLowerCase().replace(/\s/g, '-')}`}>
              <div className="text-[9px] font-bold text-gray-500 uppercase tracking-wider">{m.label}</div>
              <div className={`text-lg font-black tabular-nums ${m.color}`}>{m.value}</div>
            </div>
          ))}
        </div>
      </div>
      {/* Quick Tags */}
      {quickTags.length > 0 && (
        <div className="mt-3 pt-3 border-t border-gray-800 flex flex-wrap gap-1.5" data-testid="quick-tags">
          {quickTags.map((tag, i) => (
            <span key={i} className="text-[10px] font-bold text-gray-300 bg-white/5 px-2 py-0.5 rounded-full" data-testid={`quick-tag-${i}`}>
              {tag}
            </span>
          ))}
        </div>
      )}
    </IntelligenceBlock>
  );
}

// ═══════════════════════════════════════════
// ACTOR SIGNALS (dark) — highlights from /intelligence
// ═══════════════════════════════════════════
function ActorSignals({ intelligence }) {
  const highlights = intelligence?.highlights || [];
  if (highlights.length === 0) return null;

  return (
    <IntelligenceBlock dark testId="actor-signals">
      <div className="flex items-center gap-2 mb-3">
        <Sparkles className="w-4 h-4 text-amber-400" />
        <h3 className="text-xs font-bold text-gray-400 uppercase tracking-[0.15em]">Actor Signals</h3>
      </div>
      <div className="space-y-1.5">
        {highlights.map((h, i) => (
          <div key={i} className="flex items-center gap-2 text-[11px]" data-testid={`signal-${i}`}>
            <span className="w-1 h-1 rounded-full bg-amber-400 shrink-0" />
            <span className="text-gray-300">{h}</span>
          </div>
        ))}
      </div>
    </IntelligenceBlock>
  );
}

// ═══════════════════════════════════════════
// ENTITY SUMMARY (light) — rule-based text
// ═══════════════════════════════════════════
function EntitySummary({ intelligence }) {
  const summary = intelligence?.summary;
  if (!summary) return null;

  return (
    <IntelligenceBlock testId="entity-summary">
      <div className="flex items-center gap-2 mb-3">
        <BookOpen className="w-4 h-4 text-gray-400" />
        <h3 className="text-xs font-bold text-gray-400 uppercase tracking-[0.15em]">Entity Summary</h3>
      </div>
      <p className="text-sm text-gray-700 leading-relaxed" data-testid="summary-text">{summary}</p>
    </IntelligenceBlock>
  );
}

// ═══════════════════════════════════════════
// STRATEGY TIMELINE (light) — drift tracking
// ═══════════════════════════════════════════
function StrategyTimeline({ strategyHistory }) {
  const history = strategyHistory || [];
  if (history.length === 0) return null;

  const formatTime = (ts) => {
    const d = new Date(ts);
    const now = new Date();
    const diff = (now - d) / 1000;
    if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
    if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
    if (diff < 604800) return `${Math.floor(diff / 86400)}d ago`;
    return d.toLocaleDateString();
  };

  return (
    <IntelligenceBlock testId="strategy-timeline">
      <div className="flex items-center gap-2 mb-3">
        <Clock className="w-4 h-4 text-gray-400" />
        <h3 className="text-xs font-bold text-gray-400 uppercase tracking-[0.15em]">Strategy Timeline</h3>
      </div>
      <div className="space-y-2">
        {history.map((h, i) => {
          const isLatest = i === 0;
          return (
            <div key={i} className={`flex items-center gap-3 py-1.5 ${i < history.length - 1 ? 'border-b border-gray-100' : ''}`} data-testid={`strategy-history-${i}`}>
              <div className="w-16 shrink-0">
                <span className={`text-[10px] font-bold ${isLatest ? 'text-violet-600' : 'text-gray-400'}`}>
                  {isLatest ? 'Now' : formatTime(h.timestamp)}
                </span>
              </div>
              <div className="flex items-center gap-2 flex-1 min-w-0">
                <span className={`text-[11px] font-bold capitalize ${
                  h.strategy?.includes('Liquidity') ? 'text-cyan-600' :
                  h.strategy?.includes('Accum') ? 'text-emerald-600' :
                  h.strategy?.includes('Distrib') ? 'text-red-600' :
                  'text-gray-600'
                }`}>{clean(h.strategy || '?')}</span>
                <ChevronRight className="w-3 h-3 text-gray-300 shrink-0" />
                <span className={`text-[10px] capitalize ${REGIME_COLORS[h.regime] || 'text-gray-500'}`}>{clean(h.regime || '?')}</span>
              </div>
              <div className="flex items-center gap-2 shrink-0">
                <span className={`text-[10px] font-bold ${PRESSURE_COLORS[h.pressure]?.text?.replace('-400', '-600') || 'text-gray-500'}`}>
                  {h.pressure || '?'}
                </span>
                <span className={`text-[10px] capitalize ${CONVICTION_COLORS[h.conviction]?.replace('-400', '-600') || 'text-gray-400'}`}>
                  {h.conviction || '?'}
                </span>
              </div>
            </div>
          );
        })}
      </div>
    </IntelligenceBlock>
  );
}

// ═══════════════════════════════════════════
// TOKEN ACTIVITY (light) — per-token pressure
// ═══════════════════════════════════════════
function TokenActivity({ tokenPressure }) {
  const tokens = tokenPressure || [];
  if (tokens.length === 0) return null;

  return (
    <IntelligenceBlock testId="token-activity">
      <div className="flex items-center gap-2 mb-3">
        <BarChart3 className="w-4 h-4 text-gray-400" />
        <h3 className="text-xs font-bold text-gray-400 uppercase tracking-[0.15em]">Actor Token Activity</h3>
      </div>
      <div className="space-y-1.5">
        {tokens.map((t, i) => {
          const pc = t.pressure === 'bullish' ? 'text-emerald-600' : t.pressure === 'bearish' ? 'text-red-600' : 'text-gray-500';
          const rc = t.role === 'accumulation' ? 'text-emerald-600' : t.role === 'distribution' ? 'text-red-600' : t.role === 'liquidity' ? 'text-cyan-600' : 'text-gray-400';
          return (
            <div key={i} className="flex items-center justify-between py-1.5 border-b border-gray-100 last:border-0" data-testid={`token-pressure-${i}`}>
              <div className="flex items-center gap-2">
                <span className="text-xs font-bold text-gray-900 w-16 truncate">{t.symbol}</span>
                <span className={`text-[10px] font-bold capitalize ${rc}`}>{clean(t.role)}</span>
              </div>
              <div className="flex items-center gap-3">
                <span className="text-[10px] text-gray-400">dom {pct(t.dominance || 0)}</span>
                <span className={`text-[11px] font-bold capitalize ${pc}`} data-testid={`token-pressure-label-${i}`}>
                  {t.pressure === 'bullish' ? 'Bullish Pressure' : t.pressure === 'bearish' ? 'Distribution' : 'Liquidity'}
                </span>
              </div>
            </div>
          );
        })}
      </div>
    </IntelligenceBlock>
  );
}


function ImpactBlock({ impact }) {
  const level = impact?.impact_level || 'LOW';
  const score = impact?.impact_score || 0;
  const ic = IMPACT_COLORS[level] || IMPACT_COLORS.LOW;
  const components = impact?.components || {};

  return (
    <IntelligenceBlock dark testId="actor-impact">
      <div className="flex items-center gap-2 mb-3">
        <Target className={`w-4 h-4 ${ic}`} />
        <h3 className="text-xs font-bold text-gray-400 uppercase tracking-[0.15em]">Market Impact</h3>
      </div>
      <div className="flex items-center justify-between mb-3">
        <div className={`text-sm font-black ${ic}`}>{level}</div>
        <div className={`text-2xl font-black tabular-nums ${ic}`}>{score}</div>
      </div>
      <div className="space-y-2">
        {[
          { k: 'portfolio', label: 'Portfolio Weight', color: 'bg-violet-400' },
          { k: 'flow', label: 'Flow Activity', color: 'bg-emerald-400' },
          { k: 'network', label: 'Network Reach', color: 'bg-cyan-400' },
          { k: 'exchange', label: 'Exchange Access', color: 'bg-amber-400' },
        ].map(({ k, label, color }) => {
          const val = components[k]?.score || 0;
          return (
            <div key={k}>
              <div className="flex items-center justify-between mb-0.5">
                <span className="text-[9px] font-bold text-gray-500 uppercase tracking-wider">{label}</span>
                <span className="text-[10px] font-black text-gray-300 tabular-nums">{val}%</span>
              </div>
              <div className="h-1 bg-gray-800 rounded-full overflow-hidden">
                <div className={`h-full rounded-full ${color}`} style={{ width: `${val}%` }} />
              </div>
            </div>
          );
        })}
      </div>
      {impact?.drivers?.length > 0 && (
        <div className="mt-3 pt-2 border-t border-gray-800 space-y-0.5">
          {impact.drivers.map((d, i) => (
            <div key={i} className="text-[10px] text-gray-400 flex items-center gap-1.5">
              <ChevronRight className="w-2.5 h-2.5 text-gray-600" />{clean(d)}
            </div>
          ))}
        </div>
      )}
    </IntelligenceBlock>
  );
}

// ═══════════════════════════════════════════
// HOLDINGS (light)
// ═══════════════════════════════════════════
function HoldingsBlock({ portfolio, holdings, entityType }) {
  const totalVal = portfolio?.total_usd || 0;
  const isExchange = entityType === 'exchange';
  const noHoldings = totalVal === 0 && isExchange;

  return (
    <IntelligenceBlock testId="entity-holdings">
      <div className="flex items-center gap-2 mb-4">
        <PieChart className="w-4 h-4 text-gray-400" />
        <h3 className="text-xs font-bold text-gray-400 uppercase tracking-[0.15em]">Holdings</h3>
      </div>
      {noHoldings ? (
        <div className="py-4 text-center">
          <div className="text-sm font-bold text-gray-400">Custody entity</div>
          <div className="text-[11px] text-gray-400 mt-1">Holdings not tracked — hot wallets may not be indexed</div>
        </div>
      ) : (
        <>
          <div className="grid grid-cols-4 gap-4 mb-4">
            {[
              { label: 'Portfolio Value', value: fmt(totalVal), color: 'text-blue-600' },
              { label: 'Token Count', value: portfolio?.token_count || 0, color: 'text-gray-900' },
              { label: 'Top 3 Concentration', value: pct(portfolio?.top3_concentration || 0), color: 'text-gray-900' },
              { label: 'Stablecoin Ratio', value: holdings?.stablecoin_ratio ? pct(holdings.stablecoin_ratio) : '-', color: 'text-gray-900' },
            ].map(m => (
              <div key={m.label}>
                <div className="text-[9px] text-gray-500 uppercase tracking-wider">{m.label}</div>
                <div className={`text-lg font-black tabular-nums ${m.color}`}>{m.value}</div>
              </div>
            ))}
          </div>
          {holdings?.tokens?.length > 0 && (
            <div className="space-y-1.5">
              {holdings.tokens.slice(0, 6).map((t, i) => (
                <div key={i} className="flex items-center justify-between py-1.5 border-b border-gray-100 last:border-0">
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-bold text-gray-900">{t.symbol || '?'}</span>
                    <span className="text-[10px] text-gray-400">{t.name || ''}</span>
                  </div>
                  <div className="flex items-center gap-4 text-[11px]">
                    <span className="text-gray-600 tabular-nums">{fmt(t.value_usd || 0)}</span>
                    <span className="text-gray-400">{t.pct_of_portfolio ? pct(t.pct_of_portfolio) : '-'}</span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </>
      )}
    </IntelligenceBlock>
  );
}

// ═══════════════════════════════════════════
// FLOWS (light) + TIMELINE (light)
// ═══════════════════════════════════════════
function FlowsBlock({ flows }) {
  const allTime = flows?.all_time || {};
  const net = allTime.net_flow_usd || 0;
  const windows = flows?.flows || {};

  return (
    <IntelligenceBlock testId="entity-flows">
      <div className="flex items-center gap-2 mb-4">
        <ArrowLeftRight className="w-4 h-4 text-gray-400" />
        <h3 className="text-xs font-bold text-gray-400 uppercase tracking-[0.15em]">Capital Flows</h3>
      </div>
      <div className="grid grid-cols-4 gap-4 mb-4">
        <div>
          <div className="text-[9px] text-gray-500 uppercase tracking-wider">Inflow</div>
          <div className="text-lg font-black text-emerald-600 tabular-nums">{fmt(allTime.inflow_usd)}</div>
        </div>
        <div>
          <div className="text-[9px] text-gray-500 uppercase tracking-wider">Outflow</div>
          <div className="text-lg font-black text-red-600 tabular-nums">{fmt(allTime.outflow_usd)}</div>
        </div>
        <div>
          <div className="text-[9px] text-gray-500 uppercase tracking-wider">Net Flow</div>
          <div className={`text-lg font-black tabular-nums ${net >= 0 ? 'text-emerald-600' : 'text-red-600'}`}>{fmt(net)}</div>
        </div>
        <div>
          <div className="text-[9px] text-gray-500 uppercase tracking-wider">Velocity</div>
          <div className="text-lg font-black text-gray-900 tabular-nums">{fmt(flows?.flow_velocity)}</div>
        </div>
      </div>
      {Object.keys(windows).length > 0 && (
        <div className="space-y-1.5">
          {['24h', '7d', '30d'].map(w => {
            const wd = windows[w] || {};
            if (!wd.inflow_usd && !wd.outflow_usd) return null;
            const wNet = (wd.inflow_usd || 0) - (wd.outflow_usd || 0);
            return (
              <div key={w} className="flex items-center justify-between py-1.5 border-b border-gray-100 last:border-0 text-[11px]">
                <span className="text-gray-500 font-bold w-8">{w}</span>
                <span className="text-emerald-600 tabular-nums">{fmt(wd.inflow_usd)}</span>
                <span className="text-red-600 tabular-nums">{fmt(wd.outflow_usd)}</span>
                <span className={`font-bold tabular-nums ${wNet >= 0 ? 'text-emerald-600' : 'text-red-600'}`}>{wNet >= 0 ? '+' : ''}{fmt(wNet)}</span>
              </div>
            );
          })}
        </div>
      )}
    </IntelligenceBlock>
  );
}

function TimelineBlock({ timeline }) {
  const events = timeline?.events || [];
  const typeColors = {
    flow: 'text-emerald-500', token_shift: 'text-amber-500',
    behaviour: 'text-violet-500', cluster: 'text-cyan-500', multichain: 'text-blue-500',
  };
  const typeIcons = {
    flow: ArrowLeftRight, token_shift: Coins, behaviour: Fingerprint, cluster: GitBranch, multichain: Globe,
  };

  return (
    <IntelligenceBlock testId="entity-timeline">
      <div className="flex items-center gap-2 mb-4">
        <Clock className="w-4 h-4 text-gray-400" />
        <h3 className="text-xs font-bold text-gray-400 uppercase tracking-[0.15em]">Entity Timeline</h3>
      </div>
      {events.length === 0 ? (
        <p className="text-sm text-gray-400 text-center py-4">No timeline events</p>
      ) : (
        <div className="space-y-2 max-h-[260px] overflow-y-auto">
          {events.map((e, i) => {
            const Icon = typeIcons[e.type] || Activity;
            const color = typeColors[e.type] || 'text-gray-400';
            return (
              <div key={i} className="flex items-start gap-2.5 py-1.5 border-b border-gray-100 last:border-0" data-testid={`timeline-event-${i}`}>
                <Icon className={`w-3.5 h-3.5 mt-0.5 shrink-0 ${color}`} />
                <div className="flex-1 min-w-0">
                  <div className="text-[11px] text-gray-700">{clean(e.description)}</div>
                  <div className="text-[9px] text-gray-400">{e.window || ''}</div>
                </div>
                {e.direction && (
                  <span className={`text-[10px] font-bold ${
                    e.direction === 'inflow' || e.direction === 'accumulation' ? 'text-emerald-600' :
                    e.direction === 'outflow' || e.direction === 'distribution' ? 'text-red-600' :
                    'text-gray-500'
                  }`}>{clean(e.direction)}</span>
                )}
              </div>
            );
          })}
        </div>
      )}
    </IntelligenceBlock>
  );
}

// ═══════════════════════════════════════════
// TOKEN MATRIX (light) — with Dependencies
// ═══════════════════════════════════════════
function TokenMatrixBlock({ tokenMatrix, intelligence }) {
  const tokens = tokenMatrix?.tokens || [];
  const summary = tokenMatrix?.summary || {};
  const roleGroups = {};
  tokens.forEach(t => { const r = t.role || 'neutral_token'; if (!roleGroups[r]) roleGroups[r] = []; roleGroups[r].push(t); });

  const tokenDep = intelligence?.token_dependency || {};

  return (
    <IntelligenceBlock testId="token-matrix">
      <div className="flex items-center gap-2 mb-4">
        <Zap className="w-4 h-4 text-gray-400" />
        <h3 className="text-xs font-bold text-gray-400 uppercase tracking-[0.15em]">Token Flow Matrix</h3>
      </div>
      <div className="grid grid-cols-4 gap-4 mb-4">
        <div><div className="text-[9px] text-gray-500 uppercase">Tokens</div><div className="text-xl font-black text-gray-900 tabular-nums">{tokens.length}</div></div>
        <div><div className="text-[9px] text-gray-500 uppercase">Accumulation</div><div className="text-xl font-black text-emerald-600 tabular-nums">{summary.accumulation_count || roleGroups['accumulation_token']?.length || 0}</div></div>
        <div><div className="text-[9px] text-gray-500 uppercase">Distribution</div><div className="text-xl font-black text-red-600 tabular-nums">{summary.distribution_count || roleGroups['distribution_token']?.length || 0}</div></div>
        <div><div className="text-[9px] text-gray-500 uppercase">Liquidity</div><div className="text-xl font-black text-cyan-600 tabular-nums">{summary.liquidity_count || roleGroups['liquidity_token']?.length || 0}</div></div>
      </div>
      {/* Token Dependencies */}
      {(tokenDep.stablecoin_dependency > 0 || tokenDep.eth_dependency > 0) && (
        <div className="mb-4 p-3 rounded-xl bg-gray-50" data-testid="token-dependencies">
          <div className="text-[9px] font-bold text-gray-500 uppercase tracking-wider mb-2">Token Dependencies</div>
          <div className="grid grid-cols-3 gap-3">
            <div>
              <div className="text-[9px] text-gray-400 uppercase">Stablecoin</div>
              <div className={`text-sm font-black tabular-nums ${tokenDep.stablecoin_dependency >= 0.7 ? 'text-amber-600' : 'text-gray-700'}`}>
                {pct(tokenDep.stablecoin_dependency || 0)}
              </div>
            </div>
            <div>
              <div className="text-[9px] text-gray-400 uppercase">ETH</div>
              <div className="text-sm font-black text-gray-700 tabular-nums">{pct(tokenDep.eth_dependency || 0)}</div>
            </div>
            <div>
              <div className="text-[9px] text-gray-400 uppercase">Top Token{tokenDep.top_token_symbol ? ` (${tokenDep.top_token_symbol})` : ''}</div>
              <div className="text-sm font-black text-gray-700 tabular-nums">{pct(tokenDep.top_token_dependency || 0)}</div>
            </div>
          </div>
        </div>
      )}
      {tokens.length > 0 && (
        <div className="space-y-1.5">
          {tokens.slice(0, 8).map((t, i) => {
            const rc = ROLE_LIGHT[t.role] || ROLE_LIGHT.neutral_token;
            return (
              <div key={i} className="flex items-center justify-between py-1.5 border-b border-gray-100 last:border-0">
                <div className="flex items-center gap-2">
                  <span className="text-xs font-bold text-gray-900">{t.symbol || '?'}</span>
                  <span className={`text-[10px] font-bold capitalize ${rc}`}>
                    {clean((t.role || '').replace('_token', ''))}
                  </span>
                </div>
                <div className="flex items-center gap-3 text-[10px]">
                  <span className="text-gray-400">dom {pct(t.dominance_pct || 0)}</span>
                  <span className="text-gray-600 tabular-nums">{fmt(t.volume_usd || 0)}</span>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </IntelligenceBlock>
  );
}

// ═══════════════════════════════════════════
// BEHAVIOUR (light) — with Conviction, Regime, Playbook
// ═══════════════════════════════════════════
function BehaviourBlock({ behaviour, intelligence }) {
  const hasData = behaviour?.behaviour_type && behaviour.behaviour_type !== 'unknown' && behaviour.behaviour_type !== 'mixed' && behaviour.confidence > 0;

  if (!hasData) return (
    <IntelligenceBlock testId="entity-behaviour">
      <div className="flex items-center gap-2 mb-4"><Fingerprint className="w-4 h-4 text-gray-400" /><h3 className="text-xs font-bold text-gray-400 uppercase tracking-[0.15em]">Behaviour Analysis</h3></div>
      <p className="text-sm text-gray-400 text-center py-4">Insufficient data</p>
    </IntelligenceBlock>
  );

  const bc = BEH_LIGHT[behaviour.behaviour_type] || BEH_LIGHT.mixed;
  const conviction = intelligence?.conviction || 'low';
  const convColor = CONVICTION_COLORS[conviction] || CONVICTION_COLORS.low;
  const regime = intelligence?.regime || 'dormant';
  const regColor = REGIME_COLORS[regime] || REGIME_COLORS.dormant;
  const playbook = intelligence?.playbook || '';

  return (
    <IntelligenceBlock testId="entity-behaviour">
      <div className="flex items-center gap-2 mb-4">
        <Fingerprint className="w-4 h-4 text-gray-400" />
        <h3 className="text-xs font-bold text-gray-400 uppercase tracking-[0.15em]">Behaviour Analysis</h3>
      </div>
      {/* Row 1: Type + Confidence + Velocity */}
      <div className="grid grid-cols-3 gap-4 mb-3">
        <div>
          <div className="text-[9px] text-gray-500 uppercase">Type</div>
          <div className={`text-lg font-black capitalize ${bc}`}>{clean(behaviour.behaviour_type)}</div>
        </div>
        <div>
          <div className="text-[9px] text-gray-500 uppercase">Confidence</div>
          <div className="text-lg font-black text-gray-900 tabular-nums">{conf(behaviour.confidence)}</div>
        </div>
        <div>
          <div className="text-[9px] text-gray-500 uppercase">Velocity</div>
          <div className="text-lg font-black text-gray-900 tabular-nums">{behaviour.velocity || fmt(behaviour?.signals?.flow?.velocity_usd) || '-'}</div>
        </div>
      </div>
      {/* Row 2: Conviction + Regime + Playbook */}
      <div className="grid grid-cols-3 gap-4 mb-3 p-3 rounded-xl bg-gray-50" data-testid="intelligence-metrics">
        <div>
          <div className="text-[9px] text-gray-500 uppercase">Conviction</div>
          <div className={`text-sm font-black capitalize ${conviction === 'extreme' ? 'text-red-600' : conviction === 'high' ? 'text-amber-600' : conviction === 'moderate' ? 'text-blue-600' : 'text-gray-500'}`} data-testid="conviction-value">
            {clean(conviction)}
          </div>
        </div>
        <div>
          <div className="text-[9px] text-gray-500 uppercase">Regime</div>
          <div className={`text-sm font-black capitalize ${regime === 'accumulation' ? 'text-emerald-600' : regime === 'distribution' ? 'text-red-600' : regime === 'liquidity' ? 'text-cyan-600' : regime === 'rotation' ? 'text-amber-600' : 'text-gray-500'}`} data-testid="regime-value">
            {clean(regime)}
          </div>
        </div>
        <div>
          <div className="text-[9px] text-gray-500 uppercase">Playbook</div>
          <div className="text-sm font-black text-gray-700 capitalize" data-testid="playbook-value">{clean(playbook)}</div>
        </div>
      </div>
      {behaviour.drivers?.length > 0 && (
        <div className="space-y-1">
          {behaviour.drivers.slice(0, 4).map((d, i) => (
            <div key={i} className="text-[11px] text-gray-600 flex items-start gap-1.5">
              <span className="w-1 h-1 rounded-full bg-gray-400 mt-1.5 shrink-0" />{clean(d)}
            </div>
          ))}
        </div>
      )}
    </IntelligenceBlock>
  );
}

// ═══════════════════════════════════════════
// SIMILAR (light)
// ═══════════════════════════════════════════
function SimilarBlock({ similar }) {
  const items = similar?.similar || [];
  return (
    <IntelligenceBlock testId="similar-entities">
      <div className="flex items-center gap-2 mb-4"><Eye className="w-4 h-4 text-gray-400" /><h3 className="text-xs font-bold text-gray-400 uppercase tracking-[0.15em]">Similar Entities</h3></div>
      {items.length === 0 ? <p className="text-sm text-gray-400 text-center py-4">No similar entities</p> : (
        <div className="space-y-2">
          {items.slice(0, 5).map((s, i) => (
            <div key={i} className="flex items-center justify-between py-2 border-b border-gray-100 last:border-0" data-testid={`similar-${i}`}>
              <div>
                <div className="text-xs font-bold text-gray-900">{(s.name || s.slug || '').replace(/_/g, ' ')}</div>
                <div className="text-[10px] text-gray-400 capitalize">{(s.type || '').replace(/_/g, ' ')}</div>
              </div>
              <div className="flex items-center gap-3 text-[10px]">
                <span className="text-gray-400">Beh {((s.behaviour_sim || 0) * 100).toFixed(0)}%</span>
                <span className="text-gray-400">Port {((s.portfolio_sim || 0) * 100).toFixed(0)}%</span>
                <span className="text-sm font-black text-violet-600 tabular-nums">{((s.composite_score || 0) * 100).toFixed(0)}%</span>
              </div>
            </div>
          ))}
        </div>
      )}
    </IntelligenceBlock>
  );
}

// ═══════════════════════════════════════════
// CLUSTERS (light) — with Cluster Roles
// ═══════════════════════════════════════════
function ClustersBlock({ clusters, intelligence }) {
  const items = clusters?.clusters || [];
  const clusterRoles = intelligence?.cluster_roles || [];

  // Build lookup: cluster_id → role data
  const roleMap = {};
  clusterRoles.forEach(cr => { roleMap[cr.cluster_id] = cr; });

  const CLUSTER_ROLE_COLORS = {
    liquidity: 'text-cyan-600',
    trading: 'text-blue-600',
    custody: 'text-violet-600',
    treasury: 'text-amber-600',
    routing: 'text-emerald-600',
    unknown: 'text-gray-400',
  };

  return (
    <IntelligenceBlock testId="entity-clusters">
      <div className="flex items-center gap-2 mb-4"><GitBranch className="w-4 h-4 text-gray-400" /><h3 className="text-xs font-bold text-gray-400 uppercase tracking-[0.15em]">Wallet Clusters</h3></div>
      <div className="grid grid-cols-3 gap-3 mb-3">
        <div><div className="text-[9px] text-gray-500 uppercase">Discovered</div><div className="text-xl font-black text-cyan-600 tabular-nums">{clusters?.total_discovered || 0}</div></div>
        <div><div className="text-[9px] text-gray-500 uppercase">Clusters</div><div className="text-xl font-black text-gray-900 tabular-nums">{items.length}</div></div>
        <div><div className="text-[9px] text-gray-500 uppercase">Avg Conf</div><div className="text-xl font-black text-gray-900 tabular-nums">{items.length ? conf(items.reduce((s, c) => s + (c.confidence || 0), 0) / items.length) : '-'}</div></div>
      </div>
      {items.length > 0 && (
        <div className="space-y-1.5">
          {items.slice(0, 5).map((c, i) => {
            const roleData = roleMap[c.cluster_id];
            const role = roleData?.cluster_role || 'unknown';
            const roleColor = CLUSTER_ROLE_COLORS[role] || CLUSTER_ROLE_COLORS.unknown;
            const flowWeight = roleData?.flow_weight;
            const tokenProfile = roleData?.token_profile;

            return (
              <div key={i} className="flex items-center justify-between py-1.5 border-b border-gray-100 last:border-0 text-[11px]" data-testid={`cluster-row-${i}`}>
                <div className="flex items-center gap-2">
                  <span className="text-gray-500 truncate max-w-[100px]">{(c.cluster_id || '?').replace(/_/g, ' ')}</span>
                  <span className={`text-[10px] font-bold capitalize ${roleColor}`} data-testid={`cluster-role-${i}`}>
                    {clean(role)}
                  </span>
                </div>
                <div className="flex items-center gap-3">
                  {tokenProfile && tokenProfile !== 'single_asset' && (
                    <span className="text-[9px] text-gray-400 capitalize">{clean(tokenProfile)}</span>
                  )}
                  {flowWeight > 0 && (
                    <span className="text-[9px] text-gray-400">wt {(flowWeight * 100).toFixed(0)}%</span>
                  )}
                  <span className="text-gray-400">{c.cluster_size || c.size || 0} wallets</span>
                  <span className="text-cyan-600 font-bold tabular-nums">{conf(c.confidence || 0)}</span>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </IntelligenceBlock>
  );
}

function InteractionBlock({ interactions }) {
  const nodes = interactions?.nodes || [];
  const edges = interactions?.edges || [];
  const summary = interactions?.summary || {};
  const byType = summary.by_type || {};

  return (
    <IntelligenceBlock testId="interaction-network">
      <div className="flex items-center gap-2 mb-4"><Radio className="w-4 h-4 text-gray-400" /><h3 className="text-xs font-bold text-gray-400 uppercase tracking-[0.15em]">Interaction Network</h3></div>
      <div className="grid grid-cols-2 gap-3 mb-3">
        <div><div className="text-[9px] text-gray-500 uppercase">Nodes</div><div className="text-xl font-black text-violet-600 tabular-nums">{summary.total_nodes || 0}</div></div>
        <div><div className="text-[9px] text-gray-500 uppercase">Connections</div><div className="text-xl font-black text-cyan-600 tabular-nums">{summary.total_edges || 0}</div></div>
      </div>
      <div className="space-y-1 mb-3">
        {Object.entries(byType).filter(([k]) => k !== 'entity' || byType[k] > 1).map(([type, count]) => (
          <div key={type} className="flex items-center justify-between text-[11px]">
            <span className="text-gray-500 capitalize">{type.replace(/_/g, ' ')}s</span>
            <span className="text-gray-900 font-bold tabular-nums">{count}</span>
          </div>
        ))}
      </div>
      {edges.length > 0 && (
        <div className="space-y-1 max-h-[160px] overflow-y-auto">
          {edges.slice(0, 8).map((e, i) => {
            const targetNode = nodes.find(n => n.id === e.target) || {};
            const typeColor = e.type === 'exchange_flow' ? 'text-amber-600' : e.type === 'token_interaction' ? 'text-emerald-600' : e.type === 'similarity' ? 'text-violet-600' : e.type === 'otc_flow' ? 'text-red-500' : e.type === 'liquidity_routing' ? 'text-cyan-600' : 'text-gray-500';
            const typeLabel = e.type === 'exchange_flow' ? 'Exchange Flow' : e.type === 'token_interaction' ? 'Token Flow' : e.type === 'similarity' ? 'Similarity' : e.type === 'otc_flow' ? 'OTC' : e.type === 'liquidity_routing' ? 'Liquidity' : (e.type || 'flow').replace(/_/g, ' ');
            return (
              <div key={i} className="flex items-center gap-2 py-1.5 border-b border-gray-100 last:border-0 text-[10px]">
                <span className={`font-bold shrink-0 px-1.5 py-0.5 rounded bg-gray-50 ${typeColor}`}>{typeLabel}</span>
                <span className="text-gray-700 truncate flex-1">{targetNode.label || e.target}</span>
                <span className="text-gray-500 font-bold shrink-0 tabular-nums">{e.label || ''}</span>
              </div>
            );
          })}
        </div>
      )}
    </IntelligenceBlock>
  );
}

// ═══════════════════════════════════════════
// DISCOVERY (light)
// ═══════════════════════════════════════════
function DiscoveryBlock({ discovery }) {
  const candidates = discovery?.candidates || [];
  return (
    <IntelligenceBlock testId="entity-discovery">
      <div className="flex items-center gap-2 mb-4"><Search className="w-4 h-4 text-gray-400" /><h3 className="text-xs font-bold text-gray-400 uppercase tracking-[0.15em]">Discovery Candidates</h3></div>
      {candidates.length === 0 ? <p className="text-sm text-gray-400 text-center py-4">No candidates</p> : (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
          {candidates.slice(0, 8).map((c, i) => (
            <div key={i} className="p-3 rounded-xl bg-gray-50" data-testid={`discovery-${i}`}>
              <div className="flex items-center justify-between mb-1">
                <span className="text-[10px] text-gray-500 capitalize">{clean(c.candidate_type)}</span>
                <span className={`text-xs font-black tabular-nums ${(c.discovery_score || 0) >= 0.7 ? 'text-emerald-600' : 'text-gray-500'}`}>
                  {((c.discovery_score || 0) * 100).toFixed(0)}%
                </span>
              </div>
              <div className="text-[10px] text-gray-700 truncate">{(c.cluster_id || '?').replace(/_/g, ' ')}</div>
              <div className="text-[9px] text-gray-400 mt-1">{c.wallet_count || 0} wallets</div>
            </div>
          ))}
        </div>
      )}
    </IntelligenceBlock>
  );
}

// ═══════════════════════════════════════════
// MULTICHAIN (light)
// ═══════════════════════════════════════════
function MultichainBlock({ chains }) {
  const chainList = chains?.chains || [];
  const totalTx = chainList.reduce((s, c) => s + (c.tx_count || 0), 0);

  return (
    <IntelligenceBlock testId="entity-multichain">
      <div className="flex items-center gap-2 mb-4"><Globe className="w-4 h-4 text-gray-400" /><h3 className="text-xs font-bold text-gray-400 uppercase tracking-[0.15em]">Multichain Activity</h3></div>
      <div className="grid grid-cols-4 gap-4 mb-4">
        <div><div className="text-[9px] text-gray-500 uppercase">Active Chains</div><div className="text-xl font-black text-amber-600 tabular-nums">{chainList.filter(c => c.tx_count > 0).length}</div></div>
        <div><div className="text-[9px] text-gray-500 uppercase">Total Tx</div><div className="text-xl font-black text-gray-900 tabular-nums">{totalTx}</div></div>
        <div><div className="text-[9px] text-gray-500 uppercase">Primary</div><div className="text-lg font-black text-gray-900">{chains?.primary_chain || '-'}</div></div>
        <div><div className="text-[9px] text-gray-500 uppercase">Bridges</div><div className="text-xl font-black text-gray-900 tabular-nums">{chains?.bridge_count || 0}</div></div>
      </div>
      {chainList.length > 0 && (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
          {chainList.map((c, i) => {
            const pctVal = totalTx > 0 ? (c.tx_count / totalTx * 100) : 0;
            return (
              <div key={i} className="p-3 rounded-xl bg-gray-50">
                <div className="flex items-center justify-between mb-1">
                  <span className="text-xs font-bold text-gray-900">{c.chain_name || `Chain ${c.chain_id}`}</span>
                  <span className={`text-[10px] font-bold tabular-nums ${c.tx_count > 0 ? 'text-emerald-600' : 'text-gray-400'}`}>{c.tx_count} tx</span>
                </div>
                <div className="h-1.5 bg-gray-200 rounded-full overflow-hidden">
                  <div className="h-full rounded-full bg-amber-500" style={{ width: `${pctVal}%` }} />
                </div>
                <div className="text-[9px] text-gray-400 mt-1">{pctVal.toFixed(1)}%</div>
              </div>
            );
          })}
        </div>
      )}
    </IntelligenceBlock>
  );
}

// ═══════════════════════════════════════════
// OTC ACTIVITY (dark) — detected OTC trades for entity
// ═══════════════════════════════════════════
function OTCActivityBlock({ otcTrades }) {
  const trades = otcTrades?.trades || [];
  if (trades.length === 0) return null;

  const confColor = (c) => c >= 0.6 ? 'text-red-400' : c >= 0.4 ? 'text-amber-400' : 'text-gray-400';

  return (
    <IntelligenceBlock dark testId="otc-activity">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <Package className="w-4 h-4 text-amber-400" />
          <h3 className="text-xs font-bold text-gray-400 uppercase tracking-[0.15em]">OTC Activity</h3>
        </div>
        <span className="text-[10px] font-bold text-amber-400" data-testid="otc-count">{trades.length} detected</span>
      </div>
      <div className="space-y-2">
        {trades.slice(0, 5).map((t, i) => (
          <div key={i} className="py-2 border-b border-gray-800 last:border-0" data-testid={`otc-trade-${i}`}>
            <div className="flex items-center justify-between mb-1">
              <div className="flex items-center gap-2">
                <span className="text-xs font-black text-white">{t.asset}</span>
                <ArrowLeftRight className="w-3 h-3 text-gray-500" />
                <span className="text-xs font-black text-cyan-400">{t.stablecoin}</span>
              </div>
              <span className="text-sm font-black text-amber-400 tabular-nums" data-testid={`otc-value-${i}`}>{t.usd_value_fmt}</span>
            </div>
            <div className="flex items-center justify-between text-[10px]">
              <div className="flex items-center gap-3">
                <span className="text-gray-500">Seller: <span className="text-gray-300">{t.seller_entity}</span></span>
                <span className="text-gray-500">Buyer: <span className="text-gray-300">{t.buyer_entity}</span></span>
              </div>
              <span className={`font-bold ${confColor(t.confidence)}`} data-testid={`otc-confidence-${i}`}>
                {(t.confidence * 100).toFixed(0)}% conf
              </span>
            </div>
            <div className="flex items-center gap-3 mt-1 text-[9px] text-gray-600">
              <span>val_match: {(t.signals?.value_match * 100).toFixed(0)}%</span>
              <span>time: {(t.signals?.time_proximity * 100).toFixed(0)}%</span>
              <span>cluster: {(t.signals?.cluster_distance * 100).toFixed(0)}%</span>
              <span>liq: {(t.signals?.liquidity * 100).toFixed(0)}%</span>
            </div>
          </div>
        ))}
      </div>
    </IntelligenceBlock>
  );
}

// ═══════════════════════════════════════════
// MAIN
// ═══════════════════════════════════════════
export default function EntityTerminal({ _embeddedEntityId, _embeddedOnBack }) {
  const params = useParams();
  const navigate = useNavigate();
  const entityId = _embeddedEntityId || params.entityId;
  const goBack = _embeddedOnBack || (() => navigate('/entities'));
  const [loading, setLoading] = useState(true);
  const [entity, setEntity] = useState(null);
  const [portfolio, setPortfolio] = useState(null);
  const [holdings, setHoldings] = useState(null);
  const [flows, setFlows] = useState(null);
  const [behaviour, setBehaviour] = useState(null);
  const [tokenMatrix, setTokenMatrix] = useState(null);
  const [similar, setSimilar] = useState(null);
  const [clusters, setClusters] = useState(null);
  const [discovery, setDiscovery] = useState(null);
  const [chains, setChains] = useState(null);
  const [impact, setImpact] = useState(null);
  const [timeline, setTimeline] = useState(null);
  const [interactions, setInteractions] = useState(null);
  const [intelligence, setIntelligence] = useState(null);
  const [strategyHistory, setStrategyHistory] = useState(null);
  const [tokenPressure, setTokenPressure] = useState(null);
  const [otcTrades, setOtcTrades] = useState(null);

  const loadEntity = useCallback(async () => {
    if (!entityId) return;
    setLoading(true);
    const base = `${API}/api/entities/v2`;
    try {
      const results = await Promise.allSettled([
        fetch(`${base}/${entityId}`).then(r => r.json()),
        fetch(`${base}/${entityId}/portfolio`).then(r => r.json()),
        fetch(`${base}/${entityId}/holdings`).then(r => r.json()),
        fetch(`${base}/${entityId}/flows`).then(r => r.json()),
        fetch(`${base}/${entityId}/behaviour`).then(r => r.json()),
        fetch(`${base}/${entityId}/token-matrix`).then(r => r.json()),
        fetch(`${base}/${entityId}/similar`).then(r => r.json()),
        fetch(`${base}/${entityId}/clusters`).then(r => r.json()),
        fetch(`${base}/discovery`).then(r => r.json()),
        fetch(`${base}/${entityId}/chains`).then(r => r.json()),
        fetch(`${base}/${entityId}/impact`).then(r => r.json()),
        fetch(`${base}/${entityId}/timeline`).then(r => r.json()),
        fetch(`${base}/${entityId}/interactions`).then(r => r.json()),
        fetch(`${base}/${entityId}/intelligence`).then(r => r.json()),
        fetch(`${base}/${entityId}/strategy-history`).then(r => r.json()),
        fetch(`${base}/${entityId}/token-pressure`).then(r => r.json()),
        fetch(`${API}/api/intelligence/otc?entity=${entityId}`).then(r => r.json()),
      ]);
      const val = (i) => results[i].status === 'fulfilled' ? results[i].value : null;
      setEntity(val(0)?.entity || null);
      setPortfolio(val(1));
      setHoldings(val(2));
      setFlows(val(3));
      setBehaviour(val(4));
      setTokenMatrix(val(5));
      setSimilar(val(6));
      setClusters(val(7));
      setDiscovery(val(8));
      setChains(val(9));
      setImpact(val(10));
      setTimeline(val(11));
      setInteractions(val(12));
      setIntelligence(val(13));
      setStrategyHistory(val(14)?.history || []);
      setTokenPressure(val(15)?.tokens || []);
      setOtcTrades(val(16));
    } catch (e) {
      console.error('Failed:', e);
    } finally {
      setLoading(false);
    }
  }, [entityId]);

  useEffect(() => { loadEntity(); }, [loadEntity]);

  if (!entityId) { navigate('/entities'); return null; }

  return (
    <div className="space-y-4" data-testid="entity-terminal">
      {/* Header */}
      <div className="flex items-center justify-between">
        <button onClick={goBack} className="flex items-center gap-1.5 text-xs text-gray-400 hover:text-gray-700 transition-colors" data-testid="back-to-list">
          <ChevronLeft className="w-3.5 h-3.5" /> Back to Entities
        </button>
        <button onClick={loadEntity} disabled={loading} className="p-2 text-gray-400 hover:text-gray-700 transition-colors disabled:opacity-50" data-testid="refresh-btn">
          <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
        </button>
      </div>

      {loading && !entity ? (
        <Skeleton dark />
      ) : (
        <>
          {/* Row 1: Profile Hero + Impact */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
            <div className="lg:col-span-2"><ProfileHero entity={entity} behaviour={behaviour} clusters={clusters} impact={impact} intelligence={intelligence} /></div>
            <ImpactBlock impact={impact} />
          </div>

          {/* Row 2: Actor Signals */}
          <ActorSignals intelligence={intelligence} />

          {/* Row 2.5: OTC Activity */}
          <OTCActivityBlock otcTrades={otcTrades} />

          {/* Row 3: Entity Summary */}
          <EntitySummary intelligence={intelligence} />

          {/* Row 4: Holdings */}
          <HoldingsBlock portfolio={portfolio} holdings={holdings} entityType={entity?.type} />

          {/* Row 5: Flows + Timeline */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <FlowsBlock flows={flows} />
            <TimelineBlock timeline={timeline} />
          </div>

          {/* Row 6: Token Matrix */}
          <TokenMatrixBlock tokenMatrix={tokenMatrix} intelligence={intelligence} />

          {/* Row 6.5: Token Activity (per-token pressure) */}
          <TokenActivity tokenPressure={tokenPressure} />

          {/* Row 7: Behaviour */}
          <BehaviourBlock behaviour={behaviour} intelligence={intelligence} />

          {/* Row 8: Similar */}
          <SimilarBlock similar={similar} />

          {/* Row 9: Clusters + Interaction */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <ClustersBlock clusters={clusters} intelligence={intelligence} />
            <InteractionBlock interactions={interactions} />
          </div>

          {/* Row 10: Discovery */}
          <DiscoveryBlock discovery={discovery} />

          {/* Row 11: Multichain */}
          <MultichainBlock chains={chains} />

          {/* Row 12: Strategy Timeline */}
          <StrategyTimeline strategyHistory={strategyHistory} />
        </>
      )}
    </div>
  );
}
