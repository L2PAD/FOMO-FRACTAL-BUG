/**
 * Telegram Stats Bar
 * Global stats summary
 */
import { Users, Zap, Shield, TrendingUp } from 'lucide-react';

function StatCard({ icon, label, value, sub, color = 'text-gray-900' }) {
  return (
    <div className="bg-white border border-gray-200 rounded-xl p-4">
      <div className="flex items-center gap-3">
        <div className="p-2 bg-gray-50 rounded-lg">{icon}</div>
        <div>
          <div className={`text-xl font-bold ${color}`}>{value}</div>
          <div className="text-xs text-gray-500">{label}</div>
          {sub && <div className="text-xs text-gray-400">{sub}</div>}
        </div>
      </div>
    </div>
  );
}

export default function StatsBar({ stats = {} }) {
  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-4" data-testid="stats-bar">
      <StatCard
        icon={<Users className="w-5 h-5 text-blue-500" />}
        label="Tracked Channels"
        value={stats.totalChannels?.toLocaleString() || '0'}
        sub="With scores"
      />
      <StatCard
        icon={<TrendingUp className="w-5 h-5 text-emerald-500" />}
        label="Avg Intel Score"
        value={Number(stats.avgIntelScore ?? 0).toFixed(1)}
        color="text-emerald-600"
      />
      <StatCard
        icon={<Zap className="w-5 h-5 text-violet-500" />}
        label="High Alpha"
        value={stats.highAlphaCount?.toLocaleString() || '0'}
        sub="Score >50"
      />
      <StatCard
        icon={<Shield className="w-5 h-5 text-red-500" />}
        label="Avg Fraud Risk"
        value={(Number(stats.avgFraudRisk ?? 0) * 100).toFixed(0) + '%'}
        color="text-red-600"
      />
    </div>
  );
}
