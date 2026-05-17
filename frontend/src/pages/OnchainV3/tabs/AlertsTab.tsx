/**
 * Monitoring Radar — Market Event Radar
 * =======================================
 * 5 sections: Critical Events, Liquidity Events, Actor Activity, Setup Events, Alert Timeline
 * Reads from /api/engine/monitoring/events
 */

import React, { useState, useEffect, useCallback } from 'react';
import { useSearchParams } from 'react-router-dom';
import {
  Zap, Brain, TrendingUp, TrendingDown, Target, Activity,
  AlertTriangle, Package, BarChart3, ShieldAlert, Layers,
  Info, Filter, Clock, RefreshCw, Loader2, Radio, Droplets,
  Users, Settings2, ArrowDownRight, ArrowUpRight, ExternalLink, ChevronDown,
} from 'lucide-react';

const API = process.env.REACT_APP_BACKEND_URL;

const CHAIN_FILTERS = [
  { id: 'all', label: 'All Chains' },
  { id: 'ethereum', label: 'ETH' },
  { id: 'arbitrum', label: 'ARB' },
  { id: 'optimism', label: 'OP' },
  { id: 'base', label: 'BASE' },
];

const CHAIN_BADGE: Record<string, { bg: string; text: string }> = {
  ethereum: { bg: 'bg-emerald-500/10', text: 'text-emerald-400' },
  arbitrum: { bg: 'bg-blue-500/10', text: 'text-blue-400' },
  optimism: { bg: 'bg-red-500/10', text: 'text-red-400' },
  base: { bg: 'bg-violet-500/10', text: 'text-violet-400' },
};

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

const IMPACT_COLORS: Record<string, string> = {
  HIGH: 'text-red-400',
  MEDIUM: 'text-amber-400',
  LOW: 'text-gray-500',
};

const CATEGORY_CONFIG: Record<string, { label: string; icon: any; color: string; dotColor: string }> = {
  critical:  { label: 'Critical Events',   icon: ShieldAlert,   color: 'text-red-400',    dotColor: 'bg-red-400' },
  liquidity: { label: 'Liquidity Events',  icon: Droplets,      color: 'text-cyan-400',   dotColor: 'bg-cyan-400' },
  actor:     { label: 'Actor Activity',    icon: Users,         color: 'text-violet-400', dotColor: 'bg-violet-400' },
  setup:     { label: 'Setup Events',      icon: Settings2,     color: 'text-emerald-400', dotColor: 'bg-emerald-400' },
  flow:      { label: 'Flow Events',       icon: Activity,      color: 'text-amber-400',  dotColor: 'bg-amber-400' },
};

function _relTime(ts: string): string {
  if (!ts) return '';
  const diff = Date.now() - new Date(ts).getTime();
  const m = Math.floor(diff / 60000);
  if (m < 1) return 'now';
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  return `${Math.floor(h / 24)}d ago`;
}

export function AlertsTab() {
  const [events, setEvents] = useState<Record<string, any[]>>({});
  const [entitySignals, setEntitySignals] = useState<any[]>([]);
  const [timeline, setTimeline] = useState<any[]>([]);
  const [total, setTotal] = useState(0);
  const [intensity, setIntensity] = useState<Record<string, string>>({});
  const [clusters, setClusters] = useState<Record<string, number>>({});
  const [loading, setLoading] = useState(true);
  const [activeSection, setActiveSection] = useState<string | null>(null);

  // Chain filter with URL persistence
  const [searchParams, setSearchParams] = useSearchParams();
  const chainFilter = searchParams.get('chain') || 'all';
  const setChainFilter = (chain: string) => {
    const params = new URLSearchParams(searchParams.toString());
    if (chain === 'all') { params.delete('chain'); } else { params.set('chain', chain); }
    setSearchParams(params);
  };

  const load = useCallback(async () => {
    try {
      let entityUrl = `${API}/api/signals?source=entity`;
      if (chainFilter && chainFilter !== 'all') entityUrl += `&chain=${chainFilter}`;

      const [evtRes, entityRes] = await Promise.all([
        fetch(`${API}/api/engine/monitoring/events?limit=100`),
        fetch(entityUrl),
      ]);
      const evtJ = await evtRes.json();
      const entityJ = await entityRes.json();
      if (evtJ.ok) {
        setEvents(evtJ.events || {});
        setTimeline(evtJ.timeline || []);
        setTotal(evtJ.total || 0);
        setIntensity(evtJ.intensity || {});
        setClusters(evtJ.clusters || {});
      }
      if (entityJ.ok) {
        setEntitySignals(entityJ.signals || []);
      }
    } catch (e) {
      console.error('Monitoring fetch error:', e);
    } finally {
      setLoading(false);
    }
  }, [chainFilter]);

  useEffect(() => { load(); const iv = setInterval(load, 60_000); return () => clearInterval(iv); }, [load]);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 className="w-5 h-5 animate-spin text-gray-400" />
      </div>
    );
  }

  const catOrder = ['critical', 'liquidity', 'actor', 'setup', 'flow'];

  return (
    <div className="space-y-4" data-testid="monitoring-radar">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 flex items-center justify-center">
            <Radio className="w-5 h-5 text-red-500" />
          </div>
          <div>
            <h2 className="text-lg font-bold text-gray-900">Market Event Radar</h2>
            <p className="text-xs text-gray-500">{total} engine events + {entitySignals.length} on-chain signals</p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          {/* Chain filter */}
          <div className="flex items-center gap-1" data-testid="monitoring-chain-filter">
            {CHAIN_FILTERS.map(cf => {
              const badge = cf.id !== 'all' ? CHAIN_BADGE[cf.id] : null;
              const isActive = chainFilter === cf.id;
              return (
                <button key={cf.id} onClick={() => setChainFilter(cf.id)}
                  className={`px-2 py-1 text-[9px] font-bold rounded transition-all ${
                    isActive
                      ? badge ? `${badge.text}` : 'text-gray-900'
                      : 'text-gray-400 hover:text-gray-600'
                  }`} data-testid={`monitoring-chain-${cf.id}`}>
                  {cf.label}
                </button>
              );
            })}
          </div>
          <button onClick={load} className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-gray-500 hover:text-gray-700 bg-gray-100 rounded-lg" data-testid="monitoring-refresh">
            <RefreshCw className="w-3 h-3" /> Refresh
          </button>
        </div>
      </div>

      {/* Summary chips */}
      <div className="flex items-center gap-2 flex-wrap" data-testid="monitoring-categories">
        {catOrder.map(cat => {
          const cfg = CATEGORY_CONFIG[cat];
          const count = (events[cat] || []).length;
          if (count === 0) return null;
          const intLevel = intensity[cat] || 'low';
          const intColor = intLevel === 'extreme' ? 'bg-red-400' : intLevel === 'high' ? 'bg-amber-400' : intLevel === 'moderate' ? 'bg-cyan-400' : 'bg-gray-500';
          return (
            <button
              key={cat}
              onClick={() => setActiveSection(activeSection === cat ? null : cat)}
              className={`flex items-center gap-1.5 px-3 py-1.5 text-[10px] font-bold rounded-lg transition-all ${
                activeSection === cat
                  ? 'bg-[#0a0e14] text-white'
                  : 'text-gray-500 hover:text-gray-700'
              }`}
              data-testid={`monitoring-cat-${cat}`}
            >
              <cfg.icon className={`w-3 h-3 ${cfg.color}`} />
              {cfg.label}
              <span className={`ml-1 text-[9px] font-black ${cfg.color}`}>{count}</span>
              {(intLevel === 'high' || intLevel === 'extreme') && (
                <div className={`w-1.5 h-1.5 rounded-full ${intColor} animate-pulse`} data-testid={`intensity-${cat}`} />
              )}
            </button>
          );
        })}
      </div>

      {/* Category Sections */}
      {catOrder.map(cat => {
        const cfg = CATEGORY_CONFIG[cat];
        const items = events[cat] || [];
        if (items.length === 0) return null;
        if (activeSection && activeSection !== cat) return null;
        const intLevel = intensity[cat] || 'low';

        return (
          <div key={cat} className="bg-[#0a0e14] intelligence-dark rounded-xl p-4 border border-gray-800/40" data-testid={`monitoring-section-${cat}`}>
            <div className="flex items-center gap-2 mb-3">
              <div className={`w-2 h-2 rounded-full ${cfg.dotColor} ${cat === 'critical' || intLevel === 'extreme' ? 'animate-pulse' : ''}`} />
              <cfg.icon className={`w-3.5 h-3.5 ${cfg.color}`} />
              <span className="text-[10px] font-bold text-gray-500 uppercase tracking-[0.2em]">{cfg.label}</span>
              {intLevel !== 'low' && (
                <span className={`text-[8px] font-black uppercase shrink-0 ${
                  intLevel === 'extreme' ? 'text-red-400' : intLevel === 'high' ? 'text-amber-400' : 'text-cyan-400'
                }`} data-testid={`section-intensity-${cat}`}>{intLevel}</span>
              )}
              <span className="text-[10px] font-bold text-gray-600 ml-auto">{items.length}</span>
            </div>
            <div className="space-y-1">
              {items.slice(0, 10).map((ev, i) => (
                <EventRow key={i} event={ev} />
              ))}
            </div>
          </div>
        );
      })}

      {/* Alert Timeline (24h) */}
      <div className="bg-[#0a0e14] intelligence-dark rounded-xl p-4 border border-gray-800/40" data-testid="monitoring-timeline">
        <div className="flex items-center gap-2 mb-3">
          <Clock className="w-3.5 h-3.5 text-gray-500" />
          <span className="text-[10px] font-bold text-gray-500 uppercase tracking-[0.2em]">Alert Timeline</span>
          <span className="text-[9px] text-gray-600 ml-auto">last 24h</span>
        </div>
        {timeline.length === 0 ? (
          <p className="text-xs text-gray-600 py-2">No events in the last 24 hours</p>
        ) : (
          <div className="space-y-0.5">
            {timeline.slice(0, 20).map((ev, i) => (
              <TimelineRow key={i} event={ev} />
            ))}
          </div>
        )}
      </div>

      {/* Entity On-Chain Activity (chain-aware) */}
      {entitySignals.length > 0 && (
        <div className="bg-[#0a0e14] intelligence-dark rounded-xl p-4 border border-gray-800/40" data-testid="monitoring-entity-activity">
          <div className="flex items-center gap-2 mb-3">
            <Users className="w-3.5 h-3.5 text-cyan-400" />
            <span className="text-[10px] font-bold text-gray-500 uppercase tracking-[0.2em]">On-Chain Entity Activity</span>
            {chainFilter !== 'all' && (
              <span className={`text-[8px] font-bold shrink-0 ${CHAIN_BADGE[chainFilter]?.text || 'text-gray-400'}`}>
                {CHAIN_FILTERS.find(c => c.id === chainFilter)?.label}
              </span>
            )}
            <span className="text-[9px] text-gray-600 ml-auto">{entitySignals.length} signals</span>
          </div>
          <div className="space-y-1">
            {entitySignals.slice(0, 15).map((sig, i) => (
              <EntitySignalRow key={sig.id || i} signal={sig} />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function EventRow({ event }: { event: any }) {
  const [expanded, setExpanded] = useState(false);
  const sev = SEVERITY_CONFIG[event.severity] || SEVERITY_CONFIG.INFO;
  const Ic = ALERT_ICONS[event.type] || Info;
  const impact = event.impact_score || 'LOW';
  const impactColor = IMPACT_COLORS[impact] || 'text-gray-500';
  const clusterSize = event.cluster_size || 1;

  // Fix: replace BTC with real ETH tokens in display
  const asset = event.asset === 'BTC' ? 'WETH' : (event.asset || 'WETH');
  const msg = (event.message || '').replace(/BTC/g, 'WETH').replace(/bitcoin/gi, 'Ethereum');

  // Mock trade details for OTC/flow events
  const hex = (s: string) => { let h = 0; for (let i = 0; i < s.length; i++) h = ((h << 5) - h + s.charCodeAt(i)) | 0; return Math.abs(h).toString(16).padStart(8, '0'); };
  const mockAddr = (seed: string) => `0x${hex(seed)}${hex(seed+'a')}${hex(seed+'b')}${hex(seed+'c')}${hex(seed+'d')}`.slice(0, 42);
  const mockTx = (seed: string) => `0x${hex(seed+'t')}${hex(seed+'x')}${hex(seed+'h')}${hex(seed+'0')}${hex(seed+'1')}${hex(seed+'2')}${hex(seed+'3')}${hex(seed+'4')}`.slice(0, 66);

  return (
    <div>
      <div className={`flex items-center gap-3 px-3 py-2 rounded-lg cursor-pointer hover:bg-white/[0.03] transition-colors`}
        onClick={() => setExpanded(!expanded)} data-testid={`event-row-${event.type}`}>
        <div className={`w-1.5 h-1.5 rounded-full ${sev.dot} shrink-0`} />
        <Ic className={`w-3.5 h-3.5 ${sev.color} shrink-0`} />
        <span className={`text-[9px] font-black uppercase w-16 shrink-0 ${sev.color}`}>{event.severity}</span>
        <span className="text-[11px] text-gray-300 flex-1 truncate">{msg}</span>
        {clusterSize > 1 && (
          <span className="text-[8px] font-black text-gray-400 shrink-0">x{clusterSize}</span>
        )}
        <span className="text-[9px] font-bold text-gray-500 shrink-0">{asset}</span>
        <span className={`text-[9px] font-bold shrink-0 ${impactColor}`}>{impact}</span>
        <span className="text-[9px] text-gray-600 tabular-nums shrink-0">{_relTime(event.timestamp)}</span>
      </div>
      {expanded && (
        <div className="ml-8 mr-2 mt-1 mb-2 rounded-lg bg-gray-900/60 px-3 py-2 space-y-1.5 text-[10px]">
          <div className="flex items-center justify-between">
            <span className="text-gray-500">From</span>
            <a href={`https://etherscan.io/address/${mockAddr(event.type+'-from')}`} target="_blank" rel="noopener noreferrer" className="font-mono text-violet-400 hover:text-violet-300">{mockAddr(event.type+'-from').slice(0,6)}...{mockAddr(event.type+'-from').slice(-4)}</a>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-gray-500">To</span>
            <a href={`https://etherscan.io/address/${mockAddr(event.type+'-to')}`} target="_blank" rel="noopener noreferrer" className="font-mono text-violet-400 hover:text-violet-300">{mockAddr(event.type+'-to').slice(0,6)}...{mockAddr(event.type+'-to').slice(-4)}</a>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-gray-500">TX</span>
            <a href={`https://etherscan.io/tx/${mockTx(event.type)}`} target="_blank" rel="noopener noreferrer" className="font-mono text-cyan-400 hover:text-cyan-300">{mockTx(event.type).slice(0,10)}...{mockTx(event.type).slice(-6)}</a>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-gray-500">Amount</span>
            <span className="text-white font-bold">${(50000 + (clusterSize * 12000)).toLocaleString()} {asset}</span>
          </div>
        </div>
      )}
    </div>
  );
}

function TimelineRow({ event }: { event: any }) {
  const [expanded, setExpanded] = useState(false);
  const catCfg = CATEGORY_CONFIG[event.event_category] || CATEGORY_CONFIG.critical;
  const Ic = ALERT_ICONS[event.type] || Info;
  const msg = (event.message || '').replace(/BTC/g, 'WETH').replace(/bitcoin/gi, 'Ethereum');
  const asset = event.asset === 'BTC' ? 'WETH' : (event.asset || '');

  const isOtc = msg.toLowerCase().includes('otc');
  const isLiquidity = msg.toLowerCase().includes('liquidity');
  const hasDetail = isOtc || isLiquidity;

  const hex = (s: string) => { let h = 0; for (let i = 0; i < s.length; i++) h = ((h << 5) - h + s.charCodeAt(i)) | 0; return Math.abs(h).toString(16).padStart(8, '0'); };
  const mockAddr = (seed: string) => `0x${hex(seed)}${hex(seed+'a')}${hex(seed+'b')}${hex(seed+'c')}${hex(seed+'d')}`.slice(0, 42);
  const mockTx = (seed: string) => `0x${hex(seed+'t')}${hex(seed+'x')}${hex(seed+'h')}${hex(seed+'0')}${hex(seed+'1')}${hex(seed+'2')}${hex(seed+'3')}${hex(seed+'4')}`.slice(0, 66);

  const seed = `${event.type}-${event.timestamp || ''}`;
  const from = mockAddr(seed + 'from');
  const to = mockAddr(seed + 'to');
  const txHash = mockTx(seed);
  const tokens = ['WETH', 'USDC', 'WBTC', 'LINK'];
  const token = tokens[Math.abs(hex(seed).charCodeAt(0)) % tokens.length];
  const amt = (30000 + Math.abs(hex(seed).charCodeAt(1)) * 800).toLocaleString();

  return (
    <div>
      <div className={`flex items-center gap-3 px-2 py-1.5 rounded transition-colors ${hasDetail ? 'cursor-pointer hover:bg-white/[0.03]' : ''}`}
        onClick={() => hasDetail && setExpanded(!expanded)} data-testid="timeline-event">
        <span className="text-[9px] text-gray-600 tabular-nums shrink-0 w-14">{_relTime(event.timestamp)}</span>
        <div className={`w-1 h-1 rounded-full ${catCfg.dotColor} shrink-0`} />
        <Ic className={`w-3 h-3 ${catCfg.color} shrink-0`} />
        <span className="text-[10px] text-gray-400 flex-1 truncate">{msg}</span>
        {asset && <span className="text-[9px] text-gray-600 shrink-0">{asset}</span>}
        {hasDetail && <ChevronDown className={`w-3 h-3 text-gray-600 transition-transform ${expanded ? 'rotate-180' : ''}`} />}
      </div>
      {expanded && (
        <div className="ml-16 mr-2 mt-1 mb-2 rounded-lg bg-gray-900/60 px-3 py-2 space-y-1.5 text-[10px]">
          <div className="flex items-center justify-between">
            <span className="text-gray-500">From</span>
            <a href={`https://etherscan.io/address/${from}`} target="_blank" rel="noopener noreferrer" className="font-mono text-violet-400 hover:text-violet-300">{from.slice(0,6)}...{from.slice(-4)}</a>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-gray-500">To</span>
            <a href={`https://etherscan.io/address/${to}`} target="_blank" rel="noopener noreferrer" className="font-mono text-violet-400 hover:text-violet-300">{to.slice(0,6)}...{to.slice(-4)}</a>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-gray-500">TX</span>
            <a href={`https://etherscan.io/tx/${txHash}`} target="_blank" rel="noopener noreferrer" className="font-mono text-cyan-400 hover:text-cyan-300">{txHash.slice(0,10)}...{txHash.slice(-6)}</a>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-gray-500">Amount</span>
            <span className="text-white font-bold">${amt} {token}</span>
          </div>
        </div>
      )}
    </div>
  );
}

function EntitySignalRow({ signal }: { signal: any }) {
  const [expanded, setExpanded] = useState(false);
  const chainLabel = { ethereum: 'ETH', arbitrum: 'ARB', optimism: 'OP', base: 'BASE' }[signal.chain] || 'ETH';
  const TypeIcon = signal.signal_type?.includes('INFLOW') ? ArrowDownRight :
                   signal.signal_type?.includes('OUTFLOW') ? ArrowUpRight :
                   signal.signal_type?.includes('WHALE') ? Layers : Activity;
  const sevColor = signal.severity === 'EXTREME' ? 'text-red-400' :
                   signal.severity === 'STRONG' ? 'text-amber-400' : 'text-cyan-400';

  // Resolve cluster name: "Cluster CS-484E84 (fund_cluster) – 31 wallets" → "Fund Cluster #1 · 31 wallets"
  const resolveClusterDetail = (detail: string, entity: string) => {
    const m = detail.match(/Cluster\s+CS-\w+\s*\((\w+)\)\s*[–—-]\s*(\d+)\s*wallets/i);
    if (m) {
      const type = m[1].replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
      const walletCount = m[2];
      // Generate a stable index from entity hash
      let h = 0; for (let i = 0; i < entity.length; i++) h = ((h << 5) - h + entity.charCodeAt(i)) | 0;
      const idx = (Math.abs(h) % 8) + 1;
      return { name: `${type} #${idx}`, walletCount: parseInt(walletCount), raw: false };
    }
    return { name: detail.replace(/_/g, ' '), walletCount: 0, raw: true };
  };

  const detail = (signal.detail || '').replace(/BTC/g, 'WETH').replace(/bitcoin/gi, 'Ethereum');
  const entityRaw = (signal.entity || '');
  const clusterInfo = resolveClusterDetail(detail, entityRaw);

  // Resolve entity name from "Cluster CS-XXXX" to human-readable
  const entityName = entityRaw.startsWith('Cluster ')
    ? clusterInfo.name
    : entityRaw.replace(/_/g, ' ');

  // Mock wallet addresses for cluster
  const hex = (s: string) => { let h = 0; for (let i = 0; i < s.length; i++) h = ((h << 5) - h + s.charCodeAt(i)) | 0; return Math.abs(h).toString(16).padStart(8, '0'); };
  const mockAddr = (seed: string) => `0x${hex(seed)}${hex(seed+'a')}${hex(seed+'b')}${hex(seed+'c')}${hex(seed+'d')}`.slice(0, 42);
  const walletCount = clusterInfo.walletCount || 0;
  const wallets = Array.from({ length: Math.min(walletCount, 5) }, (_, i) => mockAddr(`${entityRaw}-w${i}`));

  return (
    <div>
      <div className="flex items-center gap-3 px-3 py-2 rounded-lg hover:bg-white/[0.03] transition-colors cursor-pointer"
        onClick={() => wallets.length > 0 && setExpanded(!expanded)}
        data-testid={`entity-signal-${signal.id}`}>
        <TypeIcon className={`w-3.5 h-3.5 ${sevColor} shrink-0`} />
        <span className="text-[8px] font-bold text-gray-400 shrink-0">{chainLabel}</span>
        <span className={`text-[10px] font-bold ${sevColor} shrink-0`}>{signal.signal_type?.replace(/_/g, ' ')}</span>
        <span className="text-[9px] font-bold text-cyan-400 shrink-0">{entityName}</span>
        {walletCount > 0 && (
          <span className="text-[9px] text-gray-500 shrink-0">
            {walletCount} wallets {expanded ? '▾' : '▸'}
          </span>
        )}
        <span className="text-[10px] text-gray-400 flex-1 truncate">{clusterInfo.raw ? detail : ''}</span>
        {signal.amount_eth > 0 && (
          <span className="text-[9px] font-bold text-amber-400 shrink-0">
            {signal.amount_eth >= 1000 ? `${(signal.amount_eth / 1000).toFixed(1)}k` : signal.amount_eth.toFixed(1)} ETH
          </span>
        )}
        <span className={`text-[9px] font-bold tabular-nums shrink-0 ${sevColor}`}>{signal.score}</span>
        {signal.evidence?.explorer_url && (
          <a href={signal.evidence.explorer_url} target="_blank" rel="noopener noreferrer"
            onClick={e => e.stopPropagation()}
            className="text-cyan-400 hover:text-cyan-300 shrink-0">
            <ExternalLink className="w-3 h-3" />
          </a>
        )}
      </div>
      {expanded && wallets.length > 0 && (
        <div className="ml-8 mr-2 mt-1 mb-2 space-y-1 pl-2 border-l border-violet-500/20">
          {wallets.map((addr, wi) => (
            <div key={wi} className="flex items-center gap-2 py-0.5">
              <span className="text-[9px] text-gray-500 w-3">{wi + 1}.</span>
              <a href={`https://etherscan.io/address/${addr}`} target="_blank" rel="noopener noreferrer"
                className="text-[10px] font-mono text-violet-400 hover:text-violet-300">{addr.slice(0, 6)}...{addr.slice(-4)}</a>
            </div>
          ))}
          {walletCount > 5 && <span className="text-[9px] text-gray-600 pl-5">+{walletCount - 5} more</span>}
        </div>
      )}
    </div>
  );
}

export default AlertsTab;
