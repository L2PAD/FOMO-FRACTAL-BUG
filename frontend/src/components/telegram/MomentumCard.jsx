/**
 * Momentum Card (M-3 UI)
 * Shows momentum metrics on Channel Page
 */
import { TrendingUp, TrendingDown, Minus } from 'lucide-react';

export default function MomentumCard({ data }) {
  if (!data) return null;

  const { latest, items } = data;
  if (!latest) return null;

  const trendIcon = {
    RISING: <TrendingUp className="w-5 h-5 text-emerald-500" />,
    FALLING: <TrendingDown className="w-5 h-5 text-red-500" />,
    FLAT: <Minus className="w-5 h-5 text-gray-400" />,
  };

  const trendColor = {
    RISING: 'text-emerald-600',
    FALLING: 'text-red-600',
    FLAT: 'text-gray-600',
  };

  return (
    <div className="bg-white border border-gray-200 rounded-xl p-6" data-testid="momentum-card">
      <div className="flex items-start justify-between">
        <div>
          <div className="text-sm text-gray-500 font-medium">Momentum Score</div>
          <div className="text-3xl font-bold text-gray-900 mt-1">
            {latest.momentumScore != null ? latest.momentumScore.toFixed(1) : '—'}
          </div>
        </div>

        <div className="flex items-center gap-2">
          {trendIcon[latest.trend] || trendIcon.FLAT}
          <span className={`text-sm font-medium ${trendColor[latest.trend] || trendColor.FLAT}`}>
            {latest.trend || 'FLAT'}
          </span>
        </div>
      </div>

      {/* Velocity/Acceleration Grid */}
      <div className="grid grid-cols-4 gap-4 mt-6 pt-4 border-t border-gray-100">
        <MiniStat
          label="Velocity (7d)"
          value={latest.v7?.toFixed(2)}
          suffix="/day"
          positive={latest.v7 > 0}
        />
        <MiniStat
          label="Acceleration"
          value={latest.a7?.toFixed(2)}
          positive={latest.a7 > 0}
        />
        <MiniStat
          label="Volatility (30d)"
          value={latest.vol30?.toFixed(2)}
          warn={latest.vol30 > 3}
        />
        <MiniStat
          label="Consistency"
          value={`${Math.round((latest.consistency30 || 0) * 100)}%`}
        />
      </div>

      {/* New Riser Badge */}
      {latest.newRiser && (
        <div className="mt-4 p-3 bg-emerald-50 border border-emerald-100 rounded-lg">
          <div className="flex items-center gap-2 text-emerald-700">
            <TrendingUp className="w-4 h-4" />
            <span className="text-sm font-medium">New Riser: Crossed 70 this week with strong velocity</span>
          </div>
        </div>
      )}

      {/* Explain Bullets */}
      {latest.momentumExplain?.length > 0 && (
        <div className="mt-4 pt-4 border-t border-gray-100">
          <div className="text-xs text-gray-500 mb-2">Score Breakdown</div>
          <div className="flex flex-wrap gap-2">
            {latest.momentumExplain.slice(0, 5).map((exp, i) => (
              <span key={i} className="px-2 py-1 bg-gray-100 rounded text-xs text-gray-700">
                {exp}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function MiniStat({ label, value, suffix = '', positive, warn }) {
  let textColor = 'text-gray-900';
  if (positive === true) textColor = 'text-emerald-600';
  if (positive === false) textColor = 'text-red-600';
  if (warn) textColor = 'text-amber-600';

  return (
    <div className="text-center">
      <div className={`text-lg font-semibold ${textColor}`}>
        {value || '—'}{suffix}
      </div>
      <div className="text-xs text-gray-500 mt-0.5">{label}</div>
    </div>
  );
}
