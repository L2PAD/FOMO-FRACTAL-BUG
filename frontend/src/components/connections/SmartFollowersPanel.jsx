/**
 * SmartFollowersPanel - Compact Smart Followers display
 * Shows: Summary score + Top followers table (no tier badges, no colored numbers)
 */
import { useState, useEffect } from 'react';
import { Users, Crown } from 'lucide-react';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || '';

const ProgressBar = ({ value, color = 'purple' }) => {
  const colors = { blue: 'bg-blue-500', green: 'bg-green-500', purple: 'bg-purple-500', amber: 'bg-amber-500', red: 'bg-red-500' };
  return (
    <div className="h-2 bg-gray-200 rounded-full overflow-hidden">
      <div className={`h-full ${colors[color] || 'bg-blue-500'} transition-all duration-500`} style={{ width: `${Math.min(100, value * 100)}%` }} />
    </div>
  );
};

const SummaryCard = ({ data }) => {
  const scorePercent = Math.round(data.smart_followers_score_0_1 * 100);
  let verdict = 'Weak audience';
  let verdictColor = 'text-red-600';
  if (scorePercent >= 75) { verdict = 'Strong smart audience'; verdictColor = 'text-green-600'; }
  else if (scorePercent >= 55) { verdict = 'Good smart audience'; verdictColor = 'text-blue-600'; }
  else if (scorePercent >= 35) { verdict = 'Average audience'; verdictColor = 'text-amber-600'; }

  return (
    <div>
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <Crown className="w-4 h-4 text-purple-600" />
          <div>
            <h3 className="font-semibold text-gray-900 text-sm">Smart Followers Score</h3>
            <p className={`text-xs font-medium ${verdictColor}`}>{verdict}</p>
          </div>
        </div>
        <div className="text-right">
          <div className="text-2xl font-bold text-purple-600">{scorePercent}</div>
          <div className="text-xs text-gray-500">out of 100</div>
        </div>
      </div>
      <ProgressBar value={data.smart_followers_score_0_1} color={scorePercent >= 60 ? 'purple' : scorePercent >= 35 ? 'amber' : 'red'} />
      <div className="grid grid-cols-3 gap-2 mt-3 text-center">
        <div>
          <div className="text-sm font-semibold text-gray-900">{data.followers_count}</div>
          <div className="text-[10px] text-gray-500">Total Followers</div>
        </div>
        <div>
          <div className="text-sm font-semibold text-gray-900">{data.follower_value_index.toFixed(2)}</div>
          <div className="text-[10px] text-gray-500">Value Index</div>
        </div>
        <div>
          <div className="text-sm font-semibold text-gray-900">
            {Math.round((data.breakdown.elite_weight_share + data.breakdown.high_weight_share) * 100)}%
          </div>
          <div className="text-[10px] text-gray-500">Elite+High Share</div>
        </div>
      </div>
    </div>
  );
};

const TopFollowersTable = ({ followers }) => {
  if (!followers || followers.length === 0) {
    return (
      <div>
        <h4 className="text-[10px] font-semibold text-gray-500 uppercase tracking-wider mb-2">Top Smart Followers</h4>
        <div className="text-center text-gray-500 py-4">No follower data available</div>
      </div>
    );
  }

  return (
    <div>
      <h4 className="text-[10px] font-semibold text-gray-500 uppercase tracking-wider mb-1">Top Smart Followers</h4>
      <table className="w-full text-xs" data-testid="top-followers-table">
        <thead>
          <tr className="text-left text-gray-400">
            <th className="pb-1 font-medium w-5">#</th>
            <th className="pb-1 font-medium">Account</th>
            <th className="pb-1 font-medium text-right">Authority</th>
            <th className="pb-1 font-medium text-right">Impact</th>
          </tr>
        </thead>
        <tbody>
          {followers.slice(0, 10).map((follower, idx) => (
            <tr key={follower.follower_id} className="hover:bg-gray-50 transition-colors">
              <td className="py-1 text-gray-400">{idx + 1}</td>
              <td className="py-1">
                <span className="text-gray-900">{follower.display_name || follower.handle}</span>
              </td>
              <td className="py-1 text-right text-gray-700">{(follower.authority_score_0_1 * 100).toFixed(0)}</td>
              <td className="py-1 text-right text-green-600 font-medium">+{(follower.share_of_total * 100).toFixed(1)}%</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};

export default function SmartFollowersPanel({ accountId, onDataLoaded }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchData = async () => {
      if (!accountId) return;
      setLoading(true);
      try {
        const res = await fetch(`${BACKEND_URL}/api/connections/smart-followers/${accountId}`);
        const json = await res.json();
        if (json.ok) {
          setData(json.data);
          onDataLoaded?.(json.data);
        } else {
          setError(json.message || 'Failed to load data');
        }
      } catch (err) {
        setError(err.message);
      }
      setLoading(false);
    };
    fetchData();
  }, [accountId]);

  if (loading) {
    return (
      <div className="animate-pulse space-y-2">
        <div className="h-20 bg-gray-200 rounded"></div>
        <div className="h-40 bg-gray-200 rounded"></div>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="text-center py-4">
        <Users className="w-8 h-8 mx-auto mb-2 text-gray-300" />
        <p className="text-gray-500 text-sm">Unable to load smart followers</p>
      </div>
    );
  }

  return (
    <div className="space-y-3" data-testid="smart-followers-panel">
      <SummaryCard data={data} />
      <TopFollowersTable followers={data.top_followers} />
    </div>
  );
}

// Export TierDistribution for use in sidebar
export function TierDistributionCompact({ breakdown }) {
  if (!breakdown) return null;
  const tiers = ['elite', 'high', 'upper_mid', 'mid', 'low_mid', 'low'];
  const TIER_LABELS = { elite: 'Elite', high: 'High', upper_mid: 'Upper', mid: 'Mid', low_mid: 'Low-Mid', low: 'Low' };
  const TIER_COLORS = { elite: '#8b5cf6', high: '#22c55e', upper_mid: '#3b82f6', mid: '#06b6d4', low_mid: '#f59e0b', low: '#ef4444' };

  return (
    <div data-testid="tier-distribution">
      <div className="text-[10px] text-gray-400 uppercase tracking-wider mb-1">Tier Distribution</div>
      <div className="space-y-1">
        {tiers.map(tier => {
          const share = breakdown.tier_shares[tier] || 0;
          const count = breakdown.tier_counts[tier] || 0;
          if (count === 0) return null;
          return (
            <div key={tier} className="flex items-center gap-1.5 text-[10px]">
              <span className="w-10 text-gray-500">{TIER_LABELS[tier]}</span>
              <div className="flex-1 h-1.5 bg-gray-100 rounded-full overflow-hidden">
                <div className="h-full rounded-full" style={{ width: `${Math.max(share * 100, 5)}%`, backgroundColor: TIER_COLORS[tier] }} />
              </div>
              <span className="w-10 text-right text-gray-400">{Math.round(share * 100)}%</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
