/**
 * Compare Panel
 * Shows channel's position in the network relative to peers
 * Block UI-5: Institutional peer context
 */
import { TrendingUp, TrendingDown, ArrowUp, ArrowDown, Target, Users } from 'lucide-react';

function formatScore(val) {
  if (val === null || val === undefined) return '—';
  return val.toFixed(1);
}

function TierBadge({ tier }) {
  const colors = {
    S: 'bg-amber-50 text-amber-700 border-amber-200',
    A: 'bg-emerald-50 text-emerald-700 border-emerald-200',
    B: 'bg-blue-50 text-blue-700 border-blue-200',
    C: 'bg-neutral-100 text-neutral-600 border-neutral-200',
    D: 'bg-neutral-50 text-neutral-500 border-neutral-200',
  };
  
  return (
    <span className={`inline-flex px-2 py-0.5 rounded text-xs font-semibold border ${colors[tier] || colors.D}`}>
      Tier {tier}
    </span>
  );
}

function GapIndicator({ value, direction = 'up' }) {
  if (value === null || value === undefined) return null;
  
  const Icon = direction === 'up' ? ArrowUp : ArrowDown;
  const color = direction === 'up' ? 'text-emerald-600' : 'text-neutral-500';
  
  return (
    <div className={`flex items-center gap-1 text-sm ${color}`}>
      <Icon className="w-3.5 h-3.5" />
      <span className="font-medium">{value.toFixed(2)}</span>
    </div>
  );
}

function NeighborCard({ neighbor, direction }) {
  if (!neighbor) return null;
  
  const Icon = direction === 'up' ? ArrowUp : ArrowDown;
  const borderColor = direction === 'up' ? 'border-l-emerald-400' : 'border-l-neutral-300';
  
  return (
    <div className={`pl-3 py-1 border-l-2 ${borderColor}`}>
      <div className="flex items-center gap-2">
        <span className="text-sm font-medium text-neutral-700">@{neighbor.username}</span>
        <TierBadge tier={neighbor.tier} />
      </div>
      <div className="text-xs text-neutral-500 mt-0.5">
        IntelScore: {neighbor.intelScore}
      </div>
    </div>
  );
}

export default function ComparePanel({ data, loading = false }) {
  if (loading) {
    return (
      <div className="bg-white rounded-xl border border-neutral-200 p-6">
        <div className="flex items-center justify-center py-8">
          <div className="w-6 h-6 border-2 border-neutral-200 border-t-neutral-600 rounded-full animate-spin" />
        </div>
      </div>
    );
  }

  if (!data || !data.ok) {
    return null;
  }

  const { position, gaps, neighbors, peerContext, current } = data;

  return (
    <div className="bg-white rounded-xl border border-neutral-200" data-testid="compare-panel">
      {/* Header */}
      <div className="px-5 py-4 border-b border-neutral-100">
        <div className="flex items-center gap-2">
          <Target className="w-4 h-4 text-neutral-400" />
          <h3 className="text-sm font-semibold text-neutral-900">Position in Network</h3>
        </div>
      </div>

      {/* Main Stats Grid */}
      <div className="grid grid-cols-3 gap-4 p-5 border-b border-neutral-100">
        <div>
          <div className="text-xs text-neutral-500 mb-1">Global Rank</div>
          <div className="text-2xl font-bold text-neutral-900">
            #{position.rank}
            <span className="text-sm font-normal text-neutral-400 ml-1">/ {position.total}</span>
          </div>
        </div>

        <div>
          <div className="text-xs text-neutral-500 mb-1">Percentile</div>
          <div className={`text-2xl font-bold ${position.percentile <= 0.1 ? 'text-emerald-600' : 'text-neutral-900'}`}>
            {position.percentileLabel}
          </div>
        </div>

        <div>
          <div className="text-xs text-neutral-500 mb-1">Distance to Tier S</div>
          <div className="text-2xl font-bold">
            {gaps.toTierS <= 0 ? (
              <span className="text-amber-600">In Tier S</span>
            ) : (
              <span className="text-neutral-900">+{gaps.toTierS}</span>
            )}
          </div>
        </div>
      </div>

      {/* Gap Analysis */}
      <div className="px-5 py-4 border-b border-neutral-100 bg-neutral-50/30">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-6">
            {gaps.up !== null && (
              <div>
                <div className="text-xs text-neutral-500 mb-1">Gap to higher rank</div>
                <GapIndicator value={gaps.up} direction="up" />
              </div>
            )}
            {gaps.down !== null && (
              <div>
                <div className="text-xs text-neutral-500 mb-1">Gap to lower rank</div>
                <GapIndicator value={gaps.down} direction="down" />
              </div>
            )}
          </div>
          
          {gaps.toTierA !== null && (
            <div className="text-right">
              <div className="text-xs text-neutral-500 mb-1">To Tier A</div>
              <div className="text-sm font-medium text-neutral-600">+{gaps.toTierA}</div>
            </div>
          )}
        </div>
      </div>

      {/* Neighbors */}
      <div className="px-5 py-4 border-b border-neutral-100">
        <div className="text-xs font-medium text-neutral-500 mb-3">Nearby Channels</div>
        <div className="space-y-3">
          <NeighborCard neighbor={neighbors.prev} direction="up" />
          
          {/* Current Channel Highlight */}
          <div className="px-3 py-2 bg-blue-50 rounded-lg border border-blue-100">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <span className="text-sm font-semibold text-blue-700">@{data.username}</span>
                <TierBadge tier={current.tier} />
              </div>
              <div className="text-sm font-bold text-blue-700">
                {current.intelScore}
              </div>
            </div>
          </div>
          
          <NeighborCard neighbor={neighbors.next} direction="down" />
        </div>
      </div>

      {/* Peer Context */}
      <div className="px-5 py-4">
        <div className="flex items-center gap-2 mb-3">
          <Users className="w-4 h-4 text-neutral-400" />
          <span className="text-xs font-medium text-neutral-500">Tier {peerContext.tier} Context</span>
        </div>
        
        <div className="grid grid-cols-3 gap-4 text-sm">
          <div>
            <div className="text-xs text-neutral-400">Peers in Tier</div>
            <div className="font-semibold text-neutral-900">{peerContext.peersInTier}</div>
          </div>
          <div>
            <div className="text-xs text-neutral-400">Tier Average</div>
            <div className="font-semibold text-neutral-900">{peerContext.tierAverage}</div>
          </div>
          <div>
            <div className="text-xs text-neutral-400">vs Average</div>
            <div className={`font-semibold ${peerContext.vsAverage >= 0 ? 'text-emerald-600' : 'text-rose-600'}`}>
              {peerContext.vsAverage >= 0 ? '+' : ''}{peerContext.vsAverage}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
