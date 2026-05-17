/**
 * AnalyticsTab — colored value labels for stats.
 */
import { useState, useEffect } from 'react';
import { RefreshCw, ArrowRightLeft } from 'lucide-react';

const API = process.env.REACT_APP_BACKEND_URL;

export default function AnalyticsTab() {
  const [digest, setDigest] = useState(null);
  const [stats, setStats] = useState(null);
  const [cpAnalytics, setCpAnalytics] = useState(null);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);

  useEffect(() => {
    setLoading(true);
    Promise.all([
      fetch(`${API}/api/prediction/weekly-digest/latest`).then(r => r.ok ? r.json() : null).catch(() => null),
      fetch(`${API}/api/outcome-lab/stats`).then(r => r.ok ? r.json() : null).catch(() => null),
      fetch(`${API}/api/cross-market/kalshi/analytics`).then(r => r.ok ? r.json() : null).catch(() => null),
    ]).then(([dg, st, cp]) => {
      setDigest(dg?.digest || null);
      setStats(st || null);
      setCpAnalytics(cp || null);
    }).finally(() => setLoading(false));
  }, []);

  const handleGenerate = () => {
    setGenerating(true);
    fetch(`${API}/api/prediction/weekly-digest/generate`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}',
    }).then(r => r.ok ? r.json() : null)
      .then(d => { if (d?.digest) setDigest(d.digest); })
      .finally(() => setGenerating(false));
  };

  if (loading) return <div className="flex items-center justify-center h-64 text-gray-400 text-sm">Loading analytics...</div>;

  const acc = stats?.accuracy ?? digest?.performance?.accuracy;
  const accColor = acc == null ? 'text-gray-900' : acc >= 60 ? 'text-emerald-600' : acc >= 40 ? 'text-amber-600' : 'text-red-500';

  const execLabel = qualityObj(digest?.executionQuality?.avgScore ?? (stats?.avgCalibrationError != null ? 1 - stats.avgCalibrationError : null));
  const timingLabel = qualityObj(digest?.timing?.avgTimingQuality);

  const sysState = digest?.comparison?.systemState;
  const sysColor = sysState === 'IMPROVING' ? 'text-emerald-600' : sysState === 'DEGRADING' ? 'text-red-500' : 'text-gray-900';

  return (
    <div className="px-6 py-5 space-y-6" data-testid="analytics-tab">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-medium text-gray-900">Analytics</h2>
        <button
          onClick={handleGenerate} disabled={generating}
          className="px-3 py-1.5 bg-gray-900 text-white rounded-lg text-xs font-medium hover:bg-gray-800 transition-all disabled:opacity-50 flex items-center gap-1.5"
          data-testid="generate-digest-btn"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${generating ? 'animate-spin' : ''}`} />
          {generating ? 'Generating...' : 'Refresh Digest'}
        </button>
      </div>

      {/* Stats — colored values */}
      <div className="flex items-center gap-8">
        <Stat label="Accuracy" value={acc != null ? `${acc}%` : '--'} color={accColor} />
        <Stat label="Execution" value={execLabel.text} color={execLabel.color} />
        <Stat label="Timing" value={timingLabel.text} color={timingLabel.color} />
        <Stat label="Markets" value={digest?.performance?.totalMarkets || stats?.traceStats?.uniqueMarkets || '--'} color="text-gray-900" />
      </div>

      {/* Improved / Degraded */}
      {digest?.comparison && (
        <div className="grid grid-cols-2 gap-6">
          <div>
            <div className="text-xs text-emerald-600 font-medium mb-1">Improved</div>
            <p className="text-sm text-gray-600">{digest.comparison.biggestImprovement || 'No significant improvements'}</p>
            {digest.comparison.metricDeltas?.filter(d => d.direction === 'UP').slice(0, 3).map((d, i) => (
              <div key={i} className="text-xs text-emerald-600 mt-0.5">{d.metric}: +{d.delta?.toFixed(1)}</div>
            ))}
          </div>
          <div>
            <div className="text-xs text-red-500 font-medium mb-1">Degraded</div>
            <p className="text-sm text-gray-600">{digest.comparison.biggestDegradation || 'No significant degradations'}</p>
            {digest.comparison.metricDeltas?.filter(d => d.direction === 'DOWN').slice(0, 3).map((d, i) => (
              <div key={i} className="text-xs text-red-500 mt-0.5">{d.metric}: {d.delta?.toFixed(1)}</div>
            ))}
          </div>
        </div>
      )}

      {/* Lessons / Mistakes */}
      <div className="grid grid-cols-2 gap-6">
        {digest?.lessons?.length > 0 && (
          <div>
            <div className="text-xs text-emerald-600 font-medium mb-1">Lessons</div>
            {digest.lessons.map((l, i) => <div key={i} className="text-sm text-gray-600 leading-relaxed">+ {l}</div>)}
          </div>
        )}
        {digest?.mistakes?.length > 0 && (
          <div>
            <div className="text-xs text-red-500 font-medium mb-1">Mistakes</div>
            {digest.mistakes.map((m, i) => <div key={i} className="text-sm text-gray-500 leading-relaxed">- {m}</div>)}
          </div>
        )}
      </div>

      {/* Missed */}
      {digest?.missedOpportunities?.length > 0 && (
        <div>
          <div className="text-xs text-amber-600 font-medium mb-1">Missed Opportunities</div>
          {digest.missedOpportunities.map((m, i) => (
            <div key={i} className="text-sm text-gray-600 mb-0.5">
              <span className="font-medium text-gray-900">{m.asset}</span>
              <span className="text-red-500 ml-1">+{(m.missedEdge * 100).toFixed(0)}%</span>
              <span className="text-gray-500 ml-2">{m.reason}</span>
            </div>
          ))}
        </div>
      )}

      {/* System State */}
      {sysState && (
        <div>
          <div className="text-xs text-gray-400 mb-1">System State</div>
          <span className={`text-sm font-semibold ${sysColor}`}>{sysState}</span>
        </div>
      )}

      {!digest && !stats && !cpAnalytics?.total_signals_tracked && (
        <p className="text-sm text-gray-400 py-6">Analytics are forming. Click "Refresh Digest" to generate the first report.</p>
      )}

      {/* Cross-Platform Edge Analytics */}
      <CrossPlatformAnalytics data={cpAnalytics} />
    </div>
  );
}

function CrossPlatformAnalytics({ data }) {
  if (!data) return null;

  const byType = data.by_edge_type || [];
  const byPair = data.by_platform_pair || [];
  const total = data.total_signals_tracked || 0;

  return (
    <div className="space-y-4 pt-4 border-t border-gray-100" data-testid="cp-analytics">
      <div className="flex items-center gap-2">
        <ArrowRightLeft className="w-4 h-4 text-blue-500" />
        <h3 className="text-sm font-medium text-gray-900">Cross-Platform Edge Analytics</h3>
        <span className="text-xs text-gray-400 bg-gray-100 px-1.5 py-0.5 rounded">
          {total} signals tracked
        </span>
      </div>

      {total === 0 ? (
        <p className="text-sm text-gray-400">No cross-platform signals tracked yet. Signals will appear as the system detects mispricings.</p>
      ) : (
        <>
          {/* Edge Case Type Performance Table */}
          {byType.length > 0 && (
            <div className="overflow-x-auto">
              <table className="w-full text-xs" data-testid="edge-type-table">
                <thead>
                  <tr className="text-left text-gray-400 border-b border-gray-100">
                    <th className="pb-2 pr-4 font-medium">Edge Type</th>
                    <th className="pb-2 pr-4 font-medium text-right">Count</th>
                    <th className="pb-2 pr-4 font-medium text-right">Actionable</th>
                    <th className="pb-2 pr-4 font-medium text-right">Avg Edge</th>
                    <th className="pb-2 pr-4 font-medium text-right">Avg Score</th>
                    <th className="pb-2 pr-4 font-medium text-right">Win Rate</th>
                    <th className="pb-2 pr-4 font-medium text-right">Realized</th>
                    <th className="pb-2 pr-4 font-medium text-right">Capture</th>
                    <th className="pb-2 font-medium text-right">Exec Rate</th>
                  </tr>
                </thead>
                <tbody>
                  {byType.map((row, i) => (
                    <tr key={i} className="border-b border-gray-50 hover:bg-gray-50/50">
                      <td className="py-2 pr-4">
                        <span className="font-medium text-gray-700 capitalize">
                          {(row.edge_case_type || 'unknown').replace(/_/g, ' ').toLowerCase()}
                        </span>
                      </td>
                      <td className="py-2 pr-4 text-right text-gray-600 tabular-nums">{row.count}</td>
                      <td className="py-2 pr-4 text-right text-gray-600 tabular-nums">{row.actionable_count}</td>
                      <td className="py-2 pr-4 text-right text-emerald-600 font-mono tabular-nums">
                        {row.avg_predicted_edge != null ? `${row.avg_predicted_edge}%` : '--'}
                      </td>
                      <td className="py-2 pr-4 text-right text-gray-600 tabular-nums">
                        {row.avg_score != null ? row.avg_score.toFixed(3) : '--'}
                      </td>
                      <td className="py-2 pr-4 text-right tabular-nums">
                        <span className={row.win_rate != null ? (row.win_rate >= 60 ? 'text-emerald-600' : row.win_rate >= 40 ? 'text-amber-600' : 'text-red-500') : 'text-gray-400'}>
                          {row.win_rate != null ? `${row.win_rate}%` : '--'}
                        </span>
                      </td>
                      <td className="py-2 pr-4 text-right text-gray-600 tabular-nums">
                        {row.avg_realized_edge != null ? `${row.avg_realized_edge}%` : '--'}
                      </td>
                      <td className="py-2 pr-4 text-right tabular-nums">
                        <span className={row.edge_capture_ratio != null ? (row.edge_capture_ratio >= 1.0 ? 'text-emerald-600 font-semibold' : 'text-amber-600') : 'text-gray-400'}>
                          {row.edge_capture_ratio != null ? row.edge_capture_ratio.toFixed(2) : '--'}
                        </span>
                      </td>
                      <td className="py-2 text-right text-gray-600 tabular-nums">
                        {row.execution_success_rate != null ? `${row.execution_success_rate}%` : '--'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {/* Platform Pair + Type Breakdown */}
          {byPair.length > 0 && (
            <div>
              <div className="text-xs font-bold uppercase tracking-wider text-gray-400 mb-2">By Platform Pair + Type</div>
              <div className="space-y-1">
                {byPair.map((row, i) => (
                  <div key={i} className="flex items-center justify-between text-xs py-1 border-b border-gray-50">
                    <div className="flex items-center gap-2">
                      <span className="text-gray-400">{(row.platform_pair || '').replace('_', '/')}</span>
                      <span className="font-medium text-gray-700 capitalize">
                        {(row.edge_case_type || 'unknown').replace(/_/g, ' ').toLowerCase()}
                      </span>
                    </div>
                    <div className="flex items-center gap-4 text-gray-500 tabular-nums">
                      <span>{row.count} signals</span>
                      <span>{row.actionable_count} actionable</span>
                      <span className="text-emerald-600">{row.avg_predicted_edge != null ? `${row.avg_predicted_edge}% avg` : '--'}</span>
                      <span>{row.win_rate != null ? `${row.win_rate}% win` : '--'}</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}

function Stat({ label, value, color }) {
  return (
    <div>
      <div className="text-xs text-gray-400">{label}</div>
      <div className={`text-lg font-semibold tabular-nums ${color}`}>{value}</div>
    </div>
  );
}

function qualityObj(score) {
  if (score == null) return { text: '--', color: 'text-gray-900' };
  if (score >= 0.7) return { text: 'Good', color: 'text-emerald-600' };
  if (score >= 0.45) return { text: 'Average', color: 'text-amber-600' };
  return { text: 'Weak', color: 'text-red-500' };
}
