import { useState, useEffect, useCallback } from 'react';
import {
  dashboardApi,
  OverviewData, CalibrationData, InteractionData,
  DecisionData, DistributionData, AlertsData,
} from './lib/dashboardApi';
import Card from './components/Card';
import { Loader2, RefreshCw, AlertTriangle } from 'lucide-react';

const HORIZONS = ['all', '24H', '7D', '30D'] as const;
const PERIODS  = ['24h', '7d', '30d', 'all'] as const;

function Toggle({ options, value, onChange, label }: {
  options: readonly string[]; value: string; onChange: (v: string) => void; label: string;
}) {
  return (
    <div className="flex items-center gap-2" data-testid={`toggle-${label.toLowerCase()}`}>
      <span className="text-xs font-medium text-gray-500 uppercase tracking-wide w-16">{label}</span>
      <div className="flex bg-gray-100 rounded-lg p-0.5">
        {options.map(o => (
          <button
            key={o}
            onClick={() => onChange(o)}
            data-testid={`toggle-${label.toLowerCase()}-${o.toLowerCase()}`}
            className={`px-3 py-1 text-xs font-medium rounded-md transition-all ${
              value === o
                ? 'bg-white text-gray-900 shadow-sm'
                : 'text-gray-500 hover:text-gray-700'
            }`}
          >
            {o === 'all' ? 'All' : o}
          </button>
        ))}
      </div>
    </div>
  );
}

function Metric({ label, value, sub, warn }: { label: string; value: string; sub?: string; warn?: boolean }) {
  return (
    <div>
      <div className="text-xs text-gray-500">{label}</div>
      <div className={`text-lg font-bold ${warn ? 'text-amber-600' : 'text-gray-900'}`}>{value}</div>
      {sub && <div className="text-xs text-gray-400">{sub}</div>}
    </div>
  );
}

function SampleBadge({ n }: { n: number }) {
  const low = n < 50;
  return (
    <div className={`flex items-center gap-1 text-xs font-medium ${low ? 'text-amber-600' : 'text-gray-400'}`}
         data-testid="sample-badge">
      {low && <AlertTriangle className="w-3 h-3" />}
      N = {n}
    </div>
  );
}

/* ─── Overview Panel ─── */
function OverviewPanel({ d }: { d: OverviewData }) {
  return (
    <Card title="Overview" right={<SampleBadge n={d.sample_size} />}>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4" data-testid="overview-panel">
        <Metric label="Total Forecasts" value={String(d.total_forecasts)} />
        <Metric label="Evaluated" value={`${d.evaluated} (${d.evaluated_pct.toFixed(1)}%)`} />
        <Metric label="Hit Rate" value={`${(d.hit_rate * 100).toFixed(1)}%`} />
        <Metric label="FP Rate" value={`${(d.fp_rate * 100).toFixed(1)}%`} warn={d.fp_rate > 0.5} />
        <Metric label="Avg Error" value={`${d.avg_error.toFixed(1)}%`} />
        <div className="col-span-2 md:col-span-3">
          <div className="text-xs text-gray-500 mb-1">Active Layers</div>
          <div className="flex flex-wrap gap-1.5">
            {Object.entries(d.active_layers).map(([k, v]) => (
              <span key={k} className={`text-xs px-2 py-0.5 rounded-full font-medium ${
                v ? 'bg-emerald-100 text-emerald-700' : 'bg-gray-100 text-gray-400'
              }`} data-testid={`layer-${k}`}>
                {k.replace(/_/g, ' ')}
              </span>
            ))}
          </div>
        </div>
      </div>
    </Card>
  );
}

/* ─── Calibration Panel ─── */
function CalibrationPanel({ d }: { d: CalibrationData }) {
  return (
    <Card title="Calibration" right={<SampleBadge n={d.sample_size} />}>
      <div data-testid="calibration-panel">
        <div className="grid grid-cols-3 gap-4 mb-4">
          <Metric label="ECE" value={d.ece != null ? d.ece.toFixed(4) : '—'} warn={d.ece != null && d.ece > 0.08} />
          <Metric label="Brier" value={d.brier != null ? d.brier.toFixed(4) : '—'} warn={d.brier != null && d.brier > 0.28} />
          <Metric label="Sharpness" value={d.sharpness != null ? d.sharpness.toFixed(4) : '—'} />
        </div>
        {d.buckets.length > 0 && (
          <div className="space-y-1.5">
            <div className="text-xs text-gray-500">Reliability Diagram</div>
            {d.buckets.map((b, i) => {
              const gap = Math.abs(b.conf - b.actual);
              return (
                <div key={i} className="flex items-center gap-2 text-xs">
                  <div className="w-10 text-right text-gray-500">{(b.conf * 100).toFixed(0)}%</div>
                  <div className="flex-1 h-3 bg-gray-100 rounded-full overflow-hidden relative">
                    <div className="absolute h-full bg-blue-200 rounded-full" style={{ width: `${b.conf * 100}%` }} />
                    <div className={`absolute h-full rounded-full ${gap > 0.05 ? 'bg-red-400' : 'bg-emerald-400'}`}
                         style={{ width: `${b.actual * 100}%` }} />
                  </div>
                  <div className="w-10 text-gray-500">{(b.actual * 100).toFixed(0)}%</div>
                  <div className="w-10 text-right text-gray-400">n={b.count}</div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </Card>
  );
}

/* ─── Interaction Panel ─── */
function InteractionPanel({ d }: { d: InteractionData }) {
  const states = ['aligned', 'fragile', 'conflict', 'range'];
  const stateColors: Record<string, string> = {
    aligned: 'bg-emerald-100 text-emerald-700',
    fragile: 'bg-amber-100 text-amber-700',
    conflict: 'bg-red-100 text-red-700',
    range: 'bg-blue-100 text-blue-700',
  };

  return (
    <Card title="Interaction Layer" right={<SampleBadge n={d.sample_size} />}>
      <div className="space-y-4" data-testid="interaction-panel">
        {/* State Distribution */}
        <div>
          <div className="text-xs text-gray-500 mb-2">State Distribution</div>
          <div className="flex gap-2">
            {states.map(s => (
              <div key={s} className={`flex-1 text-center py-1.5 rounded-lg text-xs font-medium ${stateColors[s] || 'bg-gray-100'}`}>
                {s}<br/><span className="text-sm font-bold">{((d.state_distribution[s] || 0) * 100).toFixed(0)}%</span>
              </div>
            ))}
          </div>
        </div>
        {/* Performance by State */}
        <div>
          <div className="text-xs text-gray-500 mb-2">Performance by State</div>
          <div className="space-y-1">
            {d.performance_by_state.map(p => (
              <div key={p.state} className="flex items-center gap-2 text-xs">
                <span className={`px-2 py-0.5 rounded-full font-medium ${stateColors[p.state] || 'bg-gray-100'}`}>{p.state}</span>
                <span className="text-gray-600">acc: <strong>{(p.accuracy * 100).toFixed(1)}%</strong></span>
                <span className={`${p.fp_rate > 0.5 ? 'text-red-600 font-semibold' : 'text-gray-600'}`}>
                  FP: {(p.fp_rate * 100).toFixed(1)}%
                </span>
                <span className="text-gray-400 ml-auto">n={p.count}</span>
              </div>
            ))}
          </div>
        </div>
        {/* Confidence Flow */}
        <div>
          <div className="text-xs text-gray-500 mb-1">Confidence Flow</div>
          <div className="flex items-center gap-3 text-sm">
            <span className="text-gray-600">Before: <strong>{d.confidence_flow.avg_before?.toFixed(3) ?? '—'}</strong></span>
            <span className="text-gray-400">→</span>
            <span className="text-gray-600">After: <strong>{d.confidence_flow.avg_after?.toFixed(3) ?? '—'}</strong></span>
            <span className={`font-semibold ${
              (d.confidence_flow.avg_delta ?? 0) > 0 ? 'text-emerald-600' : 
              (d.confidence_flow.avg_delta ?? 0) < 0 ? 'text-red-600' : 'text-gray-600'
            }`}>
              ({d.confidence_flow.avg_delta != null ? (d.confidence_flow.avg_delta > 0 ? '+' : '') + d.confidence_flow.avg_delta.toFixed(4) : '—'})
            </span>
          </div>
        </div>
        {/* Confidence Delta by state */}
        {Object.keys(d.confidence_delta).length > 0 && (
          <div>
            <div className="text-xs text-gray-500 mb-1">Confidence Delta by State</div>
            <div className="flex gap-2">
              {states.map(s => {
                const v = d.confidence_delta[s];
                if (v === undefined) return null;
                return (
                  <div key={s} className="text-xs text-center">
                    <div className="text-gray-400">{s}</div>
                    <div className={`font-semibold ${v > 0 ? 'text-emerald-600' : v < 0 ? 'text-red-600' : 'text-gray-600'}`}>
                      {v > 0 ? '+' : ''}{v.toFixed(4)}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}
      </div>
    </Card>
  );
}

/* ─── Decision Panel ─── */
function DecisionPanel({ d }: { d: DecisionData }) {
  const dirs = ['LONG', 'SHORT', 'NEUTRAL'];
  const dirColors: Record<string, string> = {
    LONG: 'bg-emerald-500', SHORT: 'bg-red-500', NEUTRAL: 'bg-gray-400',
  };

  return (
    <Card title="Decision" right={<SampleBadge n={d.sample_size} />}>
      <div className="space-y-4" data-testid="decision-panel">
        <div>
          <div className="text-xs text-gray-500 mb-2">Direction Distribution</div>
          <div className="flex h-6 rounded-full overflow-hidden">
            {dirs.map(dir => {
              const pct = (d.direction_distribution[dir] || 0) * 100;
              if (pct === 0) return null;
              return <div key={dir} className={`${dirColors[dir]}`} style={{ width: `${pct}%` }} title={`${dir}: ${pct.toFixed(1)}%`} />;
            })}
          </div>
          <div className="flex justify-between mt-1 text-xs text-gray-500">
            {dirs.map(dir => (
              <span key={dir}>{dir}: {((d.direction_distribution[dir] || 0) * 100).toFixed(1)}%</span>
            ))}
          </div>
        </div>
        {d.by_horizon.length > 0 && (
          <div>
            <div className="text-xs text-gray-500 mb-2">By Horizon</div>
            <div className="space-y-1.5">
              {d.by_horizon.map(h => (
                <div key={h.horizon} className="flex items-center gap-2 text-xs">
                  <span className="w-10 font-medium text-gray-700">{h.horizon}</span>
                  <div className="flex-1 flex h-4 rounded overflow-hidden">
                    <div className="bg-emerald-500" style={{ width: `${h.long * 100}%` }} />
                    <div className="bg-red-500" style={{ width: `${h.short * 100}%` }} />
                    <div className="bg-gray-300" style={{ width: `${h.neutral * 100}%` }} />
                  </div>
                  <span className="w-16 text-gray-400 text-right">N={((h.long + h.short + h.neutral) > 0 ? '~' : '0')}</span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </Card>
  );
}

/* ─── Distribution Panel ─── */
function DistributionPanel({ d }: { d: DistributionData }) {
  const maxCount = Math.max(...d.confidence_histogram.map(b => b.count), 1);
  return (
    <Card title="Confidence Distribution">
      <div className="space-y-1.5" data-testid="distribution-panel">
        {d.confidence_histogram.map((b, i) => (
          <div key={i} className="flex items-center gap-2 text-xs">
            <span className="w-16 text-right text-gray-500">{b.bucket}</span>
            <div className="flex-1 h-5 bg-gray-100 rounded overflow-hidden">
              <div className="h-full bg-indigo-400 rounded transition-all" style={{ width: `${(b.count / maxCount) * 100}%` }} />
            </div>
            <span className="w-10 text-right text-gray-600 font-medium">{b.count}</span>
          </div>
        ))}
      </div>
    </Card>
  );
}

/* ─── Alerts Panel ─── */
function AlertsPanel({ d }: { d: AlertsData }) {
  const severityColors: Record<string, string> = {
    high: 'bg-red-50 border-red-200 text-red-700',
    medium: 'bg-amber-50 border-amber-200 text-amber-700',
    low: 'bg-emerald-50 border-emerald-200 text-emerald-700',
  };
  return (
    <Card title="Alerts">
      <div className="space-y-2" data-testid="alerts-panel">
        {d.alerts.map((a, i) => (
          <div key={i} className={`text-xs px-3 py-2 rounded-lg border ${severityColors[a.severity] || 'bg-gray-50 border-gray-200 text-gray-700'}`}>
            <span className="font-semibold mr-1">{a.type}:</span>{a.message}
          </div>
        ))}
      </div>
    </Card>
  );
}

/* ═══ Main Dashboard ═══ */
export default function DecisionIntelDashboard() {
  const [horizon, setHorizon] = useState('all');
  const [period, setPeriod] = useState('7d');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [overview, setOverview] = useState<OverviewData | null>(null);
  const [calibration, setCalibration] = useState<CalibrationData | null>(null);
  const [interaction, setInteraction] = useState<InteractionData | null>(null);
  const [decision, setDecision] = useState<DecisionData | null>(null);
  const [distribution, setDistribution] = useState<DistributionData | null>(null);
  const [alerts, setAlerts] = useState<AlertsData | null>(null);

  const fetchAll = useCallback(async () => {
    setLoading(true);
    setError(null);
    const f = { horizon, period };
    try {
      const [ov, cal, inter, dec, dist, al] = await Promise.all([
        dashboardApi.overview(f),
        dashboardApi.calibration(f),
        dashboardApi.interaction(f),
        dashboardApi.decision(f),
        dashboardApi.distribution(f),
        dashboardApi.alerts(f),
      ]);
      setOverview(ov);
      setCalibration(cal);
      setInteraction(inter);
      setDecision(dec);
      setDistribution(dist);
      setAlerts(al);
    } catch (e: any) {
      setError(e.message || 'Failed to load');
    } finally {
      setLoading(false);
    }
  }, [horizon, period]);

  useEffect(() => { fetchAll(); }, [fetchAll]);

  // Auto-refresh every 30s
  useEffect(() => {
    const id = setInterval(fetchAll, 30000);
    return () => clearInterval(id);
  }, [fetchAll]);

  return (
    <div className="min-h-screen bg-gray-50 p-6" data-testid="decision-intel-dashboard">
      <div className="max-w-7xl mx-auto space-y-4">
        {/* Header + Filters */}
        <div className="bg-white rounded-xl p-4">
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
            <div>
              <h1 className="text-lg font-bold text-gray-900" data-testid="dashboard-title">
                Decision Intelligence Monitor
              </h1>
              <p className="text-xs text-gray-500">Stage 2 Live • Interaction + Meta Calibration</p>
            </div>
            <div className="flex items-center gap-4">
              <Toggle options={HORIZONS} value={horizon} onChange={setHorizon} label="Horizon" />
              <Toggle options={PERIODS} value={period} onChange={setPeriod} label="Period" />
              <button onClick={fetchAll} className="p-1.5 rounded-lg hover:bg-gray-100 transition-colors"
                      data-testid="refresh-btn">
                <RefreshCw className={`w-4 h-4 text-gray-500 ${loading ? 'animate-spin' : ''}`} />
              </button>
            </div>
          </div>
        </div>

        {error && (
          <div className="bg-red-50 border border-red-200 rounded-lg p-3 text-sm text-red-700" data-testid="error-msg">
            {error}
          </div>
        )}

        {loading && !overview ? (
          <div className="flex items-center justify-center h-64">
            <Loader2 className="w-8 h-8 text-gray-400 animate-spin" />
          </div>
        ) : (
          <>
            {/* Row 1: Overview */}
            {overview && <OverviewPanel d={overview} />}

            {/* Row 2: Interaction + Calibration */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
              {interaction && <InteractionPanel d={interaction} />}
              {calibration && <CalibrationPanel d={calibration} />}
            </div>

            {/* Row 3: Decision + Distribution */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
              {decision && <DecisionPanel d={decision} />}
              {distribution && <DistributionPanel d={distribution} />}
            </div>

            {/* Row 4: Alerts */}
            {alerts && <AlertsPanel d={alerts} />}
          </>
        )}

        {/* Footer */}
        <div className="text-center text-xs text-gray-400 py-2">
          Auto-refresh every 30s • Horizon: {horizon} • Period: {period}
        </div>
      </div>
    </div>
  );
}
