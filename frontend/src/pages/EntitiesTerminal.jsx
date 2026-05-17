/**
 * Entities Intelligence Terminal — Phase E-UI (Platform Style)
 * Uses IntelligenceBlock pattern from CEX Flow / Token Intelligence
 */
import { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Layers, Building, PieChart, Activity, Eye, Users,
  TrendingUp, TrendingDown, Fingerprint, Search,
  RefreshCw, ChevronRight, ChevronDown, Shield, Zap, GitBranch,
  BarChart3, ArrowUpRight, Target, ArrowLeftRight, Gauge,
  Package, ExternalLink
} from 'lucide-react';
import { IntelligenceBlock } from '../components/intelligence';

const API = process.env.REACT_APP_BACKEND_URL;

const shortAddr = (a) => a ? `${a.slice(0, 6)}...${a.slice(-4)}` : '';

function fmt(v) {
  if (!v && v !== 0) return '$0';
  const a = Math.abs(v);
  if (a >= 1e9) return `$${(v / 1e9).toFixed(2)}B`;
  if (a >= 1e6) return `$${(v / 1e6).toFixed(2)}M`;
  if (a >= 1e3) return `$${(v / 1e3).toFixed(1)}K`;
  return `$${v.toFixed(0)}`;
}

const TYPE_ICONS = { exchange: Building, protocol: Layers, fund: PieChart, market_maker: Activity, whale: Eye };

const BEH_COLORS = {
  accumulation: 'text-emerald-600',
  distribution: 'text-red-600',
  market_making: 'text-blue-600',
  liquidity_provision: 'text-cyan-600',
  treasury: 'text-amber-600',
  mixed: 'text-gray-500',
};

const BEH_DARK = {
  accumulation: 'text-emerald-400',
  distribution: 'text-red-400',
  market_making: 'text-blue-400',
  liquidity_provision: 'text-cyan-400',
  treasury: 'text-amber-400',
  mixed: 'text-gray-400',
};

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
// HERO: Entities Overview (dark)
// ═══════════════════════════════════════════
function EntitiesHero({ entities, behaviours, loading }) {
  if (loading && !entities.length) return <Skeleton dark />;

  const typeDistrib = {};
  entities.forEach(e => {
    const t = e.type || 'unknown';
    typeDistrib[t] = (typeDistrib[t] || 0) + 1;
  });

  const behDistrib = {};
  Object.values(behaviours).forEach(b => {
    const t = b.behaviour_type || 'unknown';
    behDistrib[t] = (behDistrib[t] || 0) + 1;
  });

  const avgConf = Object.values(behaviours).length
    ? (Object.values(behaviours).reduce((s, b) => s + (b.confidence || 0), 0) / Object.values(behaviours).length * 100)
    : 0;

  return (
    <IntelligenceBlock dark testId="entities-hero">
      <div className="text-[10px] font-bold text-gray-500 uppercase tracking-[0.2em] mb-2">Entities Intelligence</div>
      <div className="flex flex-col lg:flex-row lg:items-start lg:justify-between gap-6">
        <div className="flex-1">
          <div className="text-2xl font-black text-violet-400 mb-1" data-testid="total-entities">{entities.length} Entities Tracked</div>
          <p className="text-xs text-gray-400 mb-3">Actor Intelligence Layer — behaviour, flows, clusters, discovery</p>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <div className="text-[9px] font-bold text-gray-500 uppercase tracking-wider mb-1">By Type</div>
              {Object.entries(typeDistrib).sort((a, b) => b[1] - a[1]).map(([t, c]) => (
                <div key={t} className="flex items-center justify-between text-[11px]">
                  <span className="text-gray-400 capitalize">{t.replace(/_/g, ' ')}</span>
                  <span className="text-white font-bold">{c}</span>
                </div>
              ))}
            </div>
            <div>
              <div className="text-[9px] font-bold text-gray-500 uppercase tracking-wider mb-1">By Behaviour</div>
              {Object.entries(behDistrib).sort((a, b) => b[1] - a[1]).slice(0, 5).map(([t, c]) => (
                <div key={t} className="flex items-center justify-between text-[11px]">
                  <span className={`capitalize ${BEH_DARK[t] || 'text-gray-400'}`}>{t.replace(/_/g, ' ')}</span>
                  <span className="text-white font-bold">{c}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
        <div className="flex items-center gap-8">
          <div className="text-center">
            <div className="text-3xl font-black text-amber-400 tabular-nums" data-testid="avg-confidence">{avgConf.toFixed(0)}%</div>
            <div className="text-[9px] text-gray-500 uppercase tracking-wider mt-1">Avg Confidence</div>
          </div>
          <div className="text-center">
            <div className="text-3xl font-black text-cyan-400 tabular-nums">{Object.keys(typeDistrib).length}</div>
            <div className="text-[9px] text-gray-500 uppercase tracking-wider mt-1">Entity Types</div>
          </div>
        </div>
      </div>
    </IntelligenceBlock>
  );
}

// ═══════════════════════════════════════════
// ROW 2: TOP ENTITIES (light, clickable)
// ═══════════════════════════════════════════
function TopEntitiesBlock({ entities, behaviours, onSelect, loading }) {
  if (loading && !entities.length) return <Skeleton />;

  return (
    <IntelligenceBlock testId="top-entities-row">
      <div className="flex items-center gap-2 mb-4">
        <Users className="w-4 h-4 text-gray-400" />
        <h3 className="text-xs font-bold text-gray-400 uppercase tracking-[0.15em]">Top Entities</h3>
      </div>
      <div className="space-y-1">
        {entities.slice(0, 12).map((e, idx) => {
          const beh = behaviours[e.slug] || {};
          const Icon = TYPE_ICONS[e.type] || Building;
          const bc = BEH_COLORS[beh.behaviour_type] || BEH_COLORS.mixed;
          return (
            <button
              key={e.slug}
              onClick={() => onSelect(e.slug)}
              className="w-full flex items-center gap-3 p-3 rounded-xl hover:bg-gray-50 transition-all group text-left"
              data-testid={`entity-row-${e.slug}`}
            >
              <span className="text-xs text-gray-400 w-5 shrink-0 tabular-nums">{idx + 1}</span>
              <div className="w-8 h-8 rounded-lg bg-gray-100 flex items-center justify-center shrink-0">
                <Icon className="w-4 h-4 text-gray-500" />
              </div>
              <div className="flex-1">
                <div className="text-sm font-bold text-gray-900 group-hover:text-violet-600 transition-colors">{e.name?.replace(/_/g, ' ')}</div>
                <div className="text-[10px] text-gray-400 capitalize">{(e.type || '').replace(/_/g, ' ')} &middot; {e.address_count || 0} addresses</div>
              </div>
              {beh.behaviour_type && beh.behaviour_type !== 'unknown' && (
                <span className={`text-[10px] font-bold capitalize ${bc}`}>
                  {(beh.behaviour_type || '').replace(/_/g, ' ')}
                </span>
              )}
              {beh.confidence > 0 && (
                <span className="text-xs text-gray-400 tabular-nums">{(beh.confidence * 100).toFixed(0)}%</span>
              )}
              <ArrowUpRight className="w-3.5 h-3.5 text-gray-300 group-hover:text-violet-500 shrink-0 transition-colors" />
            </button>
          );
        })}
      </div>
    </IntelligenceBlock>
  );
}

// ═══════════════════════════════════════════
// ROW 3: BEHAVIOUR DISTRIBUTION (light)
// ═══════════════════════════════════════════
function BehaviourBlock({ behaviours, loading }) {
  if (loading) return <Skeleton />;

  const distrib = {};
  Object.values(behaviours).forEach(b => {
    const t = b.behaviour_type || 'unknown';
    if (!distrib[t]) distrib[t] = { count: 0, totalConf: 0 };
    distrib[t].count += 1;
    distrib[t].totalConf += b.confidence || 0;
  });
  const total = Object.values(distrib).reduce((s, d) => s + d.count, 0) || 1;

  return (
    <IntelligenceBlock testId="behaviour-distribution">
      <div className="flex items-center gap-2 mb-4">
        <Fingerprint className="w-4 h-4 text-gray-400" />
        <h3 className="text-xs font-bold text-gray-400 uppercase tracking-[0.15em]">Behaviour Distribution</h3>
      </div>
      <div className="space-y-3">
        {Object.entries(distrib).sort((a, b) => b[1].count - a[1].count).map(([type, data]) => {
          const pctVal = (data.count / total * 100).toFixed(0);
          const avgConf = (data.totalConf / data.count * 100).toFixed(0);
          const bc = BEH_COLORS[type] || BEH_COLORS.mixed;
          const barColor = bc.includes('emerald') ? '#059669' : bc.includes('red') ? '#dc2626' : bc.includes('blue') ? '#2563eb' : bc.includes('cyan') ? '#0891b2' : bc.includes('amber') ? '#d97706' : '#6b7280';
          return (
            <div key={type} data-testid={`behaviour-${type}`}>
              <div className="flex items-center justify-between mb-1">
                <span className={`text-xs font-bold capitalize ${bc}`}>{type.replace(/_/g, ' ')}</span>
                <div className="flex items-center gap-3">
                  <span className="text-[10px] text-gray-400">{avgConf}% avg</span>
                  <span className="text-sm font-black text-gray-900 tabular-nums">{data.count}</span>
                </div>
              </div>
              <div className="h-1.5 bg-gray-100 rounded-full overflow-hidden">
                <div className="h-full rounded-full"
                  style={{ width: `${pctVal}%`, backgroundColor: barColor }} />
              </div>
            </div>
          );
        })}
      </div>
    </IntelligenceBlock>
  );
}

// ═══════════════════════════════════════════
// ROW 3B: DISCOVERY CANDIDATES (light)
// ═══════════════════════════════════════════
function DiscoveryBlock({ discovery, loading }) {
  const [expandedIdx, setExpandedIdx] = useState(null);
  if (loading) return <Skeleton />;

  return (
    <IntelligenceBlock testId="discovery-candidates">
      <div className="flex items-center gap-2 mb-4">
        <Search className="w-4 h-4 text-gray-400" />
        <h3 className="text-xs font-bold text-gray-400 uppercase tracking-[0.15em]">Discovery Candidates</h3>
      </div>
      {(!discovery || discovery.length === 0) ? (
        <p className="text-sm text-gray-400 text-center py-4">No candidates yet</p>
      ) : (
        <div className="space-y-3">
          {discovery.slice(0, 6).map((c, i) => {
            const hasWallets = c.wallet_addresses && c.wallet_addresses.length > 0;
            const isExpanded = expandedIdx === i;
            return (
              <div key={i} className="py-2.5" data-testid={`discovery-${i}`}>
                <div
                  className={`flex items-center justify-between mb-1 ${hasWallets ? 'cursor-pointer hover:bg-gray-50 -mx-2 px-2 py-1 rounded' : ''}`}
                  onClick={() => hasWallets && setExpandedIdx(isExpanded ? null : i)}
                >
                  <div className="flex items-center gap-2">
                    {hasWallets && (isExpanded
                      ? <ChevronDown className="w-3 h-3 text-gray-400" />
                      : <ChevronRight className="w-3 h-3 text-gray-400" />
                    )}
                    <div>
                      <div className="text-xs font-bold text-gray-900 capitalize">{(c.candidate_type || '').replace(/_/g, ' ')}</div>
                      <div className="text-[10px] text-gray-400 truncate max-w-[180px]">{(c.cluster_id || '?').replace(/_/g, ' ')}</div>
                    </div>
                  </div>
                  <div className="flex items-center gap-3">
                    <span className="text-[10px] text-gray-400">{c.wallets || c.wallet_count || 0} wallets</span>
                    <span className={`text-sm font-black tabular-nums ${(c.discovery_score || 0) >= 0.7 ? 'text-emerald-600' : 'text-gray-500'}`}>
                      {((c.discovery_score || 0) * 100).toFixed(0)}%
                    </span>
                  </div>
                </div>
                {isExpanded && c.wallet_addresses && (
                  <div className="mt-1 ml-6 space-y-0.5 pl-3 border-l-2 border-violet-500/20" data-testid={`discovery-wallets-${i}`}>
                    {c.wallet_addresses.map((addr, wi) => (
                      <div key={addr} className="flex items-center gap-2 py-0.5 group/dw">
                        <span className="text-[9px] text-gray-500 tabular-nums w-3">{wi + 1}.</span>
                        <a href={`https://etherscan.io/address/${addr}`} target="_blank" rel="noopener noreferrer"
                          className="text-[10px] text-violet-500 hover:text-violet-700 font-mono transition-colors" data-testid={`discovery-wallet-link-${i}-${wi}`}>
                          {shortAddr(addr)}
                        </a>
                        <a href={`https://etherscan.io/address/${addr}`} target="_blank" rel="noopener noreferrer"
                          className="opacity-0 group-hover/dw:opacity-100 transition-opacity">
                          <ExternalLink className="w-2.5 h-2.5 text-gray-400 hover:text-blue-500" />
                        </a>
                      </div>
                    ))}
                  </div>
                )}
                {c.signals && c.signals.length > 0 && (
                  <div className="mt-1.5 flex flex-wrap gap-1" data-testid={`discovery-signals-${i}`}>
                    {c.signals.slice(0, 3).map((sig, j) => (
                      <span key={j} className="text-[9px] text-gray-500 bg-gray-100 px-1.5 py-0.5 rounded">{sig}</span>
                    ))}
                  </div>
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
// ROW 4: CLUSTER COVERAGE (light)
// ═══════════════════════════════════════════
function ClusterBlock({ clusters, loading }) {
  if (loading) return <Skeleton />;

  const entities = clusters?.entities || [];
  const totalWallets = clusters?.total_discovered || 0;
  const totalClusters = entities.reduce((sum, e) => sum + (e.cluster_count || 0), 0);

  return (
    <IntelligenceBlock testId="cluster-coverage">
      <div className="flex items-center gap-2 mb-4">
        <GitBranch className="w-4 h-4 text-gray-400" />
        <h3 className="text-xs font-bold text-gray-400 uppercase tracking-[0.15em]">Cluster Coverage</h3>
      </div>
      <div className="grid grid-cols-3 gap-4 mb-4">
        <div>
          <div className="text-[9px] text-gray-500 uppercase tracking-wider">Clusters</div>
          <div className="text-xl font-black text-gray-900 tabular-nums">{totalClusters}</div>
        </div>
        <div>
          <div className="text-[9px] text-gray-500 uppercase tracking-wider">Wallets</div>
          <div className="text-xl font-black text-cyan-600 tabular-nums">{totalWallets}</div>
        </div>
        <div>
          <div className="text-[9px] text-gray-500 uppercase tracking-wider">Entities</div>
          <div className="text-xl font-black text-violet-600 tabular-nums">{entities.length}</div>
        </div>
      </div>
      {entities.length > 0 && (
        <div className="space-y-1.5">
          {entities.slice(0, 5).map((e, i) => (
            <div key={i} className="py-1.5 border-b border-gray-100 last:border-0">
              <div className="flex items-center justify-between text-[11px]">
                <span className="text-gray-700 font-medium">{(e.name || e.entity_name || e.slug || e.entity_slug || '').replace(/_/g, ' ')}</span>
                <div className="flex items-center gap-3">
                  <span className="text-gray-400">{e.cluster_count || 0} clusters</span>
                  <span className="text-cyan-600 font-bold tabular-nums">{e.total_discovered || e.total_wallets || 0} wallets</span>
                </div>
              </div>
              {e.wallet_addresses?.length > 0 && (
                <div className="flex items-center gap-2 mt-0.5">
                  {e.wallet_addresses.slice(0, 3).map((w, wi) => (
                    <a key={wi} href={`https://etherscan.io/address/${w}`} target="_blank" rel="noopener noreferrer"
                      className="no-underline text-[9px] flex items-center gap-0.5 text-violet-400 hover:text-violet-300 font-mono transition-colors" data-testid={`cluster-wallet-${i}-${wi}`}>
                      {shortAddr(w)}
                      <ExternalLink className="w-2.5 h-2.5" />
                    </a>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </IntelligenceBlock>
  );
}

// ═══════════════════════════════════════════
// ACTOR PRESSURE MAP (dark) — bullish vs bearish
// ═══════════════════════════════════════════
function PressureMapBlock({ pressureMap, loading }) {
  if (loading && !pressureMap) return <Skeleton dark />;
  if (!pressureMap) return null;

  const IMPACT_COLORS = {
    SYSTEMIC: 'text-red-400',
    HIGH: 'text-amber-400',
    MEDIUM: 'text-blue-400',
    LOW: 'text-gray-400',
  };

  return (
    <IntelligenceBlock dark testId="pressure-map">
      <div className="flex items-center gap-2 mb-4">
        <Gauge className="w-4 h-4 text-violet-400" />
        <h3 className="text-xs font-bold text-gray-400 uppercase tracking-[0.15em]">Actor Market Pressure</h3>
        <div className="ml-auto flex items-center gap-3 text-[10px]">
          <span className="text-emerald-400">{pressureMap.bullish_count || 0} Bullish</span>
          <span className="text-red-400">{pressureMap.bearish_count || 0} Bearish</span>
          <span className="text-gray-500">{pressureMap.neutral_count || 0} Neutral</span>
        </div>
      </div>
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Bullish */}
        <div>
          <div className="text-[9px] font-bold text-emerald-400 uppercase tracking-wider mb-2">Bullish Actors</div>
          <div className="space-y-2">
            {(pressureMap.bullish_entities || []).slice(0, 5).map((e, i) => (
              <div key={i} data-testid={`bullish-actor-${i}`}>
                <div className="flex items-center justify-between text-[11px]">
                  <span className="text-white font-bold truncate max-w-[100px]">{e.name?.replace(/_/g, ' ')}</span>
                  <div className="flex items-center gap-2">
                    <span className="text-[9px] text-gray-500 tabular-nums">{e.impact_score || 0}</span>
                    <span className={`font-bold ${IMPACT_COLORS[e.impact] || 'text-gray-400'}`}>{e.impact}</span>
                  </div>
                </div>
                {e.strategy && e.strategy !== 'Mixed Strategy' && (
                  <div className="text-[9px] text-emerald-400 mt-0.5">{e.strategy}</div>
                )}
              </div>
            ))}
            {(pressureMap.bullish_entities || []).length === 0 && <div className="text-[10px] text-gray-600">No bullish actors</div>}
          </div>
        </div>
        {/* Bearish */}
        <div>
          <div className="text-[9px] font-bold text-red-400 uppercase tracking-wider mb-2">Bearish Actors</div>
          <div className="space-y-2">
            {(pressureMap.bearish_entities || []).slice(0, 5).map((e, i) => (
              <div key={i} data-testid={`bearish-actor-${i}`}>
                <div className="flex items-center justify-between text-[11px]">
                  <span className="text-white font-bold truncate max-w-[100px]">{e.name?.replace(/_/g, ' ')}</span>
                  <div className="flex items-center gap-2">
                    <span className="text-[9px] text-gray-500 tabular-nums">{e.impact_score || 0}</span>
                    <span className={`font-bold ${IMPACT_COLORS[e.impact] || 'text-gray-400'}`}>{e.impact}</span>
                  </div>
                </div>
                {e.strategy && e.strategy !== 'Mixed Strategy' && (
                  <div className="text-[9px] text-red-400 mt-0.5">{e.strategy}</div>
                )}
              </div>
            ))}
            {(pressureMap.bearish_entities || []).length === 0 && <div className="text-[10px] text-gray-600">No bearish actors</div>}
          </div>
        </div>
        {/* Neutral (top 5) */}
        <div>
          <div className="text-[9px] font-bold text-gray-400 uppercase tracking-wider mb-2">Neutral Actors</div>
          <div className="space-y-2">
            {(pressureMap.neutral_entities || []).slice(0, 5).map((e, i) => (
              <div key={i} data-testid={`neutral-actor-${i}`}>
                <div className="flex items-center justify-between text-[11px]">
                  <span className="text-gray-300 font-bold truncate max-w-[100px]">{e.name?.replace(/_/g, ' ')}</span>
                  <div className="flex items-center gap-2">
                    <span className="text-[9px] text-gray-500 tabular-nums">{e.impact_score || 0}</span>
                    <span className={`font-bold ${IMPACT_COLORS[e.impact] || 'text-gray-400'}`}>{e.impact}</span>
                  </div>
                </div>
                {e.strategy && e.strategy !== 'Mixed Strategy' && (
                  <div className="text-[9px] text-gray-400 mt-0.5">{e.strategy}</div>
                )}
              </div>
            ))}
          </div>
        </div>
      </div>
    </IntelligenceBlock>
  );
}

// ═══════════════════════════════════════════
// ACTOR INTERACTIONS (light) — capital routing
// ═══════════════════════════════════════════
function ActorFlowsBlock({ actorFlows, loading }) {
  const [expandedFlow, setExpandedFlow] = useState(null);
  if (loading && !actorFlows) return <Skeleton />;
  if (!actorFlows) return null;

  const interactions = actorFlows.interactions || [];
  if (interactions.length === 0) return null;

  const TYPE_COLORS = {
    exchange_flow: 'text-amber-600',
    dex_flow: 'text-emerald-600',
    bridge_flow: 'text-cyan-600',
    entity_to_entity: 'text-violet-600',
  };

  return (
    <IntelligenceBlock testId="actor-flows">
      <div className="flex items-center gap-2 mb-4">
        <ArrowLeftRight className="w-4 h-4 text-gray-400" />
        <h3 className="text-xs font-bold text-gray-400 uppercase tracking-[0.15em]">Actor Interactions</h3>
        <span className="text-[10px] text-gray-400 ml-auto">{interactions.length} flows</span>
      </div>
      <div className="space-y-1.5">
        {interactions.slice(0, 10).map((flow, i) => {
          const hasWallets = (flow.from_wallets?.length > 0) || (flow.to_wallets?.length > 0);
          const isExpanded = expandedFlow === i;
          return (
            <div key={i} data-testid={`actor-flow-${i}`}>
              <div
                className={`flex items-center justify-between py-1.5 text-[11px] ${hasWallets ? 'cursor-pointer hover:bg-gray-50 -mx-2 px-2 rounded' : ''}`}
                onClick={() => hasWallets && setExpandedFlow(isExpanded ? null : i)}
              >
                <div className="flex items-center gap-2 flex-1 min-w-0">
                  {hasWallets && (isExpanded
                    ? <ChevronDown className="w-3 h-3 text-gray-400 shrink-0" />
                    : <ChevronRight className="w-3 h-3 text-gray-400 shrink-0" />
                  )}
                  <span className="text-gray-900 font-bold truncate max-w-[100px]">{flow.from_name?.replace(/_/g, ' ')}</span>
                  <ChevronRight className="w-3 h-3 text-gray-300 shrink-0" />
                  <span className="text-gray-900 font-bold truncate max-w-[100px]">{flow.to_name?.replace(/_/g, ' ')}</span>
                </div>
                <div className="flex items-center gap-3 shrink-0">
                  <span className={`text-[10px] capitalize ${TYPE_COLORS[flow.type] || 'text-gray-400'}`}>
                    {(flow.type || '').replace(/_/g, ' ')}
                  </span>
                  <span className="text-gray-600 font-bold tabular-nums">{flow.label || ''}</span>
                </div>
              </div>
              {isExpanded && (
                <div className="ml-6 pb-2 grid grid-cols-2 gap-3">
                  {flow.from_wallets?.length > 0 && (
                    <div className="space-y-0.5 pl-3 border-l-2 border-amber-500/20" data-testid={`actor-from-wallets-${i}`}>
                      <div className="text-[9px] text-gray-400 font-bold uppercase">{flow.from_name?.replace(/_/g, ' ')}</div>
                      {flow.from_wallets.map((addr, wi) => (
                        <div key={addr} className="flex items-center gap-1.5 group/aw">
                          <a href={`https://etherscan.io/address/${addr}`} target="_blank" rel="noopener noreferrer"
                            className="text-[10px] text-violet-500 hover:text-violet-700 font-mono transition-colors">
                            {shortAddr(addr)}
                          </a>
                          <a href={`https://etherscan.io/address/${addr}`} target="_blank" rel="noopener noreferrer"
                            className="opacity-0 group-hover/aw:opacity-100 transition-opacity">
                            <ExternalLink className="w-2.5 h-2.5 text-gray-400" />
                          </a>
                        </div>
                      ))}
                    </div>
                  )}
                  {flow.to_wallets?.length > 0 && (
                    <div className="space-y-0.5 pl-3 border-l-2 border-emerald-500/20" data-testid={`actor-to-wallets-${i}`}>
                      <div className="text-[9px] text-gray-400 font-bold uppercase">{flow.to_name?.replace(/_/g, ' ')}</div>
                      {flow.to_wallets.map((addr, wi) => (
                        <div key={addr} className="flex items-center gap-1.5 group/aw">
                          <a href={`https://etherscan.io/address/${addr}`} target="_blank" rel="noopener noreferrer"
                            className="text-[10px] text-violet-500 hover:text-violet-700 font-mono transition-colors">
                            {shortAddr(addr)}
                          </a>
                          <a href={`https://etherscan.io/address/${addr}`} target="_blank" rel="noopener noreferrer"
                            className="opacity-0 group-hover/aw:opacity-100 transition-opacity">
                            <ExternalLink className="w-2.5 h-2.5 text-gray-400" />
                          </a>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </IntelligenceBlock>
  );
}

// ═══════════════════════════════════════════
// RECENT OTC ACTIVITY (dark)
// ═══════════════════════════════════════════
function RecentOTCBlock({ otcData, loading }) {
  if (loading && !otcData) return null;
  const trades = otcData?.trades || [];
  if (trades.length === 0) return null;

  const confColor = (c) => c >= 0.6 ? 'text-red-400' : c >= 0.4 ? 'text-amber-400' : 'text-gray-400';

  return (
    <IntelligenceBlock dark testId="recent-otc">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <Package className="w-4 h-4 text-amber-400" />
          <h3 className="text-xs font-bold text-gray-400 uppercase tracking-[0.15em]">Recent OTC Activity</h3>
        </div>
        <span className="text-[10px] font-bold text-amber-400" data-testid="list-otc-count">{otcData.count || 0} detected</span>
      </div>
      <div className="space-y-2">
        {trades.slice(0, 5).map((t, i) => (
          <div key={i} className="py-1.5 border-b border-gray-800 last:border-0 text-[11px]" data-testid={`list-otc-${i}`}>
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <span className="text-white font-bold">{t.asset}</span>
                <ChevronRight className="w-3 h-3 text-gray-600" />
                <span className="text-cyan-400 font-bold">{t.stablecoin}</span>
              </div>
              <div className="flex items-center gap-3">
                <span className="text-[10px] text-gray-500">{t.source_entity}</span>
                <span className="text-amber-400 font-black tabular-nums">{t.usd_value_fmt}</span>
                <span className={`font-bold ${confColor(t.confidence)}`}>{(t.confidence * 100).toFixed(0)}%</span>
              </div>
            </div>
            {(t.seller_wallets?.length > 0 || t.buyer_wallets?.length > 0) && (
              <div className="flex items-center gap-3 mt-1 text-[9px] text-gray-500">
                {t.seller_wallets?.slice(0, 2).map((w, wi) => (
                  <a key={wi} href={`https://etherscan.io/address/${w}`} target="_blank" rel="noopener noreferrer"
                    className="no-underline flex items-center gap-0.5 text-violet-400 hover:text-violet-300 font-mono transition-colors" data-testid={`otc-wallet-${i}-${wi}`}>
                    {shortAddr(w)}
                    <ExternalLink className="w-2.5 h-2.5" />
                  </a>
                ))}
              </div>
            )}
          </div>
        ))}
      </div>
    </IntelligenceBlock>
  );
}

// ═══════════════════════════════════════════
// DETECTED MARKET MAKERS (dark)
// ═══════════════════════════════════════════
function DetectedMMBlock({ mmData, loading }) {
  if (loading && !mmData) return null;
  const makers = mmData?.market_makers || [];
  if (makers.length === 0) return null;

  const typeColor = (t) => t === 'market_maker' ? 'text-red-400' : t === 'probable_mm' ? 'text-amber-400' : 'text-gray-500';
  const typeLabel = (t) => t === 'market_maker' ? 'Confirmed' : t === 'probable_mm' ? 'Probable' : 'Unlikely';

  return (
    <IntelligenceBlock dark testId="detected-mm">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <Activity className="w-4 h-4 text-violet-400" />
          <h3 className="text-xs font-bold text-gray-400 uppercase tracking-[0.15em]">Detected Market Makers</h3>
        </div>
        <span className="text-[10px] font-bold text-violet-400" data-testid="list-mm-count">{mmData.count || 0} detected</span>
      </div>
      <div className="space-y-2">
        {makers.slice(0, 5).map((m, i) => (
          <div key={i} className="py-2 border-b border-gray-800 last:border-0" data-testid={`list-mm-${i}`}>
            <div className="flex items-center justify-between mb-1">
              <div className="flex items-center gap-2">
                <span className="text-sm font-black text-white">{m.name?.replace(/_/g, ' ')}</span>
                <span className={`text-[9px] font-bold ${typeColor(m.type)}`}>{typeLabel(m.type)}</span>
              </div>
              <span className={`text-sm font-black tabular-nums ${m.score >= 0.7 ? 'text-red-400' : m.score >= 0.5 ? 'text-amber-400' : 'text-gray-400'}`}>
                {(m.score * 100).toFixed(0)}%
              </span>
            </div>
            <div className="flex items-center gap-3 text-[9px] text-gray-500">
              <span>bidir: {((m.signals?.bidirectional_flow || 0) * 100).toFixed(0)}%</span>
              <span>exch: {((m.signals?.exchange_density || 0) * 100).toFixed(0)}%</span>
              <span>stable: {((m.signals?.stablecoin_recycling || 0) * 100).toFixed(0)}%</span>
              <span>vel: {((m.signals?.velocity || 0) * 100).toFixed(0)}%</span>
            </div>
            {m.wallet_addresses?.length > 0 && (
              <div className="flex items-center gap-2 mt-1">
                {m.wallet_addresses.slice(0, 3).map((w, wi) => (
                  <a key={wi} href={`https://etherscan.io/address/${w}`} target="_blank" rel="noopener noreferrer"
                    className="no-underline text-[9px] flex items-center gap-0.5 text-violet-400 hover:text-violet-300 font-mono transition-colors" data-testid={`mm-wallet-${i}-${wi}`}>
                    {shortAddr(w)}
                    <ExternalLink className="w-2.5 h-2.5" />
                  </a>
                ))}
              </div>
            )}
          </div>
        ))}
      </div>
    </IntelligenceBlock>
  );
}

// ═══════════════════════════════════════════
// MAIN PAGE
// ═══════════════════════════════════════════
export default function EntitiesPage({ _embeddedOnSelect }) {
  const navigate = useNavigate();
  const [entities, setEntities] = useState([]);
  const [behaviours, setBehaviours] = useState({});
  const [discovery, setDiscovery] = useState([]);
  const [clusters, setClusters] = useState(null);
  const [pressureMap, setPressureMap] = useState(null);
  const [actorFlows, setActorFlows] = useState(null);
  const [otcData, setOtcData] = useState(null);
  const [mmData, setMmData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [listRes, behRes, discRes, clRes, pmRes, afRes, otcRes, mmRes] = await Promise.allSettled([
        fetch(`${API}/api/entities/v2/list?limit=50`).then(r => r.json()),
        fetch(`${API}/api/entities/v2/behaviour/overview`).then(r => r.json()),
        fetch(`${API}/api/entities/v2/discovery`).then(r => r.json()),
        fetch(`${API}/api/entities/v2/clusters/overview`).then(r => r.json()),
        fetch(`${API}/api/entities/v2/global/pressure-map`).then(r => r.json()),
        fetch(`${API}/api/entities/v2/global/actor-flows`).then(r => r.json()),
        fetch(`${API}/api/intelligence/otc`).then(r => r.json()),
        fetch(`${API}/api/intelligence/market-makers`).then(r => r.json()),
      ]);
      if (listRes.status === 'fulfilled') setEntities(listRes.value?.entities || []);
      if (behRes.status === 'fulfilled') {
        const map = {};
        (behRes.value?.entities || []).forEach(e => { map[e.slug || e.entity_slug] = e; });
        setBehaviours(map);
      }
      if (discRes.status === 'fulfilled') setDiscovery(discRes.value?.candidates || []);
      if (clRes.status === 'fulfilled') setClusters(clRes.value);
      if (pmRes.status === 'fulfilled') setPressureMap(pmRes.value);
      if (afRes.status === 'fulfilled') setActorFlows(afRes.value);
      if (otcRes.status === 'fulfilled') setOtcData(otcRes.value);
      if (mmRes.status === 'fulfilled') setMmData(mmRes.value);
    } catch (e) {
      console.error('Failed:', e);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const filtered = search
    ? entities.filter(e => (e.name || '').toLowerCase().includes(search.toLowerCase()) || (e.slug || '').includes(search.toLowerCase()))
    : entities;

  const selectEntity = (slug) => {
    if (_embeddedOnSelect) _embeddedOnSelect(slug);
    else navigate(`/entity/${slug}`);
  };

  return (
    <div className="space-y-4" data-testid="entities-terminal">
      {/* Header */}
      <div className="flex items-center justify-end gap-3">
        <div className="relative">
          <input
            type="text" value={search} onChange={e => setSearch(e.target.value)}
            placeholder="Search entities..."
            className="px-3 py-1.5 text-xs bg-gray-50 rounded-lg text-gray-900 placeholder-gray-400 focus:outline-none w-48"
            data-testid="entity-search"
          />
        </div>
        <button onClick={load} disabled={loading}
          className="p-2 text-gray-400 hover:text-gray-700 transition-colors disabled:opacity-50"
          data-testid="refresh-btn">
          <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
        </button>
      </div>

      {/* Hero */}
      <EntitiesHero entities={entities} behaviours={behaviours} loading={loading} />

      {/* Row 1.5: Actor Market Pressure */}
      <PressureMapBlock pressureMap={pressureMap} loading={loading} />

      {/* Row 2: Top Entities */}
      <TopEntitiesBlock entities={filtered} behaviours={behaviours} onSelect={selectEntity} loading={loading} />

      {/* Row 2.5: Actor Interactions */}
      <ActorFlowsBlock actorFlows={actorFlows} loading={loading} />

      {/* Row 2.7: OTC + Market Makers */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <RecentOTCBlock otcData={otcData} loading={loading} />
        <DetectedMMBlock mmData={mmData} loading={loading} />
      </div>

      {/* Row 3: Behaviour + Discovery */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <BehaviourBlock behaviours={behaviours} loading={loading} />
        <DiscoveryBlock discovery={discovery} loading={loading} />
      </div>

      {/* Row 4: Cluster Coverage */}
      <ClusterBlock clusters={clusters} loading={loading} />
    </div>
  );
}
