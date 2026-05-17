/**
 * Similar Channels Panel (BLOCK U-8)
 * Recommendation engine - shows channels similar to current one
 */
import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { RefreshCw, TrendingUp, TrendingDown, Shield, Users } from 'lucide-react';
import * as telegramApi from '../../api/telegramIntel.api';

/**
 * Lifecycle badge colors
 */
const LIFECYCLE_COLORS = {
  EMERGING: 'bg-emerald-100 text-emerald-700 border-emerald-200',
  EXPANDING: 'bg-blue-100 text-blue-700 border-blue-200',
  MATURE: 'bg-violet-100 text-violet-700 border-violet-200',
  SATURATED: 'bg-amber-100 text-amber-700 border-amber-200',
  DECLINING: 'bg-red-100 text-red-700 border-red-200',
  STABLE: 'bg-gray-100 text-gray-600 border-gray-200',
};

/**
 * Category badge colors
 */
const CATEGORY_COLORS = {
  ALPHA: 'bg-yellow-100 text-yellow-700 border-yellow-200',
  ESTABLISHED: 'bg-indigo-100 text-indigo-700 border-indigo-200',
  GROWTH: 'bg-teal-100 text-teal-700 border-teal-200',
  ENGAGED: 'bg-pink-100 text-pink-700 border-pink-200',
  RISKY: 'bg-red-100 text-red-700 border-red-200',
  GENERAL: 'bg-gray-100 text-gray-600 border-gray-200',
};

export default function SimilarChannelsPanel({ username }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (username) loadSimilar();
  }, [username]);

  const loadSimilar = async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await telegramApi.getSimilarChannels(username, 6);
      setData(result);
    } catch (err) {
      console.error('[U-8] Failed to load similar channels:', err);
      setError('Failed to load similar channels');
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="bg-white rounded-xl border border-gray-200 p-6" data-testid="similar-channels-loading">
        <div className="flex items-center gap-3">
          <RefreshCw className="w-5 h-5 animate-spin text-blue-500" />
          <span className="text-gray-600">Loading similar channels...</span>
        </div>
      </div>
    );
  }

  if (error || !data?.ok) {
    return (
      <div className="bg-white rounded-xl border border-gray-200 p-6" data-testid="similar-channels-error">
        <div className="text-gray-500 text-sm">
          {error || 'Could not load similar channels'}
        </div>
      </div>
    );
  }

  const items = data.items || [];

  if (items.length === 0) {
    return (
      <div className="bg-white rounded-xl border border-gray-200 p-6" data-testid="similar-channels-empty">
        <div className="font-semibold text-gray-900 mb-2">Similar Channels</div>
        <div className="text-gray-500 text-sm">
          Not enough data yet. Ingest more channels to see recommendations.
        </div>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-xl border border-gray-200 p-6" data-testid="similar-channels-panel">
      {/* Header */}
      <div className="flex items-start justify-between mb-4">
        <div>
          <h3 className="font-semibold text-gray-900">Similar Channels</h3>
          <p className="text-sm text-gray-500 mt-0.5">
            Based on category, lifecycle, utility, engagement, growth, stability
          </p>
        </div>
        <button
          onClick={loadSimilar}
          className="p-1.5 rounded-lg hover:bg-gray-100 transition-colors"
          title="Refresh"
        >
          <RefreshCw className="w-4 h-4 text-gray-500" />
        </button>
      </div>

      {/* Grid of similar channels */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
        {items.map((item) => (
          <SimilarChannelCard key={item.username} item={item} />
        ))}
      </div>
    </div>
  );
}

/**
 * Single similar channel card
 */
function SimilarChannelCard({ item }) {
  const lifecycleColor = LIFECYCLE_COLORS[item.lifecycle] || LIFECYCLE_COLORS.STABLE;
  const categoryColor = CATEGORY_COLORS[item.category] || CATEGORY_COLORS.GENERAL;

  return (
    <div 
      className="border border-gray-200 rounded-xl p-4 bg-white hover:border-blue-300 hover:shadow-sm transition-all"
      data-testid={`similar-channel-${item.username}`}
    >
      {/* Header row */}
      <div className="flex items-center justify-between mb-2">
        <Link 
          to={`/telegram/${item.username}`}
          className="font-semibold text-gray-900 hover:text-blue-600 transition-colors"
        >
          @{item.username}
        </Link>
        <span 
          className="px-2 py-0.5 text-xs rounded-full bg-gray-100 text-gray-600"
          title="Similarity score (lower is more similar)"
        >
          sim {item.similarityScore.toFixed(2)}
        </span>
      </div>

      {/* Badges row */}
      <div className="flex flex-wrap gap-1.5 mb-3">
        {item.category && (
          <span className={`px-2 py-0.5 text-xs rounded-full border ${categoryColor}`}>
            {item.category}
          </span>
        )}
        {item.lifecycle && (
          <span className={`px-2 py-0.5 text-xs rounded-full border ${lifecycleColor}`}>
            {item.lifecycle}
          </span>
        )}
      </div>

      {/* Metrics row */}
      <div className="grid grid-cols-4 gap-2 text-xs mb-3">
        <MetricItem label="Utility" value={item.utilityScore} />
        <MetricItem 
          label="Growth" 
          value={`${item.growth30 >= 0 ? '+' : ''}${item.growth30.toFixed(1)}%`}
          isPositive={item.growth30 >= 0}
        />
        <MetricItem 
          label="ER" 
          value={`${(item.engagementRate * 100).toFixed(1)}%`}
        />
        <MetricItem 
          label="Fraud" 
          value={item.fraudRisk.toFixed(2)}
          isNegative={item.fraudRisk > 0.3}
        />
      </div>

      {/* Reasons */}
      {item.reasons && item.reasons.length > 0 && (
        <div className="border-t border-gray-100 pt-2 mt-2">
          <div className="text-xs text-gray-500 space-y-0.5">
            {item.reasons.slice(0, 3).map((reason, idx) => (
              <div key={idx} className="flex items-start gap-1">
                <span className="text-gray-400">•</span>
                <span>{reason}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

/**
 * Small metric display
 */
function MetricItem({ label, value, isPositive, isNegative }) {
  let valueColor = 'text-gray-900';
  if (isPositive) valueColor = 'text-emerald-600';
  if (isNegative) valueColor = 'text-red-600';

  return (
    <div className="text-center">
      <div className={`font-medium ${valueColor}`}>{value}</div>
      <div className="text-gray-500">{label}</div>
    </div>
  );
}
