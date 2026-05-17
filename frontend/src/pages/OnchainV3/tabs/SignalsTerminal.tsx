/**
 * Signals Terminal V3.3 — Chain-Aware On-chain Intelligence
 * EVM-only. Chain badges, explorer links, evidence, provenance.
 */

import React, { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import { useSearchParams } from 'react-router-dom';
import {
  Radio, Zap, TrendingUp, TrendingDown, Minus,
  RefreshCw, Loader2, Target, Activity,
  ShieldAlert, ArrowUpRight, ArrowDownRight,
  BarChart3, Layers, Users, Droplets, AlertTriangle,
  CheckCircle, AlertOctagon, MinusCircle, Info, Shield, Clock,
  ExternalLink, ChevronDown, ChevronRight, Copy, Check,
} from 'lucide-react';

const API = process.env.REACT_APP_BACKEND_URL;

/* ═══════════════════ CONFIG ═══════════════════ */

const SEV: Record<string, { color: string; bg: string; border: string }> = {
  EXTREME: { color: 'text-red-400',   bg: 'bg-red-500/10',   border: 'border-red-500/20' },
  STRONG:  { color: 'text-amber-400', bg: 'bg-amber-500/10', border: 'border-amber-500/20' },
  WATCH:   { color: 'text-cyan-400',  bg: 'bg-cyan-500/8',   border: 'border-cyan-500/15' },
  WEAK:    { color: 'text-gray-500',  bg: 'bg-gray-500/5',   border: 'border-gray-500/15' },
};

const DIR: Record<string, { icon: any; color: string; label: string }> = {
  BULLISH:  { icon: ArrowUpRight,   color: 'text-emerald-400', label: 'Bull' },
  BEARISH:  { icon: ArrowDownRight, color: 'text-red-400',     label: 'Bear' },
  NEUTRAL:  { icon: Minus,          color: 'text-gray-500',    label: 'Neutral' },
};

const STAT: Record<string, { color: string; bg: string }> = {
  confirmed:   { color: 'text-emerald-400', bg: 'bg-emerald-500/10' },
  forming:     { color: 'text-cyan-400',    bg: 'bg-cyan-500/10' },
  detected:    { color: 'text-amber-400',   bg: 'bg-amber-500/10' },
  cooling:     { color: 'text-orange-400',  bg: 'bg-orange-500/10' },
  invalidated: { color: 'text-red-400',     bg: 'bg-red-500/10' },
};

const ALIGN_CFG: Record<string, { icon: any; color: string; label: string }> = {
  aligned:    { icon: CheckCircle,  color: 'text-emerald-400', label: 'Aligned' },
  contrarian: { icon: AlertOctagon, color: 'text-orange-400',  label: 'Contrarian' },
  neutral:    { icon: MinusCircle,  color: 'text-gray-500',    label: 'Neutral' },
};

const TYPE_ICONS: Record<string, any> = {
  SETUP_CONFIRMATION: Zap, SETUP_FAILURE: AlertTriangle,
  ACCUMULATION: TrendingUp, DISTRIBUTION: TrendingDown,
  LIQUIDITY_MAGNET: Target, LIQUIDITY_BREAK: Droplets,
  SMART_MONEY_CLUSTER: Users, ACTOR_ACCUMULATION: Users,
  ACTOR_DISTRIBUTION: Users, FLOW_ACCELERATION: Activity,
  DEVIATION: BarChart3, UNUSUAL_ACTIVITY: ShieldAlert,
  // Entity Intelligence types
  CEX_INFLOW: ArrowDownRight, CEX_OUTFLOW: ArrowUpRight,
  EXCHANGE_ACTIVITY: Activity, SMART_MONEY_ACTIVITY: Users,
  MM_ACTIVITY: BarChart3, WHALE_TRANSFER: Layers,
  TOKEN_TRANSFER: Layers,
  // Discovery types (Sprint 2)
  SMART_MONEY_ACCUMULATION: TrendingUp,
  SMART_MONEY_DISTRIBUTION: TrendingDown,
  CLUSTER_ACTIVITY: Layers,
};

function formatTokenAmount(amount: number, symbol: string): string {
  if (amount >= 1_000_000) return `${(amount / 1_000_000).toFixed(1)}M ${symbol}`;
  if (amount >= 1_000) return `${(amount / 1_000).toFixed(1)}k ${symbol}`;
  return `${amount.toFixed(1)} ${symbol}`;
}

function formatUsd(value: number): string {
  if (!value || value <= 0) return '';
  if (value >= 1_000_000) return `$${(value / 1_000_000).toFixed(1)}M`;
  if (value >= 1_000) return `$${(value / 1_000).toFixed(1)}k`;
  return `$${value.toFixed(0)}`;
}

/* Chain badge colors */
const CHAIN_BADGE: Record<string, { label: string; bg: string; text: string }> = {
  ethereum: { label: 'ETH',  bg: 'bg-gray-500/15',   text: 'text-gray-400' },
  arbitrum: { label: 'ARB',  bg: 'bg-blue-500/15',   text: 'text-blue-400' },
  optimism: { label: 'OP',   bg: 'bg-red-500/15',    text: 'text-red-400' },
  base:     { label: 'BASE', bg: 'bg-violet-500/15', text: 'text-violet-400' },
};

type FilterTab = 'all' | 'live' | 'structural' | 'actors' | 'liquidity';

const CHAIN_FILTERS = [
  { id: 'all', label: 'All Chains' },
  { id: 'ethereum', label: 'ETH' },
  { id: 'arbitrum', label: 'ARB' },
  { id: 'optimism', label: 'OP' },
  { id: 'base', label: 'BASE' },
];

function useSearchParamsCompat(): [URLSearchParams, (p: URLSearchParams) => void] {
  const [sp, setSp] = useSearchParams();
  return [sp, setSp];
}
const TABS: { id: FilterTab; label: string }[] = [
  { id: 'all', label: 'All' },
  { id: 'live', label: 'Live' },
  { id: 'structural', label: 'Structural' },
  { id: 'actors', label: 'Actors' },
  { id: 'liquidity', label: 'Liquidity' },
];
const TAB_TYPES: Record<FilterTab, string[]> = {
  all: [],
  live: ['SETUP_CONFIRMATION', 'SETUP_FAILURE', 'FLOW_ACCELERATION', 'CEX_INFLOW', 'CEX_OUTFLOW', 'EXCHANGE_ACTIVITY'],
  structural: ['ACCUMULATION', 'DISTRIBUTION', 'DEVIATION', 'UNUSUAL_ACTIVITY', 'WHALE_TRANSFER', 'TOKEN_TRANSFER'],
  actors: ['ACTOR_ACCUMULATION', 'ACTOR_DISTRIBUTION', 'SMART_MONEY_CLUSTER', 'SMART_MONEY_ACTIVITY', 'MM_ACTIVITY', 'SMART_MONEY_ACCUMULATION', 'SMART_MONEY_DISTRIBUTION', 'CLUSTER_ACTIVITY'],
  liquidity: ['LIQUIDITY_MAGNET', 'LIQUIDITY_BREAK'],
};

function ageStr(min: number): string {
  if (!min && min !== 0) return '';
  if (min < 1) return '<1m';
  if (min < 60) return `${min}m`;
  const h = Math.floor(min / 60);
  return h < 24 ? `${h}h` : `${Math.floor(h / 24)}d`;
}

/* ═══════════════════ MAIN ═══════════════════ */

export function SignalsTerminal() {
  const [signals, setSignals] = useState<any[]>([]);
  const [stats, setStats] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<FilterTab>('all');
  const [sevFilter, setSevFilter] = useState<string | null>(null);
  const [dirFilter, setDirFilter] = useState<string | null>(null);
  const [clusterView, setClusterView] = useState(false);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [clusterNames, setClusterNames] = useState<Record<string, string>>({});

  // Chain filter: read from URL params, persist changes
  const [searchParams, setSearchParams] = useSearchParamsCompat();
  const chainFilter = searchParams.get('chain') || 'all';
  const setChainFilter = useCallback((chain: string) => {
    const params = new URLSearchParams(searchParams.toString());
    if (chain === 'all') { params.delete('chain'); } else { params.set('chain', chain); }
    setSearchParams(params);
  }, [searchParams, setSearchParams]);

  // Fetch cluster name mapping
  useEffect(() => {
    fetch(`${API}/api/onchain-overview/clusters?limit=50`)
      .then(r => r.json())
      .then(d => {
        if (d.ok && d.clusters) {
          const map: Record<string, string> = {};
          d.clusters.forEach((c: any) => { if (c.cluster_id && c.cluster_name) map[c.cluster_id] = c.cluster_name; });
          setClusterNames(map);
        }
      })
      .catch(() => {});
  }, []);

  const load = useCallback(async () => {
    try {
      let url = `${API}/api/signals`;
      const params: string[] = [];
      if (dirFilter) params.push(`direction=${dirFilter}`);
      if (chainFilter && chainFilter !== 'all') params.push(`chain=${chainFilter}`);
      if (params.length) url += '?' + params.join('&');

      const [sigRes, statRes] = await Promise.all([
        fetch(url), fetch(`${API}/api/signals/stats`),
      ]);
      const sigJ = await sigRes.json();
      const statJ = await statRes.json();
      if (sigJ.ok) setSignals(sigJ.signals || []);
      if (statJ.ok) setStats(statJ);
    } catch (e) { console.error('Signals fetch error:', e); }
    finally { setLoading(false); }
  }, [dirFilter, chainFilter]);

  useEffect(() => { load(); const iv = setInterval(load, 30_000); return () => clearInterval(iv); }, [load]);

  const filtered = useMemo(() => {
    let r = signals;
    const types = TAB_TYPES[activeTab];
    if (types?.length) r = r.filter(s => types.includes(s.signal_type));
    if (sevFilter) r = r.filter(s => s.severity === sevFilter);
    return r;
  }, [signals, activeTab, sevFilter]);

  /* Top cards: strong >= 60, fallback to watch >= 40 */
  const { topSignals, topLabel } = useMemo(() => {
    const strong = signals.filter(s => s.score >= 60).slice(0, 3);
    if (strong.length > 0) return { topSignals: strong, topLabel: 'Top Strong Signals' };
    const watch = signals.filter(s => s.score >= 40).slice(0, 3);
    if (watch.length > 0) return { topSignals: watch, topLabel: 'Top Watch Signals' };
    return { topSignals: [], topLabel: '' };
  }, [signals]);

  /* Cluster groups */
  const clustered = useMemo(() => {
    if (!clusterView) return null;
    const map: Record<string, { id: string; direction: string; signals: any[]; maxScore: number }> = {};
    for (const s of filtered) {
      const cid = s.cluster_id;
      if (!cid) { map[s.id] = { id: s.id, direction: s.direction, signals: [s], maxScore: s.score }; continue; }
      if (!map[cid]) map[cid] = { id: cid, direction: s.direction, signals: [], maxScore: 0 };
      map[cid].signals.push(s);
      map[cid].maxScore = Math.max(map[cid].maxScore, s.score);
    }
    return Object.values(map).sort((a, b) => b.maxScore - a.maxScore);
  }, [filtered, clusterView]);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20" data-testid="signals-loading">
        <Loader2 className="w-5 h-5 animate-spin text-gray-400" />
      </div>
    );
  }

  return (
    <div className="space-y-4 max-w-[1400px]" data-testid="signals-terminal">

      {/* ═══ HEADER ═══ */}
      <div className="flex items-center justify-between flex-wrap gap-3" data-testid="signals-header">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-lg bg-gradient-to-br from-cyan-500/20 to-violet-500/20 flex items-center justify-center border border-cyan-500/20">
            <Radio className="w-4 h-4 text-cyan-400" />
          </div>
          <div>
            <h2 className="text-lg font-bold text-gray-900">Signals Terminal</h2>
            <p className="text-xs text-gray-500">Context-aware execution intelligence</p>
          </div>
        </div>
        {stats && (
          <div className="flex items-center gap-5 flex-wrap">
            <Chip label="Active" value={stats.total} color="text-white" />
            <Chip label="Strong" value={stats.strong} color="text-amber-400" />
            <Chip label="Extreme" value={stats.extreme} color="text-red-400" />
            <Chip label="Avg" value={stats.avg_score} color="text-cyan-400" />
            <div className="flex items-center gap-1.5">
              <ArrowUpRight className="w-3 h-3 text-emerald-400" />
              <span className="text-xs font-bold text-emerald-400">{stats.bullish}</span>
              <span className="text-[9px] text-gray-400 mx-0.5">/</span>
              <ArrowDownRight className="w-3 h-3 text-red-400" />
              <span className="text-xs font-bold text-red-400">{stats.bearish}</span>
            </div>
            {stats.has_cluster && (
              <div className="flex items-center gap-1 px-2 py-0.5 rounded bg-violet-500/10 border border-violet-500/20">
                <Layers className="w-3 h-3 text-violet-400" />
                <span className="text-[9px] font-bold text-violet-400">{stats.cluster_count} clusters</span>
              </div>
            )}
            <button onClick={load} className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-gray-500 hover:text-gray-700 bg-gray-100 rounded-lg" data-testid="signals-refresh">
              <RefreshCw className="w-3 h-3" /> Refresh
            </button>
          </div>
        )}
      </div>

      {/* ═══ CONTROLS ═══ */}
      <div className="flex items-center gap-2 flex-wrap" data-testid="signals-controls">
        {TABS.map(tab => (
          <button key={tab.id} onClick={() => setActiveTab(tab.id)}
            className={`px-3 py-1.5 text-[10px] font-bold rounded-lg transition-all ${
              activeTab === tab.id ? 'bg-[#0a0e14] text-white border border-gray-700' : 'bg-gray-100 text-gray-500 hover:bg-gray-200'
            }`} data-testid={`signals-tab-${tab.id}`}>
            {tab.label}
          </button>
        ))}

        <div className="w-px h-5 bg-gray-200 mx-1" />

        {(['BULLISH', 'BEARISH'] as const).map(d => {
          const cfg = DIR[d];
          const DIcon = cfg.icon;
          return (
            <button key={d} onClick={() => setDirFilter(dirFilter === d ? null : d)}
              className={`flex items-center gap-1 px-2.5 py-1 text-[9px] font-black rounded transition-all ${
                dirFilter === d ? `bg-[#0a0e14] ${cfg.color} border border-gray-700` : 'bg-gray-50 text-gray-400 hover:bg-gray-100'
              }`} data-testid={`direction-filter-${d.toLowerCase()}`}>
              <DIcon className="w-3 h-3" /> {cfg.label}
            </button>
          );
        })}

        <div className="w-px h-5 bg-gray-200 mx-1" />

        {['EXTREME', 'STRONG', 'WATCH', 'WEAK'].map(sev => {
          const cfg = SEV[sev];
          return (
            <button key={sev} onClick={() => setSevFilter(sevFilter === sev ? null : sev)}
              className={`px-2.5 py-1 text-[9px] font-black rounded transition-all ${
                sevFilter === sev ? `${cfg.bg} ${cfg.color} border ${cfg.border}` : 'bg-gray-50 text-gray-400 hover:bg-gray-100'
              }`} data-testid={`severity-filter-${sev.toLowerCase()}`}>
              {sev}
            </button>
          );
        })}

        <div className="w-px h-5 bg-gray-200 mx-1" />

        <button onClick={() => setClusterView(!clusterView)}
          className={`flex items-center gap-1 px-2.5 py-1 text-[9px] font-black rounded transition-all ${
            clusterView ? 'bg-violet-500/15 text-violet-400 border border-violet-500/30' : 'bg-gray-50 text-gray-400 hover:bg-gray-100'
          }`} data-testid="cluster-toggle">
          <Layers className="w-3 h-3" /> Clusters
        </button>

        <div className="w-px h-5 bg-gray-200 mx-1" />

        {/* Chain filter */}
        <div className="flex items-center gap-1" data-testid="chain-filter">
          {CHAIN_FILTERS.map(cf => {
            const badge = cf.id !== 'all' ? CHAIN_BADGE[cf.id] : null;
            const isActive = chainFilter === cf.id;
            return (
              <button key={cf.id} onClick={() => setChainFilter(cf.id)}
                className={`px-2 py-1 text-[9px] font-bold rounded transition-all ${
                  isActive
                    ? badge ? `${badge.bg} ${badge.text} border border-current/20` : 'bg-[#0a0e14] text-white border border-gray-700'
                    : 'bg-gray-50 text-gray-400 hover:bg-gray-100'
                }`} data-testid={`chain-filter-${cf.id}`}>
                {cf.label}
              </button>
            );
          })}
        </div>

        <span className="text-[10px] text-gray-400 ml-auto" data-testid="signals-count">{filtered.length} signals</span>
      </div>

      {/* ═══ TOP CARDS (Strong fallback → Watch) ═══ */}
      {activeTab === 'all' && !sevFilter && !dirFilter && (
        <div data-testid="signals-top">
          {topSignals.length > 0 ? (
            <>
              <p className="text-[9px] font-bold text-gray-500 uppercase tracking-[0.15em] mb-2" data-testid="top-signals-label">{topLabel}</p>
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                {topSignals.map((sig: any, i: number) => (
                  <TopCard key={sig.id} signal={sig} rank={i + 1} clusterNames={clusterNames} />
                ))}
              </div>
            </>
          ) : (
            <div className="flex items-center justify-center py-6 bg-[#0a0e14] rounded-xl border border-gray-800/40">
              <p className="text-xs text-gray-600" data-testid="no-strong-signals">No actionable signals currently</p>
            </div>
          )}
        </div>
      )}

      {/* ═══ TABLE ═══ */}
      <div className="bg-[#0a0e14] intelligence-dark rounded-xl border border-gray-800/40 overflow-hidden" data-testid="signals-table">
        <div className="grid grid-cols-[50px_38px_1fr_60px_50px_50px_65px_68px_100px_55px_45px] gap-1.5 px-4 py-2 border-b border-gray-800/40">
          {['Asset','Chain','Signal','Dir','Score','Conf','Status','Align','Move','Risk','Age'].map(h => (
            <span key={h} className="text-[8px] font-bold text-gray-600 uppercase">{h}</span>
          ))}
        </div>

        {clusterView && clustered ? (
          clustered.length === 0 ? <EmptyRow /> : clustered.map(cl => (
            <ClusterGroup key={cl.id} cluster={cl} selectedId={selectedId} onSelect={setSelectedId} clusterNames={clusterNames} />
          ))
        ) : (
          filtered.length === 0 ? <EmptyRow /> : filtered.map(sig => (
            <SignalRow key={sig.id} signal={sig} isSelected={selectedId === sig.id} onSelect={setSelectedId} clusterNames={clusterNames} />
          ))
        )}
      </div>
    </div>
  );
}

/* ═══════════════════ SUB-COMPONENTS ═══════════════════ */

function Chip({ label, value, color }: { label: string; value: number; color: string }) {
  return (
    <div className="text-center">
      <p className="text-[9px] text-gray-500 uppercase">{label}</p>
      <p className={`text-sm font-black tabular-nums ${color}`}>{value}</p>
    </div>
  );
}

function EmptyRow() {
  return (
    <div className="flex items-center justify-center py-10">
      <p className="text-xs text-gray-600">No signals match current filters</p>
    </div>
  );
}

/* ── Top Card ── */

function TopCard({ signal, rank, clusterNames }: { signal: any; rank: number; clusterNames: Record<string, string> }) {
  const sev = SEV[signal.severity] || SEV.WEAK;
  const dir = DIR[signal.direction] || DIR.NEUTRAL;
  const DirIcon = dir.icon;
  const TypeIcon = TYPE_ICONS[signal.signal_type] || Zap;
  const stCfg = STAT[signal.status] || STAT.detected;
  const alignStatus = signal.alignment?.status || 'neutral';
  const alignCfg = ALIGN_CFG[alignStatus] || ALIGN_CFG.neutral;
  const AlignIcon = alignCfg.icon;
  const clusterDisplayName = signal.cluster_id ? (clusterNames[signal.cluster_id] || signal.cluster_id) : '';

  return (
    <div className={`bg-[#0a0e14] intelligence-dark rounded-xl p-4 border ${sev.border} relative`} data-testid={`top-signal-${rank}`}>
      <div className={`absolute top-3 right-3 flex items-center gap-1 text-[8px] font-bold ${alignCfg.color}`}>
        <AlignIcon className="w-2.5 h-2.5" /> {alignCfg.label}
      </div>

      <div className="flex items-center gap-2 mb-2">
        <span className="text-xs font-black text-gray-700">#{rank}</span>
        <span className="text-xs font-bold text-white">{signal.asset}</span>
        <ChainBadge chain={signal.chain} />
        <span className={`text-[8px] font-black uppercase ${stCfg.color}`}>{signal.status}</span>
        {signal.age_min > 0 && (
          <span className="text-[8px] text-gray-600 ml-auto">{ageStr(signal.age_min)}</span>
        )}
      </div>

      <div className="flex items-center gap-2 mb-1.5">
        <TypeIcon className={`w-4 h-4 ${dir.color}`} />
        <span className="text-sm font-bold text-white">{signal.signal_type.replace(/_/g, ' ')}</span>
      </div>

      <div className="flex items-center gap-3 mb-3">
        <DirIcon className={`w-3.5 h-3.5 ${dir.color}`} />
        <span className={`text-xs font-bold ${dir.color}`}>{dir.label}</span>
        {signal.cluster_count > 1 && (
          <span className="text-[9px] font-bold text-violet-400">
            {clusterDisplayName} &middot; Score {signal.cluster_score} &middot; {signal.cluster_count} signals
          </span>
        )}
      </div>

      <div className="grid grid-cols-3 gap-3 mb-2">
        <div>
          <p className="text-[9px] text-gray-600">Score</p>
          <p className={`text-lg font-black tabular-nums ${sev.color}`}>{signal.score}</p>
        </div>
        <div>
          <p className="text-[9px] text-gray-600">Confidence</p>
          <p className="text-lg font-black tabular-nums text-gray-300">{signal.confidence}%</p>
        </div>
        <div>
          <p className="text-[9px] text-gray-600">Move</p>
          {signal.expected_move ? (
            <>
              <p className="text-sm font-bold text-cyan-400">{signal.expected_move}</p>
              {signal.timeframe && <p className="text-[8px] text-gray-600">{signal.timeframe}</p>}
            </>
          ) : signal.token_amount > 0 && signal.token_symbol && signal.token_symbol !== 'ETH' ? (
            <>
              <p className="text-sm font-bold text-emerald-400">{formatTokenAmount(signal.token_amount, signal.token_symbol)}</p>
              {signal.tx_count > 1 && <p className="text-[8px] text-gray-600">{signal.tx_count} tx</p>}
            </>
          ) : signal.amount_eth > 0 ? (
            <>
              <p className="text-sm font-bold text-amber-400">{signal.amount_eth >= 1000 ? `${(signal.amount_eth / 1000).toFixed(1)}k` : signal.amount_eth.toFixed(1)} ETH</p>
              {signal.tx_count > 1 && <p className="text-[8px] text-gray-600">{signal.tx_count} tx</p>}
            </>
          ) : (
            <p className="text-sm font-bold text-gray-600">&mdash;</p>
          )}
        </div>
      </div>

      {/* Context badges */}
      {signal.context && <ContextBadges context={signal.context} />}

      {/* Invalidation */}
      {signal.invalidation && (
        <div className="mt-2 pt-2 border-t border-gray-800/40" data-testid={`top-signal-${rank}-invalidation`}>
          <div className="flex items-center gap-1.5">
            <Shield className="w-3 h-3 text-orange-400" />
            <span className="text-[9px] text-orange-300 font-bold uppercase">Invalidation</span>
          </div>
          <p className="text-[10px] text-gray-300 mt-0.5">{signal.invalidation.description}</p>
          {signal.invalidation.level && (
            <span className="text-[9px] text-red-400 font-bold">@ {signal.invalidation.level}</span>
          )}
        </div>
      )}

      <QualityBadge quality={signal.quality} />

      {/* Evidence: wallet & tx links */}
      {(signal.from_addr || signal.to_addr || signal.evidence) && (
        <div className="mt-2 pt-2 border-t border-gray-800/40" data-testid={`top-signal-${rank}-evidence`}>
          <div className="space-y-1">
            <span className="text-[9px] text-gray-500 font-bold uppercase">Evidence</span>
            {signal.from_addr && (
              <div className="flex items-center gap-1.5">
                <span className="text-[8px] text-gray-600 w-10">From</span>
                <a href={signal.explorer_from || `https://etherscan.io/address/${signal.from_addr}`} target="_blank" rel="noopener noreferrer"
                  className="text-[9px] text-violet-400 hover:text-violet-300 font-mono transition-colors" data-testid={`top-signal-${rank}-from-link`}>
                  {signal.from_addr.slice(0, 6)}...{signal.from_addr.slice(-4)}
                </a>
                <ExternalLink className="w-2.5 h-2.5 text-gray-600" />
              </div>
            )}
            {signal.to_addr && (
              <div className="flex items-center gap-1.5">
                <span className="text-[8px] text-gray-600 w-10">To</span>
                <a href={signal.explorer_to || `https://etherscan.io/address/${signal.to_addr}`} target="_blank" rel="noopener noreferrer"
                  className="text-[9px] text-violet-400 hover:text-violet-300 font-mono transition-colors" data-testid={`top-signal-${rank}-to-link`}>
                  {signal.to_addr.slice(0, 6)}...{signal.to_addr.slice(-4)}
                </a>
                <ExternalLink className="w-2.5 h-2.5 text-gray-600" />
              </div>
            )}
            {signal.tx_hash && (
              <div className="flex items-center gap-1.5">
                <span className="text-[8px] text-gray-600 w-10">TX</span>
                <a href={signal.explorer_url || `https://etherscan.io/tx/${signal.tx_hash}`} target="_blank" rel="noopener noreferrer"
                  className="text-[9px] text-violet-400 hover:text-violet-300 font-mono transition-colors" data-testid={`top-signal-${rank}-tx-link`}>
                  {signal.tx_hash.slice(0, 8)}...{signal.tx_hash.slice(-4)}
                </a>
                <ExternalLink className="w-2.5 h-2.5 text-gray-600" />
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

/* ── Cluster Wallets Expandable List ── */

function ClusterWalletsList({ wallets, clusterId, clusterName }: { wallets: string[]; clusterId: string; clusterName: string }) {
  const [copiedIdx, setCopiedIdx] = useState<number | null>(null);
  const copyAddr = (addr: string, idx: number) => {
    navigator.clipboard.writeText(addr).then(() => {
      setCopiedIdx(idx);
      setTimeout(() => setCopiedIdx(null), 1500);
    });
  };

  return (
    <div className="px-4 py-3 border-b border-violet-500/15 bg-violet-500/[0.03]" data-testid={`cluster-wallets-${clusterId}`}>
      <div className="flex items-center gap-2 mb-2.5">
        <Layers className="w-3.5 h-3.5 text-violet-400" />
        <span className="text-[10px] font-bold text-violet-400">{clusterName}</span>
        <span className="text-[9px] text-gray-500">{wallets.length} wallets</span>
      </div>
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-1.5">
        {wallets.map((addr, i) => (
          <div key={addr} className="flex items-center gap-1.5 group px-2 py-1 rounded bg-gray-900/40 hover:bg-gray-900/70 transition-colors" data-testid={`cluster-wallet-${i}`}>
            <span className="text-[9px] text-gray-600 tabular-nums w-5 shrink-0">{i + 1}.</span>
            <a
              href={`https://etherscan.io/address/${addr}`}
              target="_blank"
              rel="noopener noreferrer"
              className="text-[10px] text-violet-400 hover:text-violet-300 transition-colors font-mono truncate"
              data-testid={`cluster-wallet-link-${i}`}
            >
              {addr.slice(0, 6)}...{addr.slice(-4)}
            </a>
            <button
              onClick={(e) => { e.stopPropagation(); copyAddr(addr, i); }}
              className="opacity-0 group-hover:opacity-100 transition-opacity ml-auto shrink-0"
              data-testid={`cluster-wallet-copy-${i}`}
            >
              {copiedIdx === i
                ? <Check className="w-3 h-3 text-emerald-400" />
                : <Copy className="w-3 h-3 text-gray-600 hover:text-gray-400" />
              }
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}

/* ── Signal Row ── */

function SignalRow({ signal, isSelected, onSelect, clusterNames }: { signal: any; isSelected: boolean; onSelect: (id: string | null) => void; clusterNames: Record<string, string> }) {
  const [walletsExpanded, setWalletsExpanded] = useState(false);
  const sev = SEV[signal.severity] || SEV.WEAK;
  const dir = DIR[signal.direction] || DIR.NEUTRAL;
  const DirIcon = dir.icon;
  const TypeIcon = TYPE_ICONS[signal.signal_type] || Zap;
  const stCfg = STAT[signal.status] || STAT.detected;
  const riskC: Record<string, string> = { LOW: 'text-emerald-400', MODERATE: 'text-amber-400', ELEVATED: 'text-orange-400', HIGH: 'text-red-400' };
  const alignStatus = signal.alignment?.status || 'neutral';
  const alignCfg = ALIGN_CFG[alignStatus] || ALIGN_CFG.neutral;
  const AlignIcon = alignCfg.icon;
  const clusterDisplayName = signal.cluster_id ? (clusterNames[signal.cluster_id] || signal.cluster_id) : '';
  const hasClusterWallets = signal.signal_type === 'CLUSTER_ACTIVITY' && signal.cluster_wallets?.length > 0;

  const toggle = () => onSelect(isSelected ? null : signal.id);

  return (
    <>
      <div onClick={toggle}
        className={`grid grid-cols-[50px_38px_1fr_60px_50px_50px_65px_68px_100px_55px_45px] gap-1.5 px-4 py-2.5 border-b border-gray-800/20 hover:bg-white/[0.02] transition-colors cursor-pointer ${isSelected ? 'bg-white/[0.03]' : ''}`}
        data-testid={`signal-row-${signal.id}`}>
        <span className="text-xs font-bold text-white">{signal.asset}</span>

        {/* Chain badge */}
        <ChainBadge chain={signal.chain} />

        <div className="flex items-center gap-2 min-w-0">
          <TypeIcon className={`w-3 h-3 ${sev.color} shrink-0`} />
          <QualityWrapper quality={signal.quality} signalType={signal.signal_type}>
            <span className="text-[11px] text-gray-300 truncate">{signal.signal_type.replace(/_/g, ' ')}</span>
          </QualityWrapper>
          {signal.entity && (
            <span className="text-[9px] font-bold text-cyan-400 shrink-0 truncate max-w-[100px]" data-testid={`signal-entity-${signal.id}`}>
              {(() => {
                const raw = signal.entity;
                if (raw && raw.startsWith('Cluster ')) {
                  const cid = raw.replace('Cluster ', '');
                  return clusterNames[cid] || raw.replace(/^Cluster\s+/, '').replace(/^CS-/, 'Cluster #');
                }
                return raw;
              })()}
            </span>
          )}
          {signal.wallet_label && !signal.entity?.includes(signal.wallet_label) && (
            <span className="text-[8px] font-bold text-amber-400 shrink-0 truncate max-w-[80px]" data-testid={`signal-wallet-label-${signal.id}`}>
              {signal.wallet_label}
            </span>
          )}
          {signal.cluster_id && (
            hasClusterWallets ? (
              <button
                onClick={(e) => { e.stopPropagation(); setWalletsExpanded(!walletsExpanded); }}
                className="flex items-center gap-1 text-[8px] font-bold text-violet-400 hover:text-violet-300 shrink-0 px-1.5 py-0.5 rounded bg-violet-500/10 hover:bg-violet-500/20 transition-all"
                data-testid={`signal-cluster-expand-${signal.id}`}
              >
                {walletsExpanded ? <ChevronDown className="w-3 h-3" /> : <ChevronRight className="w-3 h-3" />}
                {clusterDisplayName} · {signal.wallet_count || signal.cluster_wallets?.length} wallets
              </button>
            ) : (
              <span className="text-[8px] font-bold text-violet-400 shrink-0" data-testid={`signal-cluster-id-${signal.id}`}>
                {clusterDisplayName}
              </span>
            )
          )}
          {signal.smart_money_score > 0 && (
            <span className={`text-[8px] font-bold shrink-0 ${
              signal.smart_money_score >= 0.7 ? 'text-emerald-400' :
              signal.smart_money_score >= 0.4 ? 'text-cyan-400' :
              'text-gray-500'
            }`} data-testid={`signal-sm-score-${signal.id}`}>
              {signal.smart_money_score >= 0.7 ? 'Smart Money' : signal.smart_money_score >= 0.4 ? 'Active Wallet' : ''}
            </span>
          )}
          {signal.cluster_count > 1 && (
            <span className="text-[8px] font-bold text-violet-400 shrink-0">{signal.cluster_count} signals</span>
          )}
          {signal.source === 'entity_intelligence' && signal.cluster_score > 0 && (
            <span className={`text-[8px] font-bold shrink-0 ${
              signal.cluster_score >= 70 ? 'text-violet-400' :
              signal.cluster_score >= 40 ? 'text-gray-400' :
              'text-gray-600'
            }`} data-testid={`signal-cluster-score-${signal.id}`}>
              {signal.cluster_score >= 70 ? 'High Cluster' : signal.cluster_score >= 40 ? 'Active Cluster' : 'Low Cluster'}
            </span>
          )}
        </div>

        <div className="flex items-center gap-1">
          <DirIcon className={`w-3 h-3 ${dir.color}`} />
          <span className={`text-[10px] font-bold ${dir.color}`}>{dir.label}</span>
        </div>

        <span className={`text-xs font-black tabular-nums ${sev.color}`}>{signal.score}</span>
        <span className="text-xs font-bold tabular-nums text-gray-400">{signal.confidence}%</span>
        <span className={`text-[9px] font-black uppercase ${stCfg.color}`}>{signal.status}</span>

        <div className="flex items-center gap-1" data-testid={`signal-alignment-${signal.id}`}>
          <AlignIcon className={`w-3 h-3 ${alignCfg.color}`} />
          <span className={`text-[9px] font-bold ${alignCfg.color}`}>{alignCfg.label}</span>
        </div>

        {/* Move + Window */}
        <span className="text-[10px] font-bold tabular-nums">
          {signal.expected_move ? (
            <>
              <span className="text-cyan-400">{signal.expected_move}</span>
              {signal.timeframe && <span className="text-gray-600 font-normal"> &middot; {signal.timeframe}</span>}
            </>
          ) : signal.token_amount > 0 && signal.token_symbol && signal.token_symbol !== 'ETH' ? (
            <>
              <span className="text-emerald-400">{formatTokenAmount(signal.token_amount, signal.token_symbol)}</span>
              {signal.usd_value > 0 && <span className="text-gray-500 font-normal text-[8px]"> ({formatUsd(signal.usd_value)})</span>}
            </>
          ) : signal.amount_eth > 0 ? (
            <>
              <span className="text-amber-400">{signal.amount_eth >= 1000 ? `${(signal.amount_eth / 1000).toFixed(1)}k` : signal.amount_eth.toFixed(1)} ETH</span>
              {signal.usd_value > 0 && <span className="text-gray-500 font-normal text-[8px]"> ({formatUsd(signal.usd_value)})</span>}
            </>
          ) : (
            <span className="text-gray-600">&mdash;</span>
          )}
        </span>

        <span className={`text-[10px] font-bold ${riskC[signal.risk] || 'text-gray-500'}`}>{signal.risk}</span>
        <span className="text-[9px] text-gray-500 tabular-nums font-bold" data-testid={`signal-age-${signal.id}`}>{ageStr(signal.age_min)}</span>
      </div>

      {/* ── Expanded Detail: Drivers + Invalidation + Context + Evolution ── */}
      {isSelected && (
        <div className="px-4 py-3 border-b border-gray-800/20 bg-white/[0.015]" data-testid={`signal-detail-${signal.id}`}>
          <div className="grid grid-cols-4 gap-4">
            {/* Column 1: Drivers + Entity Info */}
            <div>
              <span className="text-[9px] text-gray-400 font-bold uppercase tracking-wide">Drivers</span>
              <div className="mt-1.5 space-y-1">
                <DriversBlock drivers={signal.drivers} driverLabels={signal.driver_labels} />
              </div>
              {/* Entity detail for entity_intelligence signals */}
              {signal.source === 'entity_intelligence' && (
                <div className="mt-2 pt-2 border-t border-gray-800/30 space-y-1.5">
                  {signal.entity && (
                    <div className="flex items-center gap-2">
                      <span className="text-[8px] text-gray-500 uppercase w-14 shrink-0">Entity</span>
                      <span className="text-[10px] text-white font-bold">{signal.entity}</span>
                      {signal.entity_type && (
                        <span className="text-[8px] font-bold text-cyan-400 uppercase">{signal.entity_type}</span>
                      )}
                    </div>
                  )}
                  {(signal.from_addr || signal.to_addr) && (
                    <div className="flex items-center gap-2">
                      <span className="text-[8px] text-gray-500 uppercase w-14 shrink-0">Addrs</span>
                      {signal.from_addr && (
                        <a href={`https://etherscan.io/address/${signal.from_addr}`} target="_blank" rel="noreferrer"
                          className="text-[10px] text-violet-400 hover:text-violet-300 transition-colors" data-testid={`signal-from-addr-${signal.id}`}>
                          {signal.from_addr.slice(0, 6)}...{signal.from_addr.slice(-4)}
                        </a>
                      )}
                      {signal.from_addr && signal.to_addr && <span className="text-[8px] text-gray-600">&rarr;</span>}
                      {signal.to_addr && (
                        <a href={`https://etherscan.io/address/${signal.to_addr}`} target="_blank" rel="noreferrer"
                          className="text-[10px] text-violet-400 hover:text-violet-300 transition-colors" data-testid={`signal-to-addr-${signal.id}`}>
                          {signal.to_addr.slice(0, 6)}...{signal.to_addr.slice(-4)}
                        </a>
                      )}
                    </div>
                  )}
                  {(signal.from_entity || signal.to_entity) && (
                    <div className="flex items-center gap-2">
                      <span className="text-[8px] text-gray-500 uppercase w-14 shrink-0">Flow</span>
                      <span className="text-[10px] text-gray-300">{signal.from_entity || '?'}</span>
                      <span className="text-[8px] text-gray-600">&rarr;</span>
                      <span className="text-[10px] text-gray-300">{signal.to_entity || '?'}</span>
                    </div>
                  )}
                  {signal.amount_eth > 0 && (
                    <div className="flex items-center gap-2">
                      <span className="text-[8px] text-gray-500 uppercase w-14 shrink-0">Amount</span>
                      {signal.token_symbol && signal.token_symbol !== 'ETH' ? (
                        <span className="text-[10px] text-emerald-400 font-bold">{formatTokenAmount(signal.token_amount || 0, signal.token_symbol)}</span>
                      ) : (
                        <span className="text-[10px] text-amber-400 font-bold">{signal.amount_eth.toFixed(2)} ETH</span>
                      )}
                      {signal.usd_value > 0 && <span className="text-[9px] text-gray-400">{formatUsd(signal.usd_value)}</span>}
                      {signal.tx_count > 1 && (
                        <span className="text-[8px] text-gray-500">({signal.tx_count} tx)</span>
                      )}
                    </div>
                  )}
                  {signal.cluster_score > 0 && (
                    <div className="flex items-center gap-2">
                      <span className="text-[8px] text-gray-500 uppercase w-14 shrink-0">Cluster</span>
                      <span className={`text-[9px] font-bold ${
                        signal.cluster_score >= 70 ? 'text-violet-400' :
                        signal.cluster_score >= 40 ? 'text-cyan-400' :
                        'text-gray-500'
                      }`}>{signal.cluster_score}</span>
                      {clusterDisplayName && <span className="text-[9px] text-violet-400">{clusterDisplayName}</span>}
                    </div>
                  )}
                  {signal.detail && (
                    <p className="text-[9px] text-gray-400 mt-1 italic">{signal.detail}</p>
                  )}
                </div>
              )}
            </div>

            {/* Column 2: Invalidation + Evidence */}
            <div>
              <div className="flex items-center gap-1.5 mb-1">
                <Shield className="w-3 h-3 text-orange-400" />
                <span className="text-[9px] text-orange-300 font-bold uppercase">Invalidation</span>
              </div>
              <p className="text-[10px] text-gray-300">{signal.invalidation?.description || 'N/A'}</p>
              {signal.invalidation?.level && (
                <span className="text-[9px] text-red-400 font-bold">@ {signal.invalidation.level}</span>
              )}
              <p className="text-[8px] text-gray-500 mt-0.5">{signal.invalidation?.type?.replace(/_/g, ' ')}</p>

              {/* Evidence */}
              <EvidenceBlock evidence={signal.evidence} />

              {/* Provenance */}
              {signal.provenance && (
                <div className="mt-2">
                  <span className="text-[8px] text-gray-600 uppercase">Source: {signal.provenance.source}</span>
                </div>
              )}
            </div>

            {/* Column 3: Context + Target */}
            <div>
              {signal.context && (
                <div className="mb-2">
                  <span className="text-[9px] text-gray-500 font-bold uppercase">Market Context</span>
                  <ContextBadges context={signal.context} />
                </div>
              )}
              {signal.target && (
                <div>
                  <span className="text-[9px] text-gray-500 font-bold uppercase">Target</span>
                  <p className="text-[10px] text-gray-400 mt-0.5">{signal.target}</p>
                </div>
              )}
              {signal.freshness !== undefined && (
                <div className="mt-1 flex items-center gap-1">
                  <Clock className="w-2.5 h-2.5 text-gray-600" />
                  <span className="text-[9px] text-gray-600">Freshness: {Math.round(signal.freshness * 100)}%</span>
                </div>
              )}
            </div>

            {/* Column 4: Evolution Timeline */}
            <EvolutionTimeline signalId={signal.id} currentPhase={signal.status} />
          </div>
        </div>
      )}

      {/* ── Cluster Wallets Expandable ── */}
      {hasClusterWallets && walletsExpanded && (
        <ClusterWalletsList
          wallets={signal.cluster_wallets}
          clusterId={signal.cluster_id}
          clusterName={clusterDisplayName || signal.cluster_id}
        />
      )}
    </>
  );
}

/* ── Context Badges (Sprint 2) ── */

function ContextBadges({ context }: { context: any }) {
  if (!context) return null;

  const badges: { label: string; color: string }[] = [];

  const regimeLabels: Record<string, string> = {
    bull_trend: 'Bull Trend', bear_trend: 'Bear Trend',
    accumulation: 'Accumulation', distribution: 'Distribution',
    neutral_chop: 'Range', early_bull: 'Early Bull', capitulation: 'Capitulation',
  };
  if (context.regime) badges.push({ label: regimeLabels[context.regime] || context.regime.replace(/_/g, ' '), color: 'text-cyan-400 bg-cyan-500/8' });

  const riskColors: Record<string, string> = { low: 'text-emerald-400 bg-emerald-500/8', moderate: 'text-amber-400 bg-amber-500/8', elevated: 'text-orange-400 bg-orange-500/8', high: 'text-red-400 bg-red-500/8' };
  if (context.risk) badges.push({ label: `Risk: ${context.risk}`, color: riskColors[context.risk] || 'text-gray-400 bg-gray-500/8' });

  if (context.pressure && context.pressure !== 'neutral') {
    badges.push({ label: `Pressure: ${context.pressure}`, color: context.pressure === 'bullish' ? 'text-emerald-400 bg-emerald-500/8' : 'text-red-400 bg-red-500/8' });
  }

  if (context.ranking && context.ranking > 0) {
    badges.push({ label: `Opportunity #${context.ranking}`, color: 'text-violet-400 bg-violet-500/8' });
  }

  return (
    <div className="flex items-center gap-1.5 flex-wrap mt-1.5" data-testid="context-badges">
      {badges.map((b, i) => (
        <span key={i} className={`text-[8px] font-bold px-1.5 py-0.5 rounded ${b.color}`}>{b.label}</span>
      ))}
    </div>
  );
}

/* ── Cluster Group ── */

function ClusterGroup({ cluster, selectedId, onSelect, clusterNames }: { cluster: any; selectedId: string | null; onSelect: (id: string | null) => void; clusterNames: Record<string, string> }) {
  const [expanded, setExpanded] = useState(true);
  const dir = DIR[cluster.direction] || DIR.NEUTRAL;
  const DirIcon = dir.icon;
  const sigs = cluster.signals;
  const clusterScore = Math.min(cluster.maxScore + Math.round(Math.log(sigs.length) * 5), 100);
  const isReal = sigs.length > 1;
  const displayName = clusterNames[cluster.id] || `${sigs[0]?.asset || 'BTC'} ${cluster.direction} Cluster`;

  if (!isReal) return <SignalRow signal={sigs[0]} isSelected={selectedId === sigs[0].id} onSelect={onSelect} clusterNames={clusterNames} />;

  return (
    <div data-testid={`cluster-${cluster.id}`}>
      <div onClick={() => setExpanded(!expanded)}
        className="flex items-center gap-3 px-4 py-2.5 bg-violet-500/[0.04] border-b border-violet-500/10 cursor-pointer hover:bg-violet-500/[0.06] transition-colors"
        data-testid={`cluster-header-${cluster.id}`}>
        <Layers className="w-3.5 h-3.5 text-violet-400" />
        <span className="text-[10px] font-bold text-violet-400">{displayName}</span>
        <span className="text-[9px] font-black text-violet-300 tabular-nums">Score {clusterScore}</span>
        <DirIcon className={`w-3 h-3 ${dir.color}`} />
        <span className="text-[9px] text-gray-500">{sigs.length} signals</span>
        <div className="ml-auto flex items-center gap-2">
          <span className="text-[8px] text-gray-600">max: {cluster.maxScore}</span>
          <span className="text-[9px] text-gray-600">{expanded ? '\u25B2' : '\u25BC'}</span>
        </div>
      </div>
      {expanded && sigs.map((sig: any) => <SignalRow key={sig.id} signal={sig} isSelected={selectedId === sig.id} onSelect={onSelect} clusterNames={clusterNames} />)}
    </div>
  );
}

/* ── Quality Badge ── */

function QualityBadge({ quality }: { quality: any }) {
  if (!quality || quality.samples === 0) return null;
  return (
    <div className="mt-2 pt-2 border-t border-gray-800/40 flex items-center gap-3" data-testid="quality-badge">
      <span className="text-[9px] text-gray-600 uppercase">History</span>
      <span className="text-[9px] text-emerald-400 font-bold">{quality.success_rate}% win</span>
      <span className="text-[9px] text-cyan-400 font-bold">{quality.avg_move}% move</span>
      <span className="text-[9px] text-gray-600">{quality.samples}s</span>
    </div>
  );
}

/* ── Quality Tooltip ── */

function QualityWrapper({ quality, signalType, children }: { quality: any; signalType: string; children: React.ReactNode }) {
  const [show, setShow] = useState(false);

  if (!quality || quality.samples === 0) return <>{children}</>;

  return (
    <div className="relative inline-flex items-center gap-1"
      onMouseEnter={() => setShow(true)} onMouseLeave={() => setShow(false)}>
      {children}
      <Info className="w-2.5 h-2.5 text-gray-600 shrink-0" />
      {show && (
        <div className="absolute left-0 top-full mt-1 z-50 w-48 p-2.5 rounded-lg bg-[#0d1117] border border-gray-700 shadow-xl"
          data-testid={`quality-tooltip-${signalType}`}>
          <p className="text-[9px] font-bold text-gray-400 uppercase mb-1.5">Historical Performance</p>
          <div className="space-y-1">
            <div className="flex justify-between">
              <span className="text-[10px] text-gray-500">Success Rate</span>
              <span className="text-[10px] text-emerald-400 font-bold">{quality.success_rate}%</span>
            </div>
            <div className="flex justify-between">
              <span className="text-[10px] text-gray-500">Avg Move</span>
              <span className="text-[10px] text-cyan-400 font-bold">{quality.avg_move}%</span>
            </div>
            <div className="flex justify-between">
              <span className="text-[10px] text-gray-500">Samples</span>
              <span className="text-[10px] text-gray-400 font-bold">{quality.samples}</span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

/* ── Chain Badge ── */

function ChainBadge({ chain }: { chain?: string }) {
  const cfg = CHAIN_BADGE[chain || 'ethereum'] || CHAIN_BADGE.ethereum;
  return (
    <span className={`text-[8px] font-black ${cfg.text}`} data-testid={`chain-badge-${chain || 'ethereum'}`}>
      {cfg.label}
    </span>
  );
}

/* ── Drivers Block (handles both array and object formats) ── */

function DriversBlock({ drivers, driverLabels }: { drivers?: any; driverLabels?: string[] }) {
  if (!drivers) return <span className="text-[9px] text-gray-500 italic">No drivers</span>;

  // Entity intelligence: drivers is string[]
  if (Array.isArray(drivers)) {
    const catColors: Record<string, string> = {
      exchange: 'text-amber-400',
      whale: 'text-cyan-400',
      entity: 'text-emerald-400',
      structural: 'text-violet-400',
    };
    return (
      <>
        {drivers.map((d: string, i: number) => {
          const label = driverLabels?.[i] || d.replace(/_/g, ' ');
          const category = d.startsWith('cex_') || d.startsWith('exchange_') ? 'exchange' :
                           d.startsWith('whale_') ? 'whale' :
                           d.startsWith('fund_') || d.startsWith('mm_') || d.startsWith('smart_money') ? 'entity' :
                           'structural';
          return (
            <span key={d} className={`text-[9px] font-bold mr-2 ${catColors[category]}`}>
              {label}
            </span>
          );
        })}
      </>
    );
  }

  // Engine signals: drivers is {key: value}
  return (
    <>
      {Object.entries(drivers).map(([key, val]) => (
        <div key={key} className="flex items-center gap-2">
          <span className="text-[8px] text-gray-500 uppercase w-14 shrink-0">{key}</span>
          <span className="text-[10px] text-gray-300 font-medium">{String(val)}</span>
        </div>
      ))}
    </>
  );
}

/* ── Evidence Block (explorer links) ── */

function EvidenceBlock({ evidence }: { evidence?: any }) {
  if (!evidence) return null;
  const hasData = evidence.wallet || evidence.tx_hash || evidence.contract;
  if (!hasData) {
    return (
      <div className="mt-2">
        <span className="text-[9px] text-gray-500 italic">No on-chain evidence — engine analysis only</span>
      </div>
    );
  }

  const walletLink = evidence.wallet_link || (evidence.wallet ? `https://etherscan.io/address/${evidence.wallet}` : '');
  const txLink = evidence.tx_link || evidence.explorer_url || (evidence.tx_hash ? `https://etherscan.io/tx/${evidence.tx_hash}` : '');
  const contractLink = evidence.contract_link || (evidence.contract ? `https://etherscan.io/address/${evidence.contract}` : '');

  return (
    <div className="mt-2 space-y-1" data-testid="evidence-block">
      <span className="text-[9px] text-gray-400 font-bold uppercase">Evidence</span>
      {evidence.wallet && (
        <div className="flex items-center gap-1.5">
          <span className="text-[8px] text-gray-500 w-12">Wallet</span>
          <a href={walletLink} target="_blank" rel="noopener noreferrer"
            className="text-[9px] text-violet-400 hover:text-violet-300 transition-colors" data-testid="evidence-wallet-link">
            {evidence.wallet.slice(0, 6)}...{evidence.wallet.slice(-4)}
          </a>
        </div>
      )}
      {evidence.tx_hash && (
        <div className="flex items-center gap-1.5">
          <span className="text-[8px] text-gray-500 w-12">TX</span>
          <a href={txLink} target="_blank" rel="noopener noreferrer"
            className="text-[9px] text-violet-400 hover:text-violet-300 transition-colors" data-testid="evidence-tx-link">
            {evidence.tx_hash.slice(0, 6)}...{evidence.tx_hash.slice(-4)}
          </a>
        </div>
      )}
      {evidence.contract && (
        <div className="flex items-center gap-1.5">
          <span className="text-[8px] text-gray-500 w-12">Contract</span>
          <a href={contractLink} target="_blank" rel="noopener noreferrer"
            className="text-[9px] text-violet-400 hover:text-violet-300 transition-colors" data-testid="evidence-contract-link">
            {evidence.contract.slice(0, 6)}...{evidence.contract.slice(-4)}
          </a>
        </div>
      )}
      {evidence.chain && (
        <div className="flex items-center gap-1.5">
          <span className="text-[8px] text-gray-500 w-12">Chain</span>
          <ChainBadge chain={evidence.chain} />
        </div>
      )}
    </div>
  );
}

/* ── Evolution Timeline ── */

function EvolutionTimeline({ signalId, currentPhase }: { signalId: string; currentPhase: string }) {
  const [phases, setPhases] = useState<any[]>([]);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    fetch(`${API}/api/signals/${signalId}/evolution`)
      .then(r => r.json())
      .then(d => { if (d.ok) setPhases(d.phases || []); })
      .catch(() => {})
      .finally(() => setLoaded(true));
  }, [signalId]);

  const PHASE_ORDER = ['detected', 'forming', 'confirmed', 'cooling', 'invalidated'];
  const currentIdx = PHASE_ORDER.indexOf(currentPhase);

  function fmtTime(ts: string): string {
    if (!ts) return '';
    try {
      const d = new Date(ts);
      return `${d.getHours().toString().padStart(2, '0')}:${d.getMinutes().toString().padStart(2, '0')}`;
    } catch { return ''; }
  }

  return (
    <div data-testid={`evolution-${signalId}`}>
      <span className="text-[9px] text-gray-500 font-bold uppercase">Signal Evolution</span>

      {/* Phase progression bar */}
      <div className="flex items-center gap-0.5 mt-2 mb-2">
        {PHASE_ORDER.map((p, i) => {
          const isActive = i <= currentIdx;
          const isCurrent = p === currentPhase;
          const phaseColor = isActive
            ? (STAT[p]?.color || 'text-gray-400')
            : 'text-gray-700';
          return (
            <div key={p} className="flex items-center gap-0.5">
              <div className={`w-2 h-2 rounded-full ${isCurrent ? 'ring-1 ring-offset-1 ring-offset-[#0a0e14]' : ''} ${
                isActive ? (STAT[p]?.bg || 'bg-gray-500/20') + ' border ' + (STAT[p]?.color.replace('text-', 'border-') || 'border-gray-500') : 'bg-gray-800 border border-gray-700'
              }`} />
              {i < PHASE_ORDER.length - 1 && (
                <div className={`w-3 h-px ${isActive && i < currentIdx ? 'bg-gray-500' : 'bg-gray-800'}`} />
              )}
            </div>
          );
        })}
      </div>

      {/* Phase labels */}
      <div className="flex items-center gap-1 mb-2">
        {PHASE_ORDER.map((p, i) => {
          const isActive = i <= currentIdx;
          return (
            <span key={p} className={`text-[7px] font-bold uppercase ${isActive ? (STAT[p]?.color || 'text-gray-400') : 'text-gray-700'}`}>
              {p.slice(0, 4)}
            </span>
          );
        })}
      </div>

      {/* History entries */}
      {loaded && phases.length > 0 ? (
        <div className="space-y-1 mt-1.5">
          {phases.map((ph, i) => (
            <div key={i} className="flex items-center gap-2">
              <span className="text-[9px] text-gray-500 tabular-nums w-10">{fmtTime(ph.timestamp)}</span>
              <div className={`w-1.5 h-1.5 rounded-full ${STAT[ph.phase]?.bg || 'bg-gray-700'}`} />
              <span className={`text-[9px] font-bold ${STAT[ph.phase]?.color || 'text-gray-500'}`}>{ph.phase}</span>
              <span className="text-[8px] text-gray-600 tabular-nums">s:{ph.score}</span>
            </div>
          ))}
        </div>
      ) : loaded ? (
        <p className="text-[8px] text-gray-700 mt-1">First observation — no transitions yet</p>
      ) : (
        <Loader2 className="w-3 h-3 animate-spin text-gray-600 mt-1" />
      )}
    </div>
  );
}

export default SignalsTerminal;
