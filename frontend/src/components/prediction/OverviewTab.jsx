/**
 * OverviewTab — Decision Screen
 * Colored text for status counters. Hot signal accent.
 */
import { ArrowRight, Flame } from 'lucide-react';
import MarketCard from './MarketCard';
import { getTopOpportunities, getTopRisks, fillIfEmpty } from '../../adapters/uiCase.adapter';

const STATUS_COUNTERS = [
  { key: 'entry',  label: 'Entry',   color: 'text-emerald-600' },
  { key: 'moving', label: 'Moving',  color: 'text-blue-600' },
  { key: 'watch',  label: 'Watch',   color: 'text-gray-500' },
  { key: 'avoid',  label: 'Avoid',   color: 'text-red-500' },
];

export default function OverviewTab({ uiCases, grouped, onNavigate, metaAlerts }) {
  const topOps = getTopOpportunities(uiCases, 3);
  const topRisks = getTopRisks(uiCases);
  const displayOps = fillIfEmpty(topOps, uiCases.filter(c => c.statusKey === 'watch'), 3);

  const recentChanges = (metaAlerts || [])
    .filter(ma => ma.priority === 'HIGH' || ma.priority === 'MEDIUM')
    .slice(0, 3);

  const hotCount = uiCases.filter(c => c.isHot).length;

  return (
    <div className="px-6 py-5 space-y-6" data-testid="overview-tab">
      {/* Status Counters — colored text */}
      <div className="flex items-center gap-6" data-testid="status-counters">
        {STATUS_COUNTERS.map(s => {
          const count = grouped[s.key]?.length || 0;
          return (
            <button
              key={s.key}
              onClick={() => onNavigate('markets', s.key)}
              className="flex items-center gap-2 text-sm hover:opacity-80 transition-opacity"
              data-testid={`counter-${s.key}`}
            >
              <span className={`font-medium ${s.color}`}>{s.label}</span>
              <span className="text-lg font-semibold text-gray-900 tabular-nums">{count}</span>
            </button>
          );
        })}
        {hotCount > 0 && (
          <span className="flex items-center gap-1 text-sm text-amber-500 font-medium ml-2">
            <Flame className="w-3.5 h-3.5" /> {hotCount} hot
          </span>
        )}
      </div>

      {/* Top Opportunities */}
      <div>
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-sm font-medium text-gray-900">Top Opportunities</h2>
          {grouped.entry?.length > 0 && (
            <button
              onClick={() => onNavigate('markets', 'entry')}
              className="flex items-center gap-1 text-xs text-gray-400 hover:text-gray-700 transition-colors"
            >
              All markets <ArrowRight className="w-3 h-3" />
            </button>
          )}
        </div>
        {displayOps.length > 0 ? (
          <div className="bg-white rounded-lg border border-gray-200/60">
            {displayOps.map(c => <MarketCard key={c.id} c={c} />)}
          </div>
        ) : (
          <p className="text-sm text-gray-400 py-6">No active opportunities — system is monitoring</p>
        )}
      </div>

      {/* Risks */}
      {topRisks.length > 0 && (
        <div>
          <h2 className="text-sm font-medium text-gray-900 mb-2">Risks</h2>
          <div className="space-y-1">
            {topRisks.map((r, i) => (
              <div key={i} className="text-sm py-1" data-testid={`risk-${i}`}>
                <span className="font-medium text-red-500">{r.asset}</span>
                <span className="text-gray-500 ml-2">{r.reason}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Changes */}
      {recentChanges.length > 0 && (
        <div>
          <h2 className="text-sm font-medium text-gray-900 mb-2">Changes</h2>
          <div className="bg-white rounded-lg border border-gray-200/60 divide-y divide-gray-100">
            {recentChanges.map((ma, i) => {
              const isHighPrio = ma.priority === 'HIGH';
              return (
                <div key={i} className="px-4 py-3 text-sm" data-testid={`change-${i}`}>
                  <span className={`text-xs font-medium uppercase tracking-wider mr-2 ${isHighPrio ? 'text-red-500' : 'text-gray-400'}`}>
                    {ma.type?.replace(/_/g, ' ')}
                  </span>
                  <span className="text-gray-600">{ma.summary}</span>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
