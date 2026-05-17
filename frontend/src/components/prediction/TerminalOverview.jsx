/**
 * TerminalOverview — Trust-first overview, light theme.
 *
 * Dark hero card for Trust Score (like Sentiment's "WHAT TO DO NOW")
 * Light cards for Opportunities / Risks / Changes
 */
import { useState, useEffect } from 'react';
import { ArrowRight, Flame, TrendingUp, AlertTriangle, Activity, ShieldCheck } from 'lucide-react';
import { getTopOpportunities, getTopRisks, fillIfEmpty } from '../../adapters/uiCase.adapter';

const API = process.env.REACT_APP_BACKEND_URL;

export default function TerminalOverview({ uiCases, grouped, onNavigate, metaAlerts }) {
  const [labData, setLabData] = useState(null);
  const [feedData, setFeedData] = useState(null);

  useEffect(() => {
    fetch(`${API}/api/prediction-lab/overview`)
      .then(r => r.ok ? r.json() : null)
      .then(d => setLabData(d))
      .catch(() => {});
    fetch(`${API}/api/feed?mode=hot`)
      .then(r => r.ok ? r.json() : null)
      .then(d => setFeedData(d))
      .catch(() => {});
  }, []);

  const topOps = getTopOpportunities(uiCases, 4);
  const topRisks = getTopRisks(uiCases);
  const displayOps = fillIfEmpty(topOps, uiCases.filter(c => c.statusKey === 'watch'), 4);
  const hotCount = uiCases.filter(c => c.isHot).length;

  const recentChanges = (metaAlerts || [])
    .filter(ma => ma.priority === 'HIGH' || ma.priority === 'MEDIUM')
    .slice(0, 4);

  const accuracy = labData?.accuracy ?? labData?.global_accuracy;
  const totalPredictions = labData?.total_forecasts ?? labData?.resolved ?? 0;
  const calibration = labData?.calibration_state ?? labData?.calibration;
  const isCalibrated = calibration === 'GOOD' || calibration === 'calibrated';

  const hotEvents = (feedData?.events || []).filter(e => e.tier === 'hot').slice(0, 3);

  return (
    <div className="p-6 space-y-5" data-testid="terminal-overview">
      {/* ─── Trust Score Hero (dark accent card) ─── */}
      <div className="bg-gray-900 rounded-xl p-6" data-testid="trust-score-hero">
        <div className="flex items-center justify-between">
          {/* Trust Score */}
          <div className="flex items-center gap-8">
            <div>
              <div className="text-4xl font-bold text-white tabular-nums tracking-tight">
                {accuracy != null ? `${Math.round(accuracy * (accuracy < 1 ? 100 : 1))}%` : '--'}
              </div>
              <div className="text-xs text-gray-400 mt-1">
                accuracy
                {totalPredictions > 0 && (
                  <span className="text-gray-500"> ({totalPredictions} predictions)</span>
                )}
              </div>
              {isCalibrated && (
                <div className="flex items-center gap-1.5 mt-1.5">
                  <ShieldCheck className="w-3.5 h-3.5 text-emerald-400" />
                  <span className="text-xs text-emerald-400 font-medium">calibrated</span>
                </div>
              )}
            </div>

            {/* Status counters */}
            <div className="flex items-center gap-5">
              {[
                { key: 'entry', label: 'ENTER', color: 'text-emerald-400' },
                { key: 'watch', label: 'WATCH', color: 'text-gray-400' },
                { key: 'avoid', label: 'AVOID', color: 'text-red-400' },
              ].map(s => {
                const items = grouped[s.key] || [];
                return (
                  <div key={s.key}>
                    <div className={`text-xs font-bold ${s.color}`}>{s.label}</div>
                    <div className="text-xs text-gray-400 mt-0.5">
                      {items.length > 0
                        ? items.slice(0, 2).map(c => c.question?.split(' ').slice(0, 4).join(' ')).join(', ')
                        : 'No threats'}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Hot count */}
          {hotCount > 0 && (
            <div className="flex items-center gap-1.5 text-amber-400">
              <Flame className="w-4 h-4" />
              <span className="text-sm font-bold">{hotCount} hot</span>
            </div>
          )}
        </div>
      </div>

      {/* ─── Status Bar (light) ─── */}
      <div className="flex items-center gap-4 px-1" data-testid="status-counters">
        {[
          { key: 'entry', label: 'Entry', color: 'text-emerald-600' },
          { key: 'moving', label: 'Moving', color: 'text-blue-600' },
          { key: 'watch', label: 'Watch', color: 'text-gray-500' },
          { key: 'avoid', label: 'Avoid', color: 'text-red-600' },
        ].map(s => {
          const count = grouped[s.key]?.length || 0;
          return (
            <button
              key={s.key}
              onClick={() => onNavigate('markets')}
              className="flex items-center gap-2 text-sm hover:opacity-80 transition-opacity"
              data-testid={`counter-${s.key}`}
            >
              <span className={`font-medium ${s.color}`}>{s.label}</span>
              <span className="text-lg font-semibold text-gray-900 tabular-nums">{count}</span>
            </button>
          );
        })}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        {/* ─── Top Opportunities ─── */}
        <Section
          title="Top Opportunities"
          action={grouped.entry?.length > 0 ? () => onNavigate('markets') : null}
          actionLabel="All markets"
        >
          {displayOps.length > 0 ? (
            <div className="space-y-1.5">
              {displayOps.map(c => <CompactRow key={c.id} c={c} />)}
            </div>
          ) : (
            <Empty text="No active opportunities. System is monitoring." />
          )}
        </Section>

        {/* ─── What Changed / Live Markets ─── */}
        <div className="space-y-5">
          {hotEvents.length > 0 && (
            <Section title="Live Markets" action={() => onNavigate('markets')} actionLabel="View all">
              <div className="space-y-2">
                {hotEvents.map(ev => <LiveRow key={ev.event_id} event={ev} />)}
              </div>
            </Section>
          )}

          {recentChanges.length > 0 && (
            <Section title="What Changed" action={() => onNavigate('signals')} actionLabel="All signals">
              <div className="space-y-2">
                {recentChanges.map((ma, i) => {
                  const isHigh = ma.priority === 'HIGH';
                  return (
                    <div key={i} className="flex items-start gap-2 text-sm" data-testid={`change-${i}`}>
                      <Activity className={`w-3 h-3 mt-0.5 flex-shrink-0 ${isHigh ? 'text-red-500' : 'text-gray-400'}`} />
                      <div>
                        <span className={`text-[10px] font-semibold uppercase tracking-wider mr-2 ${
                          isHigh ? 'text-red-500' : 'text-gray-400'
                        }`}>
                          {ma.type?.replace(/_/g, ' ')}
                        </span>
                        <span className="text-gray-600">{ma.summary}</span>
                      </div>
                    </div>
                  );
                })}
              </div>
            </Section>
          )}

          {topRisks.length > 0 && (
            <Section title="Main Risks">
              <div className="space-y-1.5">
                {topRisks.map((r, i) => (
                  <div key={i} className="flex items-center gap-2 text-sm" data-testid={`risk-${i}`}>
                    <AlertTriangle className="w-3 h-3 text-red-500 flex-shrink-0" />
                    <span className="font-medium text-red-600">{r.asset}</span>
                    <span className="text-gray-500">{r.reason}</span>
                  </div>
                ))}
              </div>
            </Section>
          )}
        </div>
      </div>
    </div>
  );
}

function Section({ title, action, actionLabel, children }) {
  return (
    <div>
      <div className="flex items-center justify-between mb-3">
        <h2 className="text-xs font-bold uppercase tracking-wider text-gray-400">{title}</h2>
        {action && (
          <button onClick={action} className="flex items-center gap-1 text-[10px] text-gray-400 hover:text-gray-600 transition-colors">
            {actionLabel} <ArrowRight className="w-3 h-3" />
          </button>
        )}
      </div>
      {children}
    </div>
  );
}

function CompactRow({ c }) {
  return (
    <div className="flex items-center justify-between py-2.5 px-3 rounded-lg bg-white border border-gray-200/80 hover:border-gray-300 transition-all"
         data-testid={`opp-${c.id}`}>
      <div className="flex items-center gap-3 min-w-0">
        {c.isHot && <Flame className="w-3 h-3 text-amber-500 flex-shrink-0" />}
        <div className="min-w-0">
          <h3 className="text-sm font-medium text-gray-900 truncate">{c.question}</h3>
          <p className="text-xs text-gray-400 truncate">{c.summary}</p>
        </div>
      </div>
      <div className="flex items-center gap-3 flex-shrink-0 ml-4">
        <span className={`text-xs font-medium ${c.edge.color}`}>Edge {c.edge.text}</span>
        <span className={`text-xs font-medium ${c.confidence.color}`}>Conf {c.confidence.text}</span>
        <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${
          c.statusKey === 'entry' ? 'bg-emerald-50 text-emerald-700' :
          c.statusKey === 'moving' ? 'bg-blue-50 text-blue-700' :
          'bg-gray-100 text-gray-500'
        }`}>
          {c.actionLabel}
        </span>
      </div>
    </div>
  );
}

function LiveRow({ event }) {
  const ov = event.overlay || {};
  const bp = ov.best_pick;
  const isAction = ov.action === 'BUY_YES' || ov.action === 'BUY_NO';

  return (
    <div className={`flex items-center justify-between py-2.5 px-3 rounded-lg border transition-all ${
      isAction
        ? 'bg-emerald-50/50 border-emerald-200/80 hover:border-emerald-300'
        : 'bg-white border-gray-200/80 hover:border-gray-300'
    }`} data-testid={`live-${event.event_id}`}>
      <div className="flex items-center gap-3 min-w-0">
        <span className="relative flex h-1.5 w-1.5 flex-shrink-0">
          <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
          <span className="relative inline-flex rounded-full h-1.5 w-1.5 bg-emerald-500"></span>
        </span>
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <span className="text-[10px] font-bold text-gray-400 uppercase">{event.asset_group}</span>
            <span className="text-[10px] text-gray-300">{event.event_type}</span>
          </div>
          <h3 className="text-sm font-medium text-gray-900 truncate">{event.title}</h3>
        </div>
      </div>
      <div className="flex items-center gap-3 flex-shrink-0 ml-4">
        {bp?.edge_pct != null && bp.edge_pct !== 0 && (
          <span className={`text-xs font-semibold ${bp.edge > 0 ? 'text-emerald-600' : 'text-red-600'}`}>
            {bp.edge > 0 ? '+' : ''}{bp.edge_pct}%
          </span>
        )}
        {isAction && (
          <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${
            ov.action === 'BUY_YES' ? 'bg-emerald-50 text-emerald-700' : 'bg-red-50 text-red-600'
          }`}>
            {ov.action === 'BUY_YES' ? 'BUY YES' : 'BUY NO'}
          </span>
        )}
      </div>
    </div>
  );
}

function Empty({ text }) {
  return <p className="text-sm text-gray-400 py-4">{text}</p>;
}
