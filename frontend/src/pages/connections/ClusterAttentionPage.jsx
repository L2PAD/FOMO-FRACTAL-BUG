/**
 * Cluster Intelligence Page — Decision tool for cluster analysis
 * Layout: Insight Bar → Cluster Cards (left) → Token Panel (right, filtered by selected cluster)
 */
import { useState, useEffect, useMemo, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { Zap, TrendingUp, AlertTriangle, Users, ArrowUpRight, ArrowDownRight, Minus, RefreshCw, ExternalLink, Shield } from 'lucide-react';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || '';

const TYPE_CONFIG = {
  smart_money: { label: 'Smart Money', color: 'text-green-600' },
  narrative_drivers: { label: 'Narrative Drivers', color: 'text-blue-600' },
  retail_noise: { label: 'Retail Noise', color: 'text-gray-500' },
  coordinated_pump: { label: 'Coordinated Pump', color: 'text-red-600' },
};
const STATUS_CONFIG = {
  emerging: { label: 'Emerging', color: 'text-green-600', dot: 'bg-green-500' },
  active: { label: 'Active', color: 'text-yellow-600', dot: 'bg-yellow-500' },
  saturated: { label: 'Saturated', color: 'text-red-500', dot: 'bg-red-500' },
  dead: { label: 'Dead', color: 'text-gray-400', dot: 'bg-gray-400' },
};
const DIR_ICON = {
  bullish: { Icon: ArrowUpRight, color: 'text-green-600' },
  mixed: { Icon: Minus, color: 'text-yellow-600' },
  dump_risk: { Icon: ArrowDownRight, color: 'text-red-600' },
};

// ─── INSIGHT BAR ────────────────────────────────────
const InsightBar = ({ insights }) => {
  if (!insights || insights.length === 0) return null;
  return (
    <div className="flex items-center gap-4 mb-3 px-4 py-2.5 bg-gray-900 text-white rounded-lg" data-testid="cluster-insight-bar">
      {insights.map((ins, i) => (
        <div key={i} className="flex items-center gap-2 text-sm">
          <Zap className="w-4 h-4 text-yellow-400 flex-shrink-0" />
          <span className="font-medium">{ins.text}</span>
        </div>
      ))}
    </div>
  );
};

// ─── CLUSTER CARD ───────────────────────────────────
const ClusterCard = ({ cluster, isSelected, onSelect }) => {
  const type = TYPE_CONFIG[cluster.type] || TYPE_CONFIG.retail_noise;
  const status = STATUS_CONFIG[cluster.status] || STATUS_CONFIG.active;
  const dir = DIR_ICON[cluster.metrics.direction] || DIR_ICON.mixed;
  const DirIcon = dir.Icon;

  return (
    <div
      onClick={() => onSelect(cluster.id)}
      className={`p-3 cursor-pointer transition-all ${isSelected ? 'bg-gray-900 text-white' : 'hover:bg-gray-50'}`}
      data-testid={`cluster-card-${cluster.id}`}
    >
      {/* Header: Name + Score */}
      <div className="flex items-center justify-between mb-1.5">
        <div className="flex items-center gap-2">
          <span className={`text-sm font-bold ${isSelected ? 'text-white' : 'text-gray-900'}`}>{cluster.name}</span>
          <span className={`text-[10px] font-medium ${isSelected ? 'text-gray-300' : type.color}`}>{type.label}</span>
        </div>
        <div className="flex items-center gap-1.5">
          <span className={`w-1.5 h-1.5 rounded-full ${status.dot}`} />
          <span className={`text-[10px] ${isSelected ? 'text-gray-300' : status.color}`}>{status.label}</span>
        </div>
      </div>

      {/* Members */}
      <div className="flex items-center gap-1 mb-1.5">
        <span className={`text-xs ${isSelected ? 'text-gray-400' : 'text-gray-500'}`}>{cluster.member_count} members:</span>
        <div className="flex -space-x-1.5">
          {cluster.members.slice(0, 4).map(m => (
            <img key={m.username} src={m.avatar} alt="" className="w-5 h-5 rounded-full border border-white" onError={e => { e.target.src = `https://ui-avatars.com/api/?name=${m.username}&size=20&background=random`; }} />
          ))}
          {cluster.member_count > 4 && <span className={`text-[10px] ml-1 ${isSelected ? 'text-gray-400' : 'text-gray-400'}`}>+{cluster.member_count - 4}</span>}
        </div>
      </div>

      {/* Tokens row */}
      <div className="flex items-center gap-2 mb-1.5 flex-wrap">
        {cluster.tokens.slice(0, 3).map(t => {
          const ret = t.price_return;
          const color = ret > 0 ? (isSelected ? 'text-green-400' : 'text-green-600') : ret < 0 ? (isSelected ? 'text-red-400' : 'text-red-600') : (isSelected ? 'text-gray-400' : 'text-gray-500');
          return (
            <span key={t.symbol} className="text-xs">
              <span className={`font-medium ${isSelected ? 'text-white' : 'text-gray-900'}`}>{t.symbol}</span>
              <span className={`ml-0.5 ${color}`}>{ret > 0 ? '+' : ''}{(ret * 100).toFixed(1)}%</span>
            </span>
          );
        })}
      </div>

      {/* Metrics row */}
      <div className="flex items-center gap-3 text-[10px]">
        <span className={isSelected ? 'text-gray-400' : 'text-gray-500'}>
          Coordination {Math.round(cluster.metrics.cohesion * 100)}%
        </span>
        <span className={isSelected ? 'text-gray-400' : 'text-gray-500'}>
          Trust {Math.round(cluster.metrics.trust * 100)}%
        </span>
        <div className="ml-auto flex items-center gap-1">
          <DirIcon className={`w-3.5 h-3.5 ${isSelected ? 'text-gray-300' : dir.color}`} />
          <span className={`font-bold ${isSelected ? 'text-white' : 'text-gray-900'}`}>
            {cluster.metrics.cluster_score.toFixed(2)}
          </span>
        </div>
      </div>

      {/* Signal */}
      <div className={`mt-1 text-[10px] italic ${isSelected ? 'text-yellow-300' : 'text-yellow-700'}`}>
        → {cluster.signal}
      </div>
    </div>
  );
};

// ─── TOKEN PANEL (right side) ──────────────────────
const TokenPanel = ({ cluster, allClusters }) => {
  if (!cluster) {
    return (
      <div className="flex items-center justify-center h-full text-gray-400 text-sm">
        Select a cluster to see token details
      </div>
    );
  }

  return (
    <div className="h-full overflow-y-auto" data-testid="token-panel">
      <div className="px-3 py-2">
        <div className="text-xs text-gray-400 uppercase tracking-wider mb-0.5">
          Tokens driven by {cluster.name}
        </div>
      </div>
      <div className="divide-y divide-gray-100">
        {cluster.tokens.map(t => {
          const clustersForToken = allClusters.filter(c =>
            c.tokens.some(ct => ct.symbol === t.symbol)
          );
          const ret = t.price_return;
          const retColor = ret > 0 ? 'text-green-600' : ret < 0 ? 'text-red-600' : 'text-gray-500';
          const impact = t.alignment_score > 0.8 ? 'HIGH' : t.alignment_score > 0.5 ? 'MEDIUM' : 'LOW';
          const impactColor = impact === 'HIGH' ? 'text-green-600' : impact === 'MEDIUM' ? 'text-yellow-600' : 'text-gray-500';

          return (
            <div key={t.symbol} className="px-3 py-2" data-testid={`token-row-${t.symbol}`}>
              <div className="flex items-center justify-between mb-0.5">
                <span className="text-sm font-bold text-gray-900">{t.symbol}</span>
                <span className={`text-sm font-bold ${retColor}`}>
                  {ret > 0 ? '+' : ''}{(ret * 100).toFixed(1)}%
                </span>
              </div>
              <div className="flex items-center gap-3 text-[10px] text-gray-500">
                <span>Impact: <span className={`font-semibold ${impactColor}`}>{impact}</span></span>
                <span>{t.verdict === 'CONFIRMED' ? '✓ Confirmed' : '○ Unconfirmed'}</span>
                <span>{t.mentions} mentioners</span>
              </div>
              {clustersForToken.length > 1 && (
                <div className="mt-0.5 text-[10px] text-purple-600 font-medium">
                  Mentioned by {clustersForToken.length} clusters
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* Members section */}
      <div className="px-3 py-2 mt-2">
        <div className="text-xs text-gray-400 uppercase tracking-wider mb-1">Members</div>
        {cluster.members.map(m => (
          <div key={m.username} className="flex items-center gap-2 py-1 text-xs">
            <img src={m.avatar} alt="" className="w-5 h-5 rounded-full" onError={e => { e.target.src = `https://ui-avatars.com/api/?name=${m.username}&size=20&background=random`; }} />
            <span className="text-gray-700 flex-1">@{m.username}</span>
            <span className="text-gray-400">{Math.round(m.authority * 100)}</span>
          </div>
        ))}
      </div>
    </div>
  );
};

// ─── CREDIBILITY RANKING ────────────────────────────
const CredibilityRanking = ({ clusters }) => {
  return (
    <div className="flex items-center gap-3 text-xs" data-testid="credibility-ranking">
      {clusters.slice(0, 5).map((c, i) => {
        const type = TYPE_CONFIG[c.type] || TYPE_CONFIG.retail_noise;
        const impactLabel = c.metrics.cluster_score > 0.7 ? 'HIGH IMPACT' : c.metrics.cluster_score > 0.5 ? 'STABLE' : 'NOISY';
        return (
          <span key={c.id} className="text-gray-500">
            #{i + 1} <span className="font-medium text-gray-700">{c.name}</span> → {Math.round(c.metrics.cluster_score * 100)}% <span className={type.color}>({impactLabel})</span>
          </span>
        );
      })}
    </div>
  );
};

// ─── MAIN PAGE ──────────────────────────────────────
export default function ClusterAttentionPage() {
  const navigate = useNavigate();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [selectedClusterId, setSelectedClusterId] = useState(null);

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetch(`${BACKEND_URL}/api/connections/clusters/intelligence`);
      const json = await res.json();
      if (json.ok) {
        setData(json.data);
        if (json.data.clusters.length > 0 && !selectedClusterId) {
          setSelectedClusterId(json.data.clusters[0].id);
        }
      }
    } catch (err) {
      console.error('Cluster fetch error:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchData(); }, [fetchData]);

  const selectedCluster = useMemo(() => {
    if (!data?.clusters) return null;
    return data.clusters.find(c => c.id === selectedClusterId);
  }, [data, selectedClusterId]);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <RefreshCw className="w-6 h-6 text-gray-400 animate-spin" />
      </div>
    );
  }

  if (!data || data.clusters.length === 0) {
    return (
      <div className="flex items-center justify-center h-64 text-gray-400 text-sm">
        No cluster data available
      </div>
    );
  }

  return (
    <div className="p-4" data-testid="cluster-attention-page">
      {/* Insight Bar */}
      <InsightBar insights={data.insights} />

      {/* Main: Clusters + Token Panel */}
      <div className="flex gap-4 mb-3" style={{ height: 480 }}>
        {/* Cluster Cards */}
        <div className="flex-1 min-w-0 bg-white rounded-lg overflow-hidden" data-testid="clusters-container">
          <div className="flex items-center justify-between px-3 py-2">
            <span className="text-xs text-gray-400 uppercase tracking-wider font-semibold">
              Clusters ({data.total})
            </span>
            <button onClick={fetchData} disabled={loading} className="p-1 text-gray-400 hover:text-gray-600" data-testid="refresh-clusters">
              <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
            </button>
          </div>
          <div className="overflow-y-auto divide-y divide-gray-100" style={{ maxHeight: 440 }}>
            {data.clusters.map(c => (
              <ClusterCard
                key={c.id}
                cluster={c}
                isSelected={c.id === selectedClusterId}
                onSelect={setSelectedClusterId}
              />
            ))}
          </div>
        </div>

        {/* Token Detail Panel */}
        <div className="w-[320px] flex-shrink-0 bg-white rounded-lg overflow-hidden" data-testid="token-detail-panel">
          <TokenPanel cluster={selectedCluster} allClusters={data.clusters} />
        </div>
      </div>

      {/* Credibility Ranking */}
      <CredibilityRanking clusters={data.clusters} />
    </div>
  );
}
