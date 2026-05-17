/**
 * Leaderboard Stats Row (Block UI-1 + U-2)
 * Institutional-style stats cards with mode support
 */
export default function LeaderboardStats({ stats, loading, mode = 'utility' }) {
  if (loading) {
    return (
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4" data-testid="leaderboard-stats">
        {[...Array(4)].map((_, i) => (
          <div key={i} className="bg-white border border-gray-200 rounded-xl p-4 animate-pulse">
            <div className="h-4 bg-gray-100 rounded w-24 mb-2"></div>
            <div className="h-8 bg-gray-100 rounded w-16"></div>
          </div>
        ))}
      </div>
    );
  }

  if (!stats) return null;

  // Utility mode stats
  if (mode === 'utility') {
    return (
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4" data-testid="leaderboard-stats">
        <StatCard
          label="Tracked Channels"
          value={stats.totalChannels || stats.total || 0}
          color="blue"
        />
        <StatCard
          label="Avg Utility"
          value={stats.avgUtility || 0}
          color="emerald"
        />
        <StatCard
          label="Avg Growth 30d"
          value={`${(stats.avgGrowth30 || 0).toFixed(1)}%`}
          color="violet"
        />
        <StatCard
          label="Avg Engagement"
          value={`${((stats.avgEngagement || 0) * 100).toFixed(1)}%`}
          color="amber"
        />
      </div>
    );
  }

  // Intel/Momentum mode stats (legacy)
  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-4" data-testid="leaderboard-stats">
      <StatCard
        label="Tracked Channels"
        value={stats.total || 0}
        color="blue"
      />
      <StatCard
        label="Avg Intel Score"
        value={stats.avgIntel?.toFixed(1) || '0'}
        color="emerald"
      />
      <StatCard
        label="High Alpha (≥80)"
        value={stats.highAlpha || 0}
        color="violet"
      />
      <StatCard
        label="High Fraud (>0.6)"
        value={stats.highFraud || 0}
        color="red"
      />
    </div>
  );
}

function StatCard({ label, value, color = 'gray' }) {
  const colors = {
    blue: 'text-blue-600',
    emerald: 'text-emerald-600',
    violet: 'text-violet-600',
    amber: 'text-amber-600',
    red: 'text-red-600',
    gray: 'text-gray-600',
  };

  return (
    <div className="rounded-xl border border-gray-200 bg-white p-4">
      <div className="text-sm text-gray-500 font-medium">{label}</div>
      <div className={`text-2xl font-bold mt-1 ${colors[color] || 'text-gray-900'}`}>
        {typeof value === 'number' ? value.toLocaleString() : value}
      </div>
    </div>
  );
}
