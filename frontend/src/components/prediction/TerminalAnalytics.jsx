/**
 * TerminalAnalytics — Unified Analytics Dashboard.
 *
 * Single top-to-bottom layout:
 *   1. HERO (Trust/Performance + System State)
 *   2. VALIDATION QUEUE (Interactive — centerpiece)
 *   3. LIVE EDGE INTELLIGENCE (VERIFIED/STRONG only)
 *   4. MODEL PERFORMANCE (Compact Prediction Lab)
 *   5. MARKET STRUCTURE (Collapsed debug)
 */
import { useState, useEffect, useCallback } from 'react';
import {
  RefreshCw, Target, ArrowRightLeft, Activity, Shield,
  ChevronDown, ChevronUp, Radio, Zap, Clock, Eye,
  FlaskConical, Gauge, CheckCircle2, AlertTriangle,
} from 'lucide-react';

const API = process.env.REACT_APP_BACKEND_URL;

/* ─── Helpers ─── */
const timeAgo = (iso) => {
  if (!iso) return '';
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return 'just now';
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  return `${Math.floor(hrs / 24)}d ago`;
};

/* ─── Main Component ─── */
export default function TerminalAnalytics() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  const loadAll = useCallback(() => {
    setLoading(true);
    Promise.all([
      fetch(`${API}/api/outcome-lab/stats`).then(r => r.ok ? r.json() : null).catch(() => null),
      fetch(`${API}/api/cross-market/kalshi/analytics`).then(r => r.ok ? r.json() : null).catch(() => null),
      fetch(`${API}/api/cross-market/kalshi/validation-queue?status=PENDING&limit=20`).then(r => r.ok ? r.json() : null).catch(() => null),
      fetch(`${API}/api/cross-market/kalshi/validation-metrics`).then(r => r.ok ? r.json() : null).catch(() => null),
      fetch(`${API}/api/cross-market/kalshi/health`).then(r => r.ok ? r.json() : null).catch(() => null),
      fetch(`${API}/api/cross-market/kalshi/signals`).then(r => r.ok ? r.json() : null).catch(() => null),
      fetch(`${API}/api/prediction-lab/overview`).then(r => r.ok ? r.json() : null).catch(() => null),
    ]).then(([stats, analytics, vq, vm, health, signals, labOverview]) => {
      setData({
        stats,
        analytics,
        validationQueue: vq?.entries || [],
        validationMetrics: vm || {},
        health,
        signals: signals?.signals || [],
        labOverview,
      });
    }).finally(() => setLoading(false));
  }, []);

  useEffect(() => { loadAll(); }, [loadAll]);

  if (loading && !data) {
    return (
      <div className="flex items-center justify-center h-64 text-gray-400 text-sm" data-testid="analytics-loading">
        <RefreshCw className="w-4 h-4 animate-spin mr-2" /> Initializing analytics...
      </div>
    );
  }

  if (!data) return null;

  return (
    <div className="p-6 space-y-10" data-testid="terminal-analytics">
      <HeroSection
        stats={data.stats}
        health={data.health}
        signals={data.signals}
        validationMetrics={data.validationMetrics}
        analytics={data.analytics}
        onRefresh={loadAll}
        loading={loading}
      />
      <div className="h-px bg-gray-100" />
      <ValidationQueueSection
        queue={data.validationQueue}
        metrics={data.validationMetrics}
        onRefresh={loadAll}
      />
      <div className="h-px bg-gray-100" />
      <LiveEdgeSection signals={data.signals} />
      <div className="h-px bg-gray-100" />
      <ModelPerformanceSection labOverview={data.labOverview} />
      <MarketStructureSection
        analytics={data.analytics}
        health={data.health}
      />
    </div>
  );
}


/* ══════════════════════════════════════════════════════════════════
   1. HERO SECTION
   ══════════════════════════════════════════════════════════════════ */
function HeroSection({ stats, health, signals, validationMetrics, analytics, onRefresh, loading }) {
  // System state logic
  const verifiedSignals = (signals || []).filter(
    s => s.edge_badge === 'verified_edge' || s.severity === 'STRONG'
  );
  const hasEdge = verifiedSignals.length > 0;
  const isScanning = health?.running === true;
  const systemState = hasEdge ? 'EDGE DETECTED' : isScanning ? 'SCANNING' : 'IDLE';
  const stateStyle = {
    'EDGE DETECTED': { bg: 'bg-amber-50', text: 'text-amber-600', border: 'border-amber-200', dot: 'bg-amber-400' },
    'SCANNING':      { bg: 'bg-emerald-50', text: 'text-emerald-600', border: 'border-emerald-200', dot: 'bg-emerald-400' },
    'IDLE':          { bg: 'bg-gray-50', text: 'text-gray-400', border: 'border-gray-200', dot: 'bg-gray-300' },
  }[systemState];

  const acc = stats?.accuracy;
  const brier = stats?.avgBrier;
  const totalSignals = analytics?.total_signals_tracked || 0;
  const validated = validationMetrics?.validated || 0;
  const totalValidation = validationMetrics?.total || 0;
  const targetValidation = 10;

  // Signal density: rough estimate from total signals / hours since first signal
  const signalDensity = totalSignals > 0 && health?.total_rebuilds > 0
    ? (totalSignals / Math.max(health.total_rebuilds * (5 / 60), 1)).toFixed(1)
    : '0';

  // Last scan time
  const lastScan = health?.last_rebuild_at ? timeAgo(health.last_rebuild_at) : null;

  // Market context
  const marketContext = hasEdge ? 'Mispricing detected' : 'No mispricing detected';

  return (
    <div className="space-y-3" data-testid="hero-section">
      {/* Compact metrics grid + state */}
      <div className="flex items-center justify-between gap-4 flex-wrap">
        <div className="grid grid-cols-5 gap-5">
          <MetricBox
            label="Accuracy"
            value={acc != null ? `${Math.round(acc)}%` : '--'}
            color={acc >= 60 ? 'text-emerald-600' : acc >= 40 ? 'text-amber-600' : 'text-gray-500'}
          />
          <MetricBox
            label="Brier"
            value={brier != null ? brier.toFixed(3) : '--'}
            color={brier != null && brier < 0.25 ? 'text-emerald-600' : 'text-gray-500'}
          />
          <MetricBox
            label="Signals"
            value={totalSignals}
            color="text-gray-700"
          />
          <MetricBox
            label="Validated"
            value={`${validated} / ${targetValidation}`}
            color={validated >= targetValidation ? 'text-emerald-600' : 'text-amber-600'}
          />
          <MetricBox
            label="Sig/hour"
            value={signalDensity}
            color="text-gray-600"
          />
        </div>

        <div className="flex items-center gap-3">
          {/* System State Badge */}
          <div className={`flex items-center gap-2 px-3 py-2 rounded-lg border ${stateStyle.bg} ${stateStyle.border}`}
               data-testid="system-state-badge">
            <span className={`w-2 h-2 rounded-full ${stateStyle.dot} ${systemState === 'SCANNING' ? 'animate-pulse' : ''}`} />
            <div>
              <span className={`text-xs font-bold tracking-wide ${stateStyle.text}`}>{systemState}</span>
              <div className="text-[10px] text-gray-400">{marketContext}</div>
            </div>
          </div>

          <button
            onClick={onRefresh}
            disabled={loading}
            className="p-2 rounded-lg hover:bg-gray-100 transition-all disabled:opacity-50"
            data-testid="refresh-analytics-btn"
          >
            <RefreshCw className={`w-3.5 h-3.5 text-gray-400 ${loading ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </div>

      {/* System Activity line */}
      <div className="flex items-center gap-3 text-[10px] text-gray-400" data-testid="system-activity">
        <span className={`flex items-center gap-1 ${systemState === 'SCANNING' ? 'text-emerald-500' : systemState === 'EDGE DETECTED' ? 'text-amber-500' : 'text-gray-400'}`}>
          <span className={`w-1.5 h-1.5 rounded-full ${stateStyle.dot} ${systemState === 'SCANNING' ? 'animate-pulse' : ''}`} />
          {systemState}
        </span>
        <span className="text-gray-300">·</span>
        <span>Monitoring markets for mispricing</span>
        {lastScan && <><span className="text-gray-300">·</span><span>Last scan: {lastScan}</span></>}
        <span className="text-gray-300">·</span>
        <span>Rebuilds: {health?.total_rebuilds || 0}</span>
        {health?.total_material_changes > 0 && <><span className="text-gray-300">·</span><span>Changes: {health.total_material_changes}</span></>}
      </div>
    </div>
  );
}

function MetricBox({ label, value, color = 'text-gray-700' }) {
  return (
    <div data-testid={`metric-${label.toLowerCase().replace(/[\s/]+/g, '-')}`}>
      <div className="text-[10px] uppercase tracking-wider text-gray-400">{label}</div>
      <div className={`text-base font-medium ${color}`}>{value}</div>
    </div>
  );
}


/* ══════════════════════════════════════════════════════════════════
   2. VALIDATION QUEUE SECTION
   ══════════════════════════════════════════════════════════════════ */
function ValidationQueueSection({ queue, metrics, onRefresh }) {
  const [submitting, setSubmitting] = useState(null);
  const [notes, setNotes] = useState({});

  const verdicts = ['REAL_EDGE', 'FAKE_EDGE', 'EXECUTION_TRAP', 'TIMING_TRAP', 'AMBIGUOUS_RULES', 'SKIP'];
  const verdictStyles = {
    'REAL_EDGE':       'bg-emerald-100 text-emerald-700 hover:bg-emerald-200',
    'FAKE_EDGE':       'bg-red-100 text-red-700 hover:bg-red-200',
    'EXECUTION_TRAP':  'bg-amber-100 text-amber-700 hover:bg-amber-200',
    'TIMING_TRAP':     'bg-orange-100 text-orange-700 hover:bg-orange-200',
    'AMBIGUOUS_RULES': 'bg-purple-100 text-purple-700 hover:bg-purple-200',
    'SKIP':            'bg-gray-100 text-gray-500 hover:bg-gray-200',
  };
  const verdictLabels = {
    'REAL_EDGE': 'Real', 'FAKE_EDGE': 'Fake', 'EXECUTION_TRAP': 'Exec Trap',
    'TIMING_TRAP': 'Timing', 'AMBIGUOUS_RULES': 'Ambiguous', 'SKIP': 'Skip',
  };

  const handleVerdict = async (validationId, verdict) => {
    setSubmitting(validationId);
    try {
      await fetch(`${API}/api/cross-market/kalshi/validate/${validationId}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          manual_verdict: verdict,
          verdict_reason: notes[validationId] || '',
        }),
      });
      onRefresh?.();
    } catch (e) { console.error(e); }
    setSubmitting(null);
  };

  return (
    <div className="bg-white border-2 border-gray-200 rounded-xl p-6 shadow-sm hover:shadow-md transition-shadow space-y-4" data-testid="validation-queue-section">
      {/* Section header */}
      <div className="flex items-center justify-between">
        <div>
          <div className="flex items-center gap-2">
            <Target className="w-3.5 h-3.5 text-gray-500" />
            <h3 className="text-base font-semibold text-gray-900">Validation Queue</h3>
            {metrics?.pending > 0 && (
              <span className="text-[10px] font-bold text-amber-600 bg-amber-50 px-1.5 py-0.5 rounded" data-testid="pending-count">
                {metrics.pending} pending
              </span>
            )}
          </div>
          <p className="text-xs text-gray-500 mt-0.5 ml-5">Make decisions on detected market inefficiencies</p>
        </div>
        {/* Aggregate metrics */}
        {metrics?.validated > 0 && (
          <div className="flex items-center gap-3 text-[10px] text-gray-400" data-testid="validation-metrics-summary">
            {metrics.real_edge_rate != null && (
              <span className={metrics.real_edge_rate >= 60 ? 'text-emerald-600 font-semibold' : 'text-gray-500'}>
                Real: {metrics.real_edge_rate}%
              </span>
            )}
            {metrics.execution_rate != null && <span>Exec: {metrics.execution_rate}%</span>}
            {metrics.trap_rate != null && <span>Trap: {metrics.trap_rate}%</span>}
            <span>{metrics.validated}/{metrics.total} validated</span>
            {!metrics.sample_sufficient && <span className="text-amber-500">Need 10+ for conclusions</span>}
          </div>
        )}
      </div>

      {/* Validation by edge type table */}
      {metrics?.by_edge_type && metrics.by_edge_type.length > 0 && (
        <div className="overflow-x-auto" data-testid="validation-by-type-table">
          <table className="w-full text-xs">
            <thead>
              <tr className="text-left text-gray-400 border-b border-gray-100">
                <th className="pb-2 pr-4 font-medium">Edge Type</th>
                <th className="pb-2 pr-2 font-medium text-right">Total</th>
                <th className="pb-2 pr-2 font-medium text-right text-emerald-500">Real</th>
                <th className="pb-2 pr-2 font-medium text-right text-red-400">Fake</th>
                <th className="pb-2 pr-2 font-medium text-right text-amber-500">ExecTrap</th>
                <th className="pb-2 pr-2 font-medium text-right text-orange-500">Timing</th>
                <th className="pb-2 font-medium text-right">Real%</th>
              </tr>
            </thead>
            <tbody>
              {metrics.by_edge_type.map((row, i) => (
                <tr key={i} className="border-b border-gray-50">
                  <td className="py-1.5 pr-4 font-medium text-gray-700 capitalize">
                    {(row.edge_case_type || 'unknown').replace(/_/g, ' ').toLowerCase()}
                  </td>
                  <td className="py-1.5 pr-2 text-right text-gray-600">{row.total}</td>
                  <td className="py-1.5 pr-2 text-right text-emerald-600">{row.real}</td>
                  <td className="py-1.5 pr-2 text-right text-red-500">{row.fake}</td>
                  <td className="py-1.5 pr-2 text-right text-amber-600">{row.exec_trap}</td>
                  <td className="py-1.5 pr-2 text-right text-orange-600">{row.timing_trap}</td>
                  <td className="py-1.5 text-right">
                    <span className={row.real_edge_rate != null ? (row.real_edge_rate >= 60 ? 'text-emerald-600 font-semibold' : 'text-gray-500') : 'text-gray-400'}>
                      {row.real_edge_rate != null ? `${row.real_edge_rate}%` : '--'}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Queue cards */}
      {queue.length === 0 ? (
        <div className="py-10 text-center" data-testid="validation-empty">
          <Eye className="w-7 h-7 text-gray-300 mx-auto mb-3" />
          <p className="text-sm font-medium text-gray-700">System scanning markets</p>
          <p className="text-xs text-gray-400 mt-1">Signals will appear here when inefficiencies are detected</p>
        </div>
      ) : (
        <div className="space-y-2" data-testid="validation-entries">
          {queue.map((entry) => (
            <div key={entry.validation_id}
                 className="p-3 rounded-lg border border-gray-200 bg-white space-y-2"
                 data-testid={`validation-entry-${entry.validation_id}`}>
              {/* Row 1: Entity + Edge type + Gap + Timestamp */}
              <div className="flex items-center justify-between gap-2">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="text-sm font-semibold text-blue-600">{entry.entity}</span>
                  <span className="text-[10px] text-gray-400 capitalize">
                    {(entry.edge_case_type || '').replace(/_/g, ' ').toLowerCase()}
                  </span>
                  <span className="text-xs font-mono text-emerald-600">+{entry.gap_pct}%</span>
                  {entry.edge_badge === 'execution_risk' && (
                    <span className="text-[10px] text-amber-500 bg-amber-50 px-1 py-0.5 rounded">Exec Risk</span>
                  )}
                </div>
                <div className="flex items-center gap-3 text-[10px] text-gray-400 shrink-0">
                  <span>Conf: {entry.score?.toFixed(2)}</span>
                  <span>Act: {entry.actionability_score?.toFixed(2)}</span>
                  {entry.created_at && (
                    <span className="flex items-center gap-1">
                      <Clock className="w-3 h-3" />
                      {timeAgo(entry.created_at)}
                    </span>
                  )}
                </div>
              </div>
              {/* Row 2: Verdict buttons + notes */}
              <div className="flex items-center gap-1.5 flex-wrap">
                {verdicts.map(v => (
                  <button key={v}
                    onClick={() => handleVerdict(entry.validation_id, v)}
                    disabled={submitting === entry.validation_id}
                    className={`text-[10px] font-bold px-2 py-1 rounded transition-all ${verdictStyles[v]} disabled:opacity-50`}
                    data-testid={`verdict-${v.toLowerCase()}-${entry.validation_id}`}>
                    {verdictLabels[v]}
                  </button>
                ))}
                <input
                  type="text"
                  placeholder="Notes..."
                  value={notes[entry.validation_id] || ''}
                  onChange={(e) => setNotes(prev => ({ ...prev, [entry.validation_id]: e.target.value }))}
                  className="text-[10px] border border-gray-200 rounded px-2 py-1 flex-1 min-w-[120px] focus:outline-none focus:border-gray-400"
                  data-testid={`validation-notes-${entry.validation_id}`}
                />
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}


/* ══════════════════════════════════════════════════════════════════
   3. LIVE EDGE INTELLIGENCE
   ══════════════════════════════════════════════════════════════════ */
function LiveEdgeSection({ signals }) {
  // Only show VERIFIED (verified_edge badge) or STRONG severity
  const strong = (signals || []).filter(
    s => s.edge_badge === 'verified_edge' || s.severity === 'STRONG'
  );

  return (
    <div className="border border-gray-100 rounded-lg p-6 space-y-3" data-testid="live-edge-section">
      <div>
        <div className="flex items-center gap-2">
          <Zap className="w-3.5 h-3.5 text-gray-500" />
          <h3 className="text-base font-semibold text-gray-900">Live Edge Intelligence</h3>
          {strong.length > 0 && (
            <span className="text-[10px] font-bold text-emerald-600 bg-emerald-50 px-1.5 py-0.5 rounded">
              {strong.length} active
            </span>
          )}
        </div>
        <p className="text-xs text-gray-500 mt-0.5 ml-5">Real-time detected opportunities</p>
      </div>

      {strong.length === 0 ? (
        <div className="py-6 text-center" data-testid="edge-empty">
          <Radio className="w-5 h-5 text-gray-300 mx-auto mb-2" />
          <p className="text-sm text-gray-400">Only STRONG / VERIFIED signals appear here</p>
          <p className="text-xs text-gray-300 mt-1">No actionable mispricing detected</p>
        </div>
      ) : (
        <div className="space-y-2" data-testid="edge-signals">
          {strong.map((s, i) => (
            <div key={s.cluster_id || i}
                 className="p-3 rounded-lg border border-emerald-100 bg-white flex items-center justify-between gap-3"
                 data-testid={`edge-signal-${s.cluster_id}`}>
              <div className="flex items-center gap-3 flex-wrap">
                <span className="text-sm font-semibold text-gray-900">{s.entity}</span>
                <span className="text-[10px] capitalize text-gray-400">
                  {(s.edge_case_type || '').replace(/_/g, ' ').toLowerCase()}
                </span>
                <span className="text-xs font-mono text-emerald-600 font-bold">+{s.gap_pct}%</span>
                {s.edge_badge === 'verified_edge' && (
                  <span className="text-[10px] font-bold text-emerald-700 bg-emerald-50 border border-emerald-200 px-1.5 py-0.5 rounded">
                    VERIFIED
                  </span>
                )}
                {s.trap_flags?.length > 0 && (
                  <span className="text-[10px] text-amber-500">
                    <AlertTriangle className="w-3 h-3 inline mr-0.5" />
                    {s.trap_flags.join(', ')}
                  </span>
                )}
              </div>
              <div className="flex items-center gap-4 text-[10px] text-gray-400 tabular-nums shrink-0">
                <span>Score: {s.score?.toFixed(3)}</span>
                <span>Act: {s.actionability_score?.toFixed(3)}</span>
                {s.real_edge_score != null && <span>RealEdge: {s.real_edge_score.toFixed(3)}</span>}
                {s.strategy && (
                  <span className="text-xs font-bold text-blue-600">{s.strategy.strategy_type}</span>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}


/* ══════════════════════════════════════════════════════════════════
   4. MODEL PERFORMANCE (Compact Prediction Lab)
   ══════════════════════════════════════════════════════════════════ */
function ModelPerformanceSection({ labOverview }) {
  const d = labOverview;
  const hasData = d && d.validated_results > 0;

  return (
    <div className="bg-gray-50 border border-gray-100 rounded-lg p-6 space-y-3" data-testid="model-performance-section">
      <div className="flex items-center gap-2">
        <FlaskConical className="w-3.5 h-3.5 text-gray-400" />
        <h3 className="text-sm font-medium text-gray-500">Model Performance</h3>
      </div>

      {!d ? (
        <div className="py-4 text-center" data-testid="model-loading">
          <p className="text-xs text-gray-400">Initializing model tracking...</p>
        </div>
      ) : !hasData ? (
        <div data-testid="model-empty">
          <div className="flex items-center gap-3">
            <Gauge className="w-4 h-4 text-gray-300" />
            <div>
              <p className="text-xs text-gray-500">
                {d.total_forecasts > 0
                  ? `${d.total_forecasts} forecasts tracking`
                  : 'No forecasts yet. Browse markets to generate predictions.'
                }
              </p>
              <p className="text-[10px] text-gray-400 mt-0.5">
                {d.total_forecasts > 0
                  ? 'Awaiting market resolution to compute accuracy'
                  : 'Calibration: Waiting for resolved data'
                }
              </p>
            </div>
          </div>
        </div>
      ) : (
        <div className="space-y-3">
          {/* Compact KPI row */}
          <div className="flex items-center gap-6 flex-wrap">
            <MiniMetric label="Accuracy" value={`${Math.round(d.accuracy * 100)}%`}
                        color={d.accuracy >= 0.55 ? 'text-emerald-600' : 'text-amber-600'} />
            <MiniMetric label="Brier" value={d.avg_brier?.toFixed(3) || '--'}
                        color={d.avg_brier < 0.2 ? 'text-emerald-600' : 'text-gray-600'} />
            <MiniMetric label="Forecasts" value={d.total_forecasts} color="text-gray-600" />
            <MiniMetric label="Resolved" value={d.resolved_forecasts} color="text-gray-600" />
            <MiniMetric label="Pending" value={d.pending_forecasts} color="text-gray-400" />
          </div>

          {/* Calibration status */}
          <div className="flex items-center gap-2 text-xs">
            <Shield className={`w-3.5 h-3.5 ${
              d.calibration_verdict === 'Well calibrated' ? 'text-emerald-500' : 'text-amber-500'
            }`} />
            <span className="text-gray-600">
              Calibration: <span className="font-medium">{d.calibration_verdict || 'Waiting for resolved data'}</span>
            </span>
          </div>

          {/* Best/Worst families compact */}
          {(d.best_families?.length > 0 || d.worst_families?.length > 0) && (
            <div className="flex gap-4 flex-wrap">
              {d.best_families?.slice(0, 3).map((f, i) => (
                <div key={i} className="flex items-center gap-2 text-xs">
                  <CheckCircle2 className="w-3 h-3 text-emerald-500" />
                  <span className="text-gray-600 font-mono text-[10px] truncate max-w-[150px]">{f.family_key}</span>
                  <span className="text-emerald-600 font-bold">{Math.round((f.correct_rate || 0) * 100)}%</span>
                </div>
              ))}
              {d.worst_families?.slice(0, 2).map((f, i) => (
                <div key={i} className="flex items-center gap-2 text-xs">
                  <AlertTriangle className="w-3 h-3 text-red-400" />
                  <span className="text-gray-600 font-mono text-[10px] truncate max-w-[150px]">{f.family_key}</span>
                  <span className="text-red-500 font-bold">{Math.round((f.correct_rate || 0) * 100)}%</span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function MiniMetric({ label, value, color }) {
  return (
    <div className="flex items-center gap-1.5">
      <span className="text-[10px] text-gray-400 uppercase tracking-wider">{label}</span>
      <span className={`text-sm font-bold ${color}`}>{value}</span>
    </div>
  );
}


/* ══════════════════════════════════════════════════════════════════
   5. MARKET STRUCTURE (Collapsed by default)
   ══════════════════════════════════════════════════════════════════ */
function MarketStructureSection({ analytics, health }) {
  const [open, setOpen] = useState(false);

  const byType = analytics?.by_edge_type || [];
  const byPair = analytics?.by_platform_pair || [];
  const total = analytics?.total_signals_tracked || 0;
  const familyCount = byType.length;

  // Context label
  const contextLabel = total > 0
    ? `${total} signals tracked`
    : familyCount > 0
      ? `Monitoring ${familyCount} edge types`
      : 'Monitoring markets';

  return (
    <div className="border-t border-gray-100 pt-4 opacity-80" data-testid="market-structure-section">
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-2 w-full text-left group"
        data-testid="market-structure-toggle"
      >
        <ArrowRightLeft className="w-3 h-3 text-gray-300" />
        <h3 className="text-xs font-medium text-gray-400 group-hover:text-gray-600 transition-colors">
          Market Structure
        </h3>
        <span className="text-[10px] text-gray-400 bg-gray-50 px-1.5 py-0.5 rounded">
          {contextLabel}
        </span>
        {open
          ? <ChevronUp className="w-3.5 h-3.5 text-gray-400 ml-auto" />
          : <ChevronDown className="w-3.5 h-3.5 text-gray-400 ml-auto" />
        }
      </button>

      {open && (
        <div className="mt-4 space-y-4" data-testid="market-structure-content">
          {/* Edge Type Performance */}
          {byType.length > 0 && (
            <div className="overflow-x-auto">
              <table className="w-full text-xs" data-testid="edge-type-table">
                <thead>
                  <tr className="text-left text-gray-400 border-b border-gray-100">
                    <th className="pb-2 pr-4 font-medium">Edge Type</th>
                    <th className="pb-2 pr-3 font-medium text-right">Count</th>
                    <th className="pb-2 pr-3 font-medium text-right">Actionable</th>
                    <th className="pb-2 pr-3 font-medium text-right">Avg Edge</th>
                    <th className="pb-2 pr-3 font-medium text-right">Win Rate</th>
                    <th className="pb-2 pr-3 font-medium text-right">Capture</th>
                    <th className="pb-2 font-medium text-right">Exec Rate</th>
                  </tr>
                </thead>
                <tbody>
                  {byType.map((row, i) => (
                    <tr key={i} className="border-b border-gray-50 hover:bg-gray-50/50">
                      <td className="py-2 pr-4 font-medium text-gray-700 capitalize">
                        {(row.edge_case_type || 'unknown').replace(/_/g, ' ').toLowerCase()}
                      </td>
                      <td className="py-2 pr-3 text-right text-gray-600 tabular-nums">{row.count}</td>
                      <td className="py-2 pr-3 text-right text-gray-600 tabular-nums">{row.actionable_count}</td>
                      <td className="py-2 pr-3 text-right text-emerald-600 font-mono tabular-nums">
                        {row.avg_predicted_edge != null ? `${row.avg_predicted_edge}%` : '--'}
                      </td>
                      <td className="py-2 pr-3 text-right tabular-nums">
                        <span className={row.win_rate != null ? (row.win_rate >= 60 ? 'text-emerald-600' : 'text-amber-600') : 'text-gray-400'}>
                          {row.win_rate != null ? `${row.win_rate}%` : '--'}
                        </span>
                      </td>
                      <td className="py-2 pr-3 text-right tabular-nums">
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

          {/* Platform Pair Breakdown */}
          {byPair.length > 0 && (
            <div>
              <div className="text-xs font-bold uppercase tracking-wider text-gray-400 mb-2">By Platform Pair</div>
              <div className="space-y-1">
                {byPair.map((row, i) => (
                  <div key={i} className="flex items-center justify-between text-xs py-1 border-b border-gray-50">
                    <div className="flex items-center gap-2">
                      <span className="text-gray-400">{(row.platform_pair || '').replace('_', '/')}</span>
                      <span className="font-medium text-gray-700 capitalize">
                        {(row.edge_case_type || '').replace(/_/g, ' ').toLowerCase()}
                      </span>
                    </div>
                    <div className="flex items-center gap-4 text-gray-500 tabular-nums">
                      <span>{row.count} signals</span>
                      <span>{row.actionable_count} actionable</span>
                      <span className="text-emerald-600">{row.avg_predicted_edge != null ? `${row.avg_predicted_edge}%` : '--'}</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Rebuild Health */}
          <RebuildHealthCompact data={health} />

          {total === 0 && (
            <p className="text-xs text-gray-400 text-center py-4">
              No structure anomalies detected. Data will populate as the system identifies cross-platform mispricings.
            </p>
          )}
        </div>
      )}
    </div>
  );
}


function RebuildHealthCompact({ data }) {
  if (!data) return null;

  const toggleAutoRebuild = async (start) => {
    const endpoint = start ? 'start' : 'stop';
    await fetch(`${API}/api/cross-market/kalshi/auto-rebuild/${endpoint}`, { method: 'POST' });
  };

  return (
    <div className="flex items-center justify-between py-3 border-t border-gray-100" data-testid="rebuild-health-compact">
      <div className="flex items-center gap-3">
        <RefreshCw className="w-3 h-3 text-gray-400" />
        <span className="text-xs text-gray-600">Rebuild Health</span>
        <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded ${data.running ? 'text-emerald-600 bg-emerald-50' : 'text-gray-400 bg-gray-100'}`}>
          {data.running ? 'AUTO' : 'MANUAL'}
        </span>
        <span className="text-[10px] text-gray-400">
          Rebuilds: {data.total_rebuilds || 0} | Skipped: {data.total_skipped || 0} | This hr: {data.rebuilds_this_hour || 0}/{data.max_rebuilds_per_hour}
        </span>
        {data.last_strong_signals > 0 && (
          <span className="text-[10px] text-emerald-600 font-semibold">Signals: {data.last_strong_signals}</span>
        )}
      </div>
      <button
        onClick={() => toggleAutoRebuild(!data.running)}
        className={`text-[10px] font-medium px-2 py-1 rounded border transition-all ${data.running ? 'text-red-500 border-red-200 hover:bg-red-50' : 'text-emerald-600 border-emerald-200 hover:bg-emerald-50'}`}
        data-testid="toggle-auto-rebuild">
        {data.running ? 'Stop' : 'Start'}
      </button>
    </div>
  );
}
