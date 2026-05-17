/**
 * Telegram Leaderboard Table (U-2 + U-7 + M-3 UI)
 * Card-based watchlist style with Utility/Intel/Momentum mode support + Lifecycle
 */
import { Link, useSearchParams } from 'react-router-dom';
import { TrendingUp, TrendingDown, Minus, Flame, Zap, Snowflake, Info, Sprout, Rocket, Building, Scale, LineChart } from 'lucide-react';

// Utility Tier Badge (A+/A/B/C/D)
function UtilityTierBadge({ tier }) {
  const colors = {
    'A+': 'bg-emerald-100 text-emerald-700 border-emerald-200',
    'A': 'bg-blue-100 text-blue-700 border-blue-200',
    'B': 'bg-sky-100 text-sky-700 border-sky-200',
    'C': 'bg-amber-100 text-amber-700 border-amber-200',
    'D': 'bg-gray-100 text-gray-500 border-gray-200',
  };
  return (
    <span className={`px-2 py-0.5 rounded text-xs font-semibold border ${colors[tier] || colors.D}`}>
      {tier}
    </span>
  );
}

// Intel Tier Badge (S/A/B/C/D)
function TierBadge({ tier }) {
  const colors = {
    S: 'bg-violet-100 text-violet-700 border-violet-200',
    A: 'bg-emerald-100 text-emerald-700 border-emerald-200',
    B: 'bg-blue-100 text-blue-700 border-blue-200',
    C: 'bg-amber-100 text-amber-700 border-amber-200',
    D: 'bg-gray-100 text-gray-500 border-gray-200',
  };
  return (
    <span className={`px-2 py-0.5 rounded text-xs font-semibold border ${colors[tier] || colors.D}`}>
      {tier}
    </span>
  );
}

// Lifecycle Badge (U-7)
function LifecycleBadge({ lifecycle }) {
  const config = {
    EMERGING: { bg: 'bg-teal-50 text-teal-700 border-teal-200', icon: Sprout, label: 'Emerging' },
    EXPANDING: { bg: 'bg-emerald-50 text-emerald-700 border-emerald-200', icon: Rocket, label: 'Expanding' },
    MATURE: { bg: 'bg-slate-50 text-slate-600 border-slate-200', icon: Building, label: 'Mature' },
    SATURATED: { bg: 'bg-amber-50 text-amber-700 border-amber-200', icon: Scale, label: 'Saturated' },
    DECLINING: { bg: 'bg-red-50 text-red-600 border-red-200', icon: LineChart, label: 'Declining' },
    STABLE: { bg: 'bg-gray-50 text-gray-600 border-gray-200', icon: Minus, label: 'Stable' },
  };
  const c = config[lifecycle] || config.STABLE;
  const Icon = c.icon;
  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium border ${c.bg}`} title={lifecycle}>
      <Icon className="w-3 h-3" />
      {c.label}
    </span>
  );
}

function TrendBadge({ trend }) {
  const config = {
    RISING: { bg: 'bg-emerald-50 text-emerald-700 border-emerald-200', icon: TrendingUp },
    FALLING: { bg: 'bg-red-50 text-red-700 border-red-200', icon: TrendingDown },
    FLAT: { bg: 'bg-gray-50 text-gray-600 border-gray-200', icon: Minus },
  };
  const c = config[trend] || config.FLAT;
  const Icon = c.icon;
  return (
    <span className={`px-2 py-0.5 rounded text-xs font-medium border flex items-center gap-1 inline-flex ${c.bg}`}>
      <Icon className="w-3 h-3" />
      {trend || 'FLAT'}
    </span>
  );
}

// Growth Badge (🔥 Hot / ⚡ Rising / 🧊 Stable)
function GrowthBadge({ growth }) {
  if (growth > 20) {
    return (
      <span className="inline-flex items-center gap-1 px-1.5 py-0.5 bg-orange-100 text-orange-700 rounded text-xs font-medium">
        <Flame className="w-3 h-3" /> Hot
      </span>
    );
  }
  if (growth > 10) {
    return (
      <span className="inline-flex items-center gap-1 px-1.5 py-0.5 bg-yellow-100 text-yellow-700 rounded text-xs font-medium">
        <Zap className="w-3 h-3" /> Rising
      </span>
    );
  }
  if (growth < -5) {
    return (
      <span className="inline-flex items-center gap-1 px-1.5 py-0.5 bg-blue-100 text-blue-600 rounded text-xs font-medium">
        <Snowflake className="w-3 h-3" /> Cooling
      </span>
    );
  }
  return null;
}

// Compute lifecycle stage from metrics (mirrors backend logic)
function getLifecycleStage(row) {
  const growth30 = row.growth30 || 0;
  const growth7 = row.growth7 || 0;
  const utilityScore = row.utilityScore || 0;
  const stability = row.stability || 0;
  
  // Compute acceleration
  const expectedWeekly = growth30 / 4;
  const acceleration = growth7 - expectedWeekly;
  
  // Classification rules (same as backend)
  if (growth30 > 15 && acceleration > 3) return 'EXPANDING';
  if (acceleration > 5 && utilityScore < 60) return 'EMERGING';
  if (growth30 >= -3 && growth30 <= 5 && utilityScore > 70 && stability > 0.6) return 'MATURE';
  if (growth30 < 3 && acceleration < -2 && utilityScore > 50) return 'SATURATED';
  if (growth30 < -5 || (growth30 < -3 && acceleration < -3)) return 'DECLINING';
  
  return 'STABLE';
}

function ScoreCell({ value, color = 'text-gray-900' }) {
  const num = Number(value ?? 0);
  return <span className={`font-medium ${color}`}>{num.toFixed(1)}</span>;
}

function PercentCell({ value, showSign = true }) {
  const num = Number(value ?? 0);
  const color = num > 0 ? 'text-emerald-600' : num < 0 ? 'text-red-600' : 'text-gray-500';
  const sign = showSign && num > 0 ? '+' : '';
  return <span className={`text-sm font-medium ${color}`}>{sign}{num.toFixed(1)}%</span>;
}

function FraudCell({ value }) {
  const num = Number(value ?? 0);
  const color = num > 0.5 ? 'text-red-600' : num > 0.25 ? 'text-amber-600' : 'text-emerald-600';
  const label = num > 0.5 ? 'High' : num > 0.25 ? 'Med' : 'Low';
  return (
    <span className={`text-sm font-medium ${color}`}>
      {label}
    </span>
  );
}

function StabilityCell({ value }) {
  const num = Number(value ?? 0);
  const pct = Math.round(num * 100);
  const color = num > 0.7 ? 'text-emerald-600' : num > 0.4 ? 'text-amber-600' : 'text-red-600';
  return <span className={`text-sm font-medium ${color}`}>{pct}%</span>;
}

function OriginalityCell({ forwardRatio }) {
  const originality = 1 - (forwardRatio ?? 0.3);
  const pct = Math.round(originality * 100);
  const color = originality > 0.7 ? 'text-emerald-600' : originality > 0.4 ? 'text-amber-600' : 'text-gray-500';
  return <span className={`text-sm font-medium ${color}`}>{pct}%</span>;
}

// Column Header with tooltip
function ColumnHeader({ label, tooltip }) {
  return (
    <th className="px-3 py-3 text-center font-medium text-gray-600 group relative">
      <span className="flex items-center justify-center gap-1">
        {label}
        {tooltip && (
          <Info className="w-3 h-3 text-gray-400 cursor-help" />
        )}
      </span>
      {tooltip && (
        <div className="absolute hidden group-hover:block z-10 w-48 p-2 text-xs text-left font-normal bg-gray-900 text-white rounded shadow-lg -translate-x-1/2 left-1/2 mt-1">
          {tooltip}
        </div>
      )}
    </th>
  );
}

export default function LeaderboardTable({ items = [], loading = false }) {
  const [searchParams] = useSearchParams();
  const mode = searchParams.get('mode') || 'utility';
  const isUtility = mode === 'utility';
  const isMomentum = mode === 'momentum';

  if (loading) {
    return (
      <div className="bg-white border border-gray-200 rounded-xl p-8 text-center">
        <div className="animate-pulse space-y-3">
          {[...Array(5)].map((_, i) => (
            <div key={i} className="h-12 bg-gray-100 rounded-lg" />
          ))}
        </div>
      </div>
    );
  }

  if (!items.length) {
    return (
      <div className="bg-white border border-gray-200 rounded-xl p-8 text-center text-gray-500">
        No channels found. Run the scoring pipeline first.
      </div>
    );
  }

  return (
    <div className="bg-white border border-gray-200 rounded-xl overflow-hidden" data-testid="leaderboard-table">
      <table className="w-full text-sm">
        <thead className="bg-gray-50 border-b border-gray-200">
          <tr>
            <th className="px-4 py-3 text-left font-medium text-gray-600">Channel</th>
            <th className="px-3 py-3 text-center font-medium text-gray-600">Tier</th>
            
            {isUtility ? (
              <>
                <ColumnHeader label="Utility" tooltip="Overall channel quality score (0-100)" />
                <ColumnHeader label="Lifecycle" tooltip="Channel stage: Emerging, Expanding, Mature, Saturated, Declining" />
                <ColumnHeader label="Growth" tooltip="30-day score change percentage" />
                <ColumnHeader label="ER" tooltip="Engagement Rate = Views / Subscribers" />
                <ColumnHeader label="Fraud" tooltip="Fraud risk level" />
              </>
            ) : isMomentum ? (
              <>
                <th className="px-3 py-3 text-center font-medium text-gray-600">Momentum</th>
                <th className="px-3 py-3 text-center font-medium text-gray-600">v7</th>
                <th className="px-3 py-3 text-center font-medium text-gray-600">a7</th>
                <th className="px-3 py-3 text-center font-medium text-gray-600">Trend</th>
                <th className="px-3 py-3 text-center font-medium text-gray-600">Intel</th>
              </>
            ) : (
              <>
                <th className="px-3 py-3 text-center font-medium text-gray-600">Intel</th>
                <th className="px-3 py-3 text-center font-medium text-gray-600">Alpha</th>
                <th className="px-3 py-3 text-center font-medium text-gray-600">Cred</th>
                <th className="px-3 py-3 text-center font-medium text-gray-600">NetAlpha</th>
                <th className="px-3 py-3 text-center font-medium text-gray-600">Fraud</th>
              </>
            )}
          </tr>
        </thead>
        <tbody>
          {items.map((row, i) => (
            <tr 
              key={row.username || i} 
              className="border-b border-gray-100 hover:bg-gray-50 transition-colors"
              data-testid={`leaderboard-row-${row.username}`}
            >
              <td className="px-4 py-3">
                <div className="flex items-center gap-2">
                  <Link
                    to={`/telegram/${row.username}`}
                    className="font-medium text-blue-600 hover:text-blue-800"
                    data-testid={`channel-link-${row.username}`}
                  >
                    @{row.username}
                  </Link>
                  {row.newRiser && (
                    <span className="px-1.5 py-0.5 bg-emerald-100 text-emerald-700 text-xs rounded font-medium">
                      NEW
                    </span>
                  )}
                </div>
              </td>
              
              <td className="px-3 py-3 text-center">
                {isUtility ? (
                  <UtilityTierBadge tier={row.utilityTier} />
                ) : (
                  <TierBadge tier={row.tier} />
                )}
              </td>
              
              {isUtility ? (
                <>
                  <td className="px-3 py-3 text-center">
                    <span className="font-semibold text-gray-900">{row.utilityScore}</span>
                  </td>
                  <td className="px-3 py-3 text-center">
                    <LifecycleBadge lifecycle={getLifecycleStage(row)} />
                  </td>
                  <td className="px-3 py-3 text-center">
                    <div className="flex items-center justify-center gap-1">
                      <PercentCell value={row.growth30} />
                      <GrowthBadge growth={row.growth30} />
                    </div>
                  </td>
                  <td className="px-3 py-3 text-center">
                    <span className="text-sm font-medium text-gray-700">
                      {(row.engagementRate * 100).toFixed(1)}%
                    </span>
                  </td>
                  <td className="px-3 py-3 text-center">
                    <FraudCell value={row.fraudRisk} />
                  </td>
                </>
              ) : isMomentum ? (
                <>
                  <td className="px-3 py-3 text-center">
                    <ScoreCell 
                      value={row.momentumScore} 
                      color={row.momentumScore >= 60 ? 'text-emerald-600' : row.momentumScore >= 40 ? 'text-blue-600' : 'text-gray-600'} 
                    />
                  </td>
                  <td className="px-3 py-3 text-center">
                    <span className={`text-sm ${row.v7 > 0 ? 'text-emerald-600' : row.v7 < 0 ? 'text-red-600' : 'text-gray-500'}`}>
                      {row.v7?.toFixed(2) || '—'}
                    </span>
                  </td>
                  <td className="px-3 py-3 text-center">
                    <span className={`text-sm ${row.a7 > 0 ? 'text-emerald-600' : row.a7 < 0 ? 'text-red-600' : 'text-gray-500'}`}>
                      {row.a7?.toFixed(2) || '—'}
                    </span>
                  </td>
                  <td className="px-3 py-3 text-center">
                    <TrendBadge trend={row.trend} />
                  </td>
                  <td className="px-3 py-3 text-center">
                    <ScoreCell value={row.intelScore} color="text-gray-600" />
                  </td>
                </>
              ) : (
                <>
                  <td className="px-3 py-3 text-center">
                    <ScoreCell value={row.intelScore} color="text-blue-600" />
                  </td>
                  <td className="px-3 py-3 text-center">
                    <ScoreCell value={row.alphaScore || row.components?.alphaScore} color="text-emerald-600" />
                  </td>
                  <td className="px-3 py-3 text-center">
                    <ScoreCell value={row.credibilityScore || row.components?.credibilityScore} color="text-amber-600" />
                  </td>
                  <td className="px-3 py-3 text-center">
                    <ScoreCell value={row.networkAlphaScore || row.components?.networkAlphaScore} color="text-violet-600" />
                  </td>
                  <td className="px-3 py-3 text-center">
                    <FraudCell value={row.fraudRisk || row.components?.fraudRisk} />
                  </td>
                </>
              )}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
