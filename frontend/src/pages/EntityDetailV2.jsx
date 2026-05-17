/**
 * Entity Intelligence Terminal — Phase 10
 * Full analytical page for entity intelligence
 */
import { useState, useEffect, useCallback } from 'react';
import { Link, useParams, useNavigate } from 'react-router-dom';
import {
  ChevronLeft, Building, TrendingUp, TrendingDown, Activity,
  ArrowUpRight, ArrowDownRight, PieChart, Users, Coins,
  Target, Zap, Search, Layers, GitBranch, Eye, BarChart3,
  ArrowLeftRight, Shield, Fingerprint
} from 'lucide-react';
import { api } from '../api/client';

const API = '/api/entities/v2';

// ── Helpers ──
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

const BEHAVIOUR_COLORS = {
  accumulation: 'text-emerald-400',
  distribution: 'text-red-400',
  market_making: 'text-blue-400',
  liquidity_provision: 'text-cyan-400',
  treasury: 'text-amber-400',
  mixed: 'text-gray-400',
};

const ROLE_COLORS = {
  liquidity_token: 'text-cyan-400',
  accumulation_token: 'text-emerald-400',
  distribution_token: 'text-red-400',
  neutral_token: 'text-gray-500',
};

const TIER_COLORS = {
  high: 'border-emerald-500/30 bg-emerald-500/5',
  medium: 'border-amber-500/30 bg-amber-500/5',
  low: 'border-gray-500/30 bg-gray-500/5',
};

const LEVEL_COLORS = {
  known: 'text-emerald-400 bg-emerald-500/10 border-emerald-500/20',
  likely: 'text-blue-400 bg-blue-500/10 border-blue-500/20',
  possible: 'text-amber-400 bg-amber-500/10 border-amber-500/20',
  unknown: 'text-gray-400 bg-gray-500/10 border-gray-500/20',
};

// ═══════════════════════════════════════════
// CARD COMPONENT
// ═══════════════════════════════════════════
function Card({ title, icon: Icon, children, className = '' }) {
  return (
    <div className={`bg-[#0d0d15] border border-white/5 rounded-lg p-4 ${className}`} data-testid={`card-${title?.toLowerCase().replace(/\s+/g,'-')}`}>
      {title && (
        <div className="flex items-center gap-2 mb-3 pb-2 border-b border-white/5">
          {Icon && <Icon className="w-3.5 h-3.5 text-gray-500" />}
          <span className="text-xs font-medium text-gray-400 uppercase tracking-wider">{title}</span>
        </div>
      )}
      {children}
    </div>
  );
}

function Metric({ label, value, sub, color = 'text-white' }) {
  return (
    <div>
      <div className="text-[10px] text-gray-500 uppercase tracking-wide mb-0.5">{label}</div>
      <div className={`text-sm font-semibold ${color}`}>{value}</div>
      {sub && <div className="text-[10px] text-gray-600">{sub}</div>}
    </div>
  );
}

function Badge({ text, color = 'text-gray-400 bg-white/5 border-white/10' }) {
  return <span className={`px-2 py-0.5 text-[10px] font-medium rounded border ${color}`}>{text}</span>;
}

// ═══════════════════════════════════════════
// ENTITY HEADER
// ═══════════════════════════════════════════
function EntityHeader({ entity, behaviour, clusters }) {
  const typeIcons = { exchange: Building, protocol: Layers, fund: PieChart, market_maker: Activity, whale: Eye };
  const TypeIcon = typeIcons[entity?.type] || Building;
  const clusterCount = clusters?.total_discovered || 0;

  return (
    <div className="flex items-center justify-between" data-testid="entity-header">
      <div className="flex items-center gap-4">
        <div className="w-12 h-12 rounded-xl bg-white/5 border border-white/10 flex items-center justify-center">
          <TypeIcon className="w-6 h-6 text-gray-400" />
        </div>
        <div>
          <h1 className="text-xl font-bold text-white">{entity?.name}</h1>
          <div className="flex items-center gap-2 mt-1">
            <Badge text={entity?.type?.toUpperCase()} />
            <Badge text={entity?.category} />
            {behaviour?.behaviour_type && behaviour.behaviour_type !== 'mixed' && (
              <Badge text={behaviour.behaviour_type.replace('_', ' ')} color={`${BEHAVIOUR_COLORS[behaviour.behaviour_type]} bg-white/5 border-white/10`} />
            )}
          </div>
        </div>
      </div>
      <div className="flex items-center gap-6 text-right">
        <div>
          <div className="text-[10px] text-gray-500 uppercase">Confidence</div>
          <div className="text-lg font-bold text-white">{conf(behaviour?.confidence || 0)}</div>
        </div>
        <div>
          <div className="text-[10px] text-gray-500 uppercase">Cluster Wallets</div>
          <div className="text-lg font-bold text-cyan-400">{clusterCount}</div>
        </div>
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════
// ROW 1: CORE — Portfolio, Net Flow, Behaviour
// ═══════════════════════════════════════════
function PortfolioCard({ data }) {
  if (!data?.total_usd) {
    return (
      <Card title="Portfolio" icon={PieChart}>
        <div className="text-xs text-gray-600">No holdings data</div>
      </Card>
    );
  }
  return (
    <Card title="Portfolio" icon={PieChart}>
      <div className="grid grid-cols-2 gap-3">
        <Metric label="Total Value" value={fmt(data.total_usd)} color="text-blue-400" />
        <Metric label="Token Count" value={data.token_count || 0} />
        <Metric label="Top 3 Conc." value={pct(data.top3_concentration || 0)} />
        <Metric label="Concentration" value={`${Math.round(data.concentration_score || 0)}/100`} />
      </div>
    </Card>
  );
}

function NetFlowCard({ data }) {
  if (!data?.flows) {
    return (
      <Card title="Net Flow" icon={ArrowLeftRight}>
        <div className="text-xs text-gray-600">No flow data</div>
      </Card>
    );
  }
  const w = data.flows?.['24h'] || data.all_time || {};
  const allTime = data.all_time || {};
  const net = allTime.net_flow_usd || 0;
  return (
    <Card title="Net Flow" icon={ArrowLeftRight}>
      <div className="grid grid-cols-2 gap-3">
        <Metric label="Inflow" value={fmt(allTime.inflow_usd)} color="text-emerald-400" />
        <Metric label="Outflow" value={fmt(allTime.outflow_usd)} color="text-red-400" />
        <Metric label="Net Flow" value={fmt(net)} color={net >= 0 ? 'text-emerald-400' : 'text-red-400'} />
        <Metric label="Velocity" value={fmt(data.flow_velocity)} sub="USD/period" />
      </div>
    </Card>
  );
}

function BehaviourCard({ data }) {
  if (!data?.behaviour_type) {
    return (
      <Card title="Behaviour" icon={Fingerprint}>
        <div className="text-xs text-gray-600">No behaviour data</div>
      </Card>
    );
  }
  return (
    <Card title="Behaviour" icon={Fingerprint}>
      <div className="mb-3">
        <div className={`text-lg font-bold capitalize ${BEHAVIOUR_COLORS[data.behaviour_type]}`}>
          {data.behaviour_type.replace('_', ' ')}
        </div>
        <div className="text-xs text-gray-500">Confidence: {conf(data.confidence)}</div>
      </div>
      <div className="space-y-1">
        {(data.drivers || []).slice(0, 4).map((d, i) => (
          <div key={i} className="flex items-center gap-1.5 text-[11px] text-gray-400">
            <div className="w-1 h-1 rounded-full bg-gray-600" />
            {d}
          </div>
        ))}
      </div>
    </Card>
  );
}

// ═══════════════════════════════════════════
// ROW 2: TOKEN ACTIVITY
// ═══════════════════════════════════════════
function TokenMatrixCard({ data }) {
  const tokens = (data?.tokens || []).filter(t => t.flow_volume_usd > 0);
  return (
    <Card title="Token Flow Matrix" icon={BarChart3}>
      {tokens.length === 0 ? (
        <div className="text-xs text-gray-600">No priced token activity</div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-[11px]">
            <thead>
              <tr className="text-gray-500 border-b border-white/5">
                <th className="text-left pb-2 font-medium">Token</th>
                <th className="text-right pb-2 font-medium">Flow Share</th>
                <th className="text-right pb-2 font-medium">Role</th>
                <th className="text-right pb-2 font-medium">Net Flow</th>
              </tr>
            </thead>
            <tbody>
              {tokens.slice(0, 8).map((t, i) => (
                <tr key={i} className="border-b border-white/3 hover:bg-white/2">
                  <td className="py-1.5 text-white font-medium">{t.symbol}</td>
                  <td className="py-1.5 text-right text-gray-400">{pct(t.flow_share)}</td>
                  <td className="py-1.5 text-right">
                    <span className={ROLE_COLORS[t.role] || 'text-gray-500'}>{t.role?.replace('_token', '')}</span>
                  </td>
                  <td className={`py-1.5 text-right ${t.net_flow_usd >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                    {fmt(t.net_flow_usd)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  );
}

function DominantAssetsCard({ data }) {
  const dom = data?.dominant_asset;
  const cls = data?.class_breakdown || {};
  return (
    <Card title="Dominant Assets" icon={Coins}>
      {!dom?.symbol ? (
        <div className="text-xs text-gray-600">No dominant asset</div>
      ) : (
        <>
          <div className="mb-3 p-2 bg-white/3 rounded border border-white/5">
            <div className="text-xs text-gray-500 mb-1">Dominant Token</div>
            <div className="flex items-center justify-between">
              <span className="text-white font-bold">{dom.symbol}</span>
              <span className={`text-sm ${ROLE_COLORS[dom.role]}`}>{dom.role?.replace('_token', '')}</span>
            </div>
            <div className="text-[10px] text-gray-500 mt-0.5">{pct(dom.flow_share)} share &middot; {fmt(dom.volume_usd)} vol</div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <Metric label="Stablecoin Dep." value={pct(data.stablecoin_dependency || 0)} color="text-cyan-400" />
            <Metric label="Top 3 Conc." value={pct(data.top3_concentration || 0)} />
          </div>
          <div className="mt-3 flex gap-2">
            {Object.entries(cls).map(([k, v]) => (
              <div key={k} className="flex-1 p-1.5 bg-white/3 rounded text-center">
                <div className="text-[10px] text-gray-500 capitalize">{k}</div>
                <div className="text-xs text-white font-medium">{v.count}</div>
                <div className="text-[9px] text-gray-600">{pct(v.share)}</div>
              </div>
            ))}
          </div>
        </>
      )}
    </Card>
  );
}

// ═══════════════════════════════════════════
// ROW 3: MARKET STRUCTURE
// ═══════════════════════════════════════════
function SimilarityCard({ data }) {
  const similar = (data?.top_similar || []).filter(s => s.similarity_score > 0.1);
  return (
    <Card title="Similarity Map" icon={GitBranch}>
      {similar.length === 0 ? (
        <div className="text-xs text-gray-600">No similar entities found</div>
      ) : (
        <div className="space-y-2">
          {similar.slice(0, 5).map((s, i) => (
            <Link
              key={i}
              to={`/entity/${s.slug}`}
              className="flex items-center justify-between p-2 bg-white/3 rounded border border-white/5 hover:border-white/10 transition-colors"
            >
              <div>
                <div className="text-xs text-white font-medium">{s.name}</div>
                <div className="flex items-center gap-1.5 mt-0.5">
                  <Badge text={s.type} />
                  <span className={`text-[10px] capitalize ${BEHAVIOUR_COLORS[s.behaviour_type]}`}>{s.behaviour_type?.replace('_', ' ')}</span>
                </div>
              </div>
              <div className="text-right">
                <div className="text-sm font-bold text-white">{conf(s.similarity_score)}</div>
                <div className="text-[9px] text-gray-500">{(s.reasons || [])[0]}</div>
              </div>
            </Link>
          ))}
        </div>
      )}
    </Card>
  );
}

function ClustersCard({ data }) {
  const clusters = data?.clusters || [];
  return (
    <Card title="Wallet Clusters" icon={Users}>
      <div className="grid grid-cols-3 gap-3 mb-3">
        <Metric label="Known Addrs" value={data?.known_addresses || 0} />
        <Metric label="Discovered" value={data?.total_discovered || 0} color="text-cyan-400" />
        <Metric label="Expansion" value={`${data?.coverage_expansion || 0}x`} color="text-emerald-400" />
      </div>
      {clusters.length === 0 ? (
        <div className="text-xs text-gray-600">No clusters detected</div>
      ) : (
        <div className="space-y-2">
          {clusters.map((cl, i) => (
            <div key={i} className={`p-2 rounded border ${TIER_COLORS[cl.tier]}`}>
              <div className="flex items-center justify-between">
                <div className="text-xs text-white font-medium">{cl.cluster_id}</div>
                <Badge text={cl.tier} color={cl.tier === 'high' ? 'text-emerald-400 bg-emerald-500/10 border-emerald-500/20' : 'text-amber-400 bg-amber-500/10 border-amber-500/20'} />
              </div>
              <div className="flex items-center gap-4 mt-1.5 text-[10px] text-gray-400">
                <span>{cl.size} wallets</span>
                <span>conf: {conf(cl.confidence)}</span>
                <span>activity: {conf(cl.activity_score)}</span>
              </div>
            </div>
          ))}
        </div>
      )}
    </Card>
  );
}

// ═══════════════════════════════════════════
// ROW 4: ATTRIBUTION
// ═══════════════════════════════════════════
function AttributionCard({ data }) {
  const attrs = data?.attributions || [];
  return (
    <Card title="Cluster Attribution" icon={Target}>
      {attrs.length === 0 ? (
        <div className="text-xs text-gray-600">No attribution data</div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-[11px]">
            <thead>
              <tr className="text-gray-500 border-b border-white/5">
                <th className="text-left pb-2 font-medium">Cluster</th>
                <th className="text-left pb-2 font-medium">Candidate</th>
                <th className="text-right pb-2 font-medium">Score</th>
                <th className="text-right pb-2 font-medium">Level</th>
              </tr>
            </thead>
            <tbody>
              {attrs.map((a, i) => (
                <tr key={i} className="border-b border-white/3">
                  <td className="py-1.5 text-white">{a.cluster_id?.split('_cluster_')[1] ? `#${a.cluster_id.split('_cluster_')[1]}` : a.cluster_id}</td>
                  <td className="py-1.5">
                    <Link to={`/entity/${a.possible_entity}`} className="text-blue-400 hover:text-blue-300">
                      {a.possible_entity}
                    </Link>
                  </td>
                  <td className="py-1.5 text-right text-white font-medium">{conf(a.attribution_score)}</td>
                  <td className="py-1.5 text-right">
                    <span className={`px-1.5 py-0.5 rounded text-[10px] border ${LEVEL_COLORS[a.attribution_level]}`}>
                      {a.attribution_level}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <div className="mt-2 space-y-1">
            {attrs.slice(0, 2).map((a, i) => (
              <div key={i} className="text-[10px] text-gray-500">
                {a.cluster_id}: {(a.signals || []).slice(0, 2).join(' · ')}
              </div>
            ))}
          </div>
        </div>
      )}
    </Card>
  );
}

function CandidatesCard({ data }) {
  const candidates = (data?.candidates || []).filter(c => c.attribution_level !== 'unknown');
  return (
    <Card title="Entity Candidates" icon={Search}>
      <div className="grid grid-cols-3 gap-3 mb-3">
        <Metric label="Total Clusters" value={data?.total_clusters || 0} />
        <Metric label="Attributed" value={data?.attributed || 0} color="text-emerald-400" />
        <Metric label="Unknown" value={(data?.by_level?.unknown) || 0} color="text-gray-500" />
      </div>
      {candidates.length === 0 ? (
        <div className="text-xs text-gray-600">No entity candidates</div>
      ) : (
        <div className="space-y-2">
          {candidates.slice(0, 5).map((c, i) => (
            <div key={i} className="flex items-center justify-between p-2 bg-white/3 rounded border border-white/5">
              <div>
                <div className="text-xs text-white font-medium">{c.cluster_id}</div>
                <div className="text-[10px] text-gray-500">{c.size} wallets &middot; {c.tier}</div>
              </div>
              <div className="text-right">
                <Link to={`/entity/${c.possible_entity}`} className="text-xs text-blue-400 hover:text-blue-300">
                  {c.possible_entity}
                </Link>
                <div className={`text-[10px] ${LEVEL_COLORS[c.attribution_level]?.split(' ')[0]}`}>{conf(c.attribution_score)}</div>
              </div>
            </div>
          ))}
        </div>
      )}
    </Card>
  );
}

// ═══════════════════════════════════════════
// ROW 5: MULTICHAIN
// ═══════════════════════════════════════════
const CHAIN_COLORS = {
  Ethereum: 'text-blue-400',
  Optimism: 'text-red-400',
  Arbitrum: 'text-sky-400',
  Base: 'text-indigo-400',
};

function MultichainCard({ data }) {
  const chains = data?.chains || [];
  return (
    <Card title="Chain Distribution" icon={Layers}>
      <div className="grid grid-cols-3 gap-3 mb-3">
        <Metric label="Chains Active" value={data?.total_chains_active || 0} color="text-cyan-400" />
        <Metric label="Total Addrs" value={data?.total_addresses || 0} />
        <Metric label="Multichain" value={data?.has_multichain_activity ? 'YES' : 'NO'} color={data?.has_multichain_activity ? 'text-emerald-400' : 'text-gray-500'} />
      </div>
      {chains.length === 0 ? (
        <div className="text-xs text-gray-600">No chain activity</div>
      ) : (
        <div className="space-y-2">
          {chains.map((ch, i) => (
            <div key={i} className="p-2 bg-white/3 rounded border border-white/5">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className={`text-xs font-bold ${CHAIN_COLORS[ch.chain_name] || 'text-gray-400'}`}>{ch.chain_name}</span>
                  <Badge text={ch.chain_type} />
                </div>
                <span className="text-xs text-white font-medium">{pct(ch.distribution_share)}</span>
              </div>
              <div className="flex items-center gap-4 mt-1.5 text-[10px] text-gray-400">
                <span>{ch.total_transfers} txs</span>
                <span>{ch.active_addresses} addrs</span>
                <span>{ch.unique_tokens} tokens</span>
                <span className={ch.direction === 'inflow_dominant' ? 'text-emerald-400' : ch.direction === 'outflow_dominant' ? 'text-red-400' : ''}>{ch.direction}</span>
                {ch.has_bridge_activity && <span className="text-purple-400">bridge</span>}
              </div>
              {/* Activity bar */}
              <div className="mt-1.5 h-1 bg-white/5 rounded-full overflow-hidden">
                <div className={`h-full rounded-full ${CHAIN_COLORS[ch.chain_name] ? 'bg-current ' + CHAIN_COLORS[ch.chain_name] : 'bg-gray-500'}`} style={{ width: `${ch.activity_score}%`, opacity: 0.6 }} />
              </div>
            </div>
          ))}
        </div>
      )}
      {(data?.bridge_summary || []).length > 0 && (
        <div className="mt-3 pt-2 border-t border-white/5">
          <div className="text-[10px] text-gray-500 mb-1">Bridge Activity</div>
          {data.bridge_summary.map((b, i) => (
            <div key={i} className="text-[10px] text-purple-400">{b.bridge} ({b.chains.join(' / ')})</div>
          ))}
        </div>
      )}
    </Card>
  );
}

function CrossChainCard({ data }) {
  const crossAddrs = data?.cross_chain_addresses || [];
  return (
    <Card title="Cross-Chain Activity" icon={GitBranch}>
      <div className="grid grid-cols-2 gap-3 mb-3">
        <Metric label="Cross-Chain Addrs" value={data?.cross_chain_count || 0} color={data?.cross_chain_count > 0 ? 'text-purple-400' : 'text-gray-500'} />
        <Metric label="Dominant Chain" value={data?.dominant_chain?.chain_name || 'N/A'} color={CHAIN_COLORS[data?.dominant_chain?.chain_name] || 'text-gray-400'} />
      </div>
      {crossAddrs.length === 0 ? (
        <div className="text-xs text-gray-600">No cross-chain addresses detected</div>
      ) : (
        <div className="space-y-1.5">
          {crossAddrs.slice(0, 5).map((cc, i) => (
            <div key={i} className="flex items-center justify-between p-1.5 bg-white/3 rounded">
              <span className="text-[10px] text-gray-400 font-mono">{cc.address.slice(0, 10)}...{cc.address.slice(-6)}</span>
              <div className="flex gap-1">
                {cc.chains.map((ch, j) => (
                  <span key={j} className={`text-[9px] px-1 rounded ${CHAIN_COLORS[ch.chain_name] || 'text-gray-400'} bg-white/5`}>{ch.chain_name}</span>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </Card>
  );
}

// ═══════════════════════════════════════════
// ROW 6: DISCOVERY (global, not per-entity)
// ═══════════════════════════════════════════
const TYPE_COLORS = {
  possible_fund: 'text-emerald-400',
  possible_market_maker: 'text-blue-400',
  possible_whale: 'text-amber-400',
  possible_protocol_actor: 'text-purple-400',
  unknown_cluster: 'text-gray-400',
};

function DiscoveryCard({ data }) {
  const candidates = data?.candidates || [];
  return (
    <Card title="Entity Discovery" icon={Zap} className="col-span-2">
      <div className="grid grid-cols-4 gap-3 mb-3">
        <Metric label="Candidates" value={data?.total_candidates || 0} color="text-amber-400" />
        <Metric label="Funds" value={data?.type_distribution?.possible_fund || 0} color="text-emerald-400" />
        <Metric label="MMs" value={data?.type_distribution?.possible_market_maker || 0} color="text-blue-400" />
        <Metric label="Whales" value={data?.type_distribution?.possible_whale || 0} color="text-amber-400" />
      </div>
      {candidates.length === 0 ? (
        <div className="text-xs text-gray-600">No new entities discovered</div>
      ) : (
        <div className="space-y-2">
          {candidates.slice(0, 5).map((c, i) => (
            <div key={i} className="flex items-center justify-between p-2 bg-white/3 rounded border border-white/5">
              <div>
                <div className="flex items-center gap-2">
                  <span className="text-xs text-white font-medium">{c.cluster_id}</span>
                  <Badge text={c.candidate_type?.replace('possible_', '')} color={`${TYPE_COLORS[c.candidate_type]} bg-white/5 border-white/10`} />
                </div>
                <div className="text-[10px] text-gray-500 mt-0.5">{c.wallets} wallets &middot; {(c.dominant_tokens || []).slice(0, 3).join(', ')}</div>
              </div>
              <div className="text-right">
                <div className="text-sm font-bold text-white">{conf(c.discovery_score)}</div>
                <div className="text-[9px] text-gray-500">{(c.signals || [])[0]}</div>
              </div>
            </div>
          ))}
        </div>
      )}
    </Card>
  );
}

// ═══════════════════════════════════════════
// ENTITY LIST (landing)
// ═══════════════════════════════════════════
function EntityListItem({ entity, behaviours, onClick }) {
  const beh = behaviours[entity.slug];
  const typeIcons = { exchange: Building, protocol: Layers, fund: PieChart, market_maker: Activity, whale: Eye };
  const TypeIcon = typeIcons[entity.type] || Building;

  return (
    <button
      onClick={() => onClick(entity.slug)}
      className="w-full flex items-center justify-between p-3 bg-[#0d0d15] border border-white/5 rounded-lg hover:border-white/15 transition-colors text-left"
      data-testid={`entity-item-${entity.slug}`}
    >
      <div className="flex items-center gap-3">
        <div className="w-9 h-9 rounded-lg bg-white/5 border border-white/10 flex items-center justify-center">
          <TypeIcon className="w-4 h-4 text-gray-500" />
        </div>
        <div>
          <div className="text-sm text-white font-medium">{entity.name}</div>
          <div className="flex items-center gap-1.5 mt-0.5">
            <span className="text-[10px] text-gray-500">{entity.type}</span>
            <span className="text-[10px] text-gray-600">&middot;</span>
            <span className="text-[10px] text-gray-500">{entity.category}</span>
          </div>
        </div>
      </div>
      <div className="flex items-center gap-4">
        {beh && beh.behaviour_type !== 'mixed' && (
          <span className={`text-xs capitalize ${BEHAVIOUR_COLORS[beh.behaviour_type]}`}>
            {beh.behaviour_type.replace('_', ' ')}
          </span>
        )}
        {beh?.confidence > 0 && (
          <span className="text-xs text-gray-400">{conf(beh.confidence)}</span>
        )}
        <ArrowUpRight className="w-3.5 h-3.5 text-gray-600" />
      </div>
    </button>
  );
}

// ═══════════════════════════════════════════
// MAIN PAGE
// ═══════════════════════════════════════════
export default function EntityDetail() {
  const { entityId } = useParams();
  const navigate = useNavigate();

  const [entities, setEntities] = useState([]);
  const [behaviours, setBehaviours] = useState({});
  const [selectedSlug, setSelectedSlug] = useState(entityId || null);
  const [loading, setLoading] = useState(true);

  // Entity detail data
  const [entity, setEntity] = useState(null);
  const [portfolio, setPortfolio] = useState(null);
  const [flows, setFlows] = useState(null);
  const [behaviour, setBehaviour] = useState(null);
  const [tokenMatrix, setTokenMatrix] = useState(null);
  const [similar, setSimilar] = useState(null);
  const [clusters, setClusters] = useState(null);
  const [clusterAttrs, setClusterAttrs] = useState(null);
  const [candidates, setCandidates] = useState(null);
  const [chainData, setChainData] = useState(null);
  const [discovery, setDiscovery] = useState(null);
  const [detailLoading, setDetailLoading] = useState(false);

  // Load entity list
  useEffect(() => {
    async function load() {
      try {
        const [listRes, behRes] = await Promise.all([
          api.get(`${API}/list?limit=50`),
          api.get(`${API}/behaviour/overview`),
        ]);
        setEntities(listRes.data?.entities || []);
        const behMap = {};
        for (const e of (behRes.data?.entities || [])) {
          behMap[e.slug] = e;
        }
        setBehaviours(behMap);
      } catch (e) {
        console.error('Failed to load entities:', e);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  // Load entity detail
  const loadDetail = useCallback(async (slug) => {
    setDetailLoading(true);
    try {
      const [entRes, portRes, flowRes, behRes, matRes, simRes, clRes, attrRes, candRes, chainRes, discRes] = await Promise.allSettled([
        api.get(`${API}/${slug}`),
        api.get(`${API}/${slug}/portfolio`),
        api.get(`${API}/${slug}/flows`),
        api.get(`${API}/${slug}/behaviour`),
        api.get(`${API}/${slug}/token-matrix`),
        api.get(`${API}/${slug}/similar`),
        api.get(`${API}/${slug}/clusters`),
        api.get(`${API}/${slug}/cluster-attributions`),
        api.get(`${API}/candidates`),
        api.get(`${API}/${slug}/chains`),
        api.get(`${API}/discovery`),
      ]);

      setEntity(entRes.status === 'fulfilled' ? entRes.value.data?.entity : null);
      setPortfolio(portRes.status === 'fulfilled' ? portRes.value.data : null);
      setFlows(flowRes.status === 'fulfilled' ? flowRes.value.data : null);
      setBehaviour(behRes.status === 'fulfilled' ? behRes.value.data : null);
      setTokenMatrix(matRes.status === 'fulfilled' ? matRes.value.data : null);
      setSimilar(simRes.status === 'fulfilled' ? simRes.value.data : null);
      setClusters(clRes.status === 'fulfilled' ? clRes.value.data : null);
      setClusterAttrs(attrRes.status === 'fulfilled' ? attrRes.value.data : null);
      setCandidates(candRes.status === 'fulfilled' ? candRes.value.data : null);
      setChainData(chainRes.status === 'fulfilled' ? chainRes.value.data : null);
      setDiscovery(discRes.status === 'fulfilled' ? discRes.value.data : null);
    } catch (e) {
      console.error('Failed to load entity detail:', e);
    } finally {
      setDetailLoading(false);
    }
  }, []);

  useEffect(() => {
    if (selectedSlug) loadDetail(selectedSlug);
  }, [selectedSlug, loadDetail]);

  // Handle entity selection
  function selectEntity(slug) {
    setSelectedSlug(slug);
    navigate(`/entity/${slug}`, { replace: true });
  }

  // ── ENTITY DETAIL VIEW ──
  if (selectedSlug) {
    return (
      <div className="min-h-screen bg-[#08080d] text-white" data-testid="entity-terminal">
        {/* Navigation */}
        <div className="border-b border-white/5 px-6 py-3">
          <div className="max-w-7xl mx-auto flex items-center gap-4">
            <button
              onClick={() => { setSelectedSlug(null); navigate('/entities'); }}
              className="flex items-center gap-1 text-xs text-gray-400 hover:text-white transition-colors"
              data-testid="back-to-list"
            >
              <ChevronLeft className="w-3.5 h-3.5" /> Entities
            </button>
            <span className="text-gray-600">/</span>
            <span className="text-xs text-gray-300">{entity?.name || selectedSlug}</span>
          </div>
        </div>

        {detailLoading ? (
          <div className="flex items-center justify-center h-64">
            <div className="w-6 h-6 border-2 border-white/20 border-t-white rounded-full animate-spin" />
          </div>
        ) : (
          <div className="max-w-7xl mx-auto px-6 py-6 space-y-5">
            {/* HEADER */}
            <EntityHeader entity={entity} behaviour={behaviour} clusters={clusters} />

            {/* ROW 1: CORE */}
            <div className="grid grid-cols-3 gap-4">
              <PortfolioCard data={portfolio} />
              <NetFlowCard data={flows} />
              <BehaviourCard data={behaviour} />
            </div>

            {/* ROW 2: TOKEN ACTIVITY */}
            <div className="grid grid-cols-2 gap-4">
              <TokenMatrixCard data={tokenMatrix} />
              <DominantAssetsCard data={tokenMatrix} />
            </div>

            {/* ROW 3: MARKET STRUCTURE */}
            <div className="grid grid-cols-2 gap-4">
              <SimilarityCard data={similar} />
              <ClustersCard data={clusters} />
            </div>

            {/* ROW 4: ATTRIBUTION */}
            <div className="grid grid-cols-2 gap-4">
              <AttributionCard data={clusterAttrs} />
              <CandidatesCard data={candidates} />
            </div>

            {/* ROW 5: MULTICHAIN */}
            <div className="grid grid-cols-2 gap-4">
              <MultichainCard data={chainData} />
              <CrossChainCard data={chainData} />
            </div>

            {/* ROW 6: DISCOVERY */}
            <div className="grid grid-cols-1 gap-4">
              <DiscoveryCard data={discovery} />
            </div>
          </div>
        )}
      </div>
    );
  }

  // ── ENTITY LIST VIEW ──
  return (
    <div className="min-h-screen bg-[#08080d] text-white" data-testid="entities-list">
      <div className="max-w-7xl mx-auto px-6 py-6">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-xl font-bold text-white">Entity Intelligence Terminal</h1>
            <p className="text-xs text-gray-500 mt-1">{entities.length} entities tracked &middot; 9-layer analysis</p>
          </div>
          <div className="flex items-center gap-2">
            <Shield className="w-4 h-4 text-emerald-500" />
            <span className="text-xs text-gray-400">Entities 10/10</span>
          </div>
        </div>

        {loading ? (
          <div className="flex items-center justify-center h-32">
            <div className="w-6 h-6 border-2 border-white/20 border-t-white rounded-full animate-spin" />
          </div>
        ) : (
          <div className="space-y-2">
            {entities.map(e => (
              <EntityListItem key={e.slug} entity={e} behaviours={behaviours} onClick={selectEntity} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
