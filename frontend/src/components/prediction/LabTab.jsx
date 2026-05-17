/**
 * LabTab — Prediction Lab: Truth Engine Dashboard.
 *
 * Decision-grade analytics UI:
 *   - Overview KPIs (Accuracy, Brier, Calibration Verdict, Opportunity Rate)
 *   - Calibration buckets (Predicted vs Actual)
 *   - Best/Worst Family tables with verdict badges
 *   - Dimension breakdown (by asset, market type, expiry, liquidity)
 *   - Recent Mistakes & Correct with root cause context
 *   - Manual Resolve / Recalculate controls
 */
import { useState, useEffect, useCallback } from 'react';
import {
  RefreshCw, FlaskConical, Target, TrendingUp, TrendingDown,
  AlertTriangle, CheckCircle2, XCircle, Clock, Crosshair,
  BarChart3, Gauge, Activity, ArrowUpRight, ArrowDownRight,
  ChevronDown, ChevronUp, Zap, Shield,
} from 'lucide-react';

const API = process.env.REACT_APP_BACKEND_URL;

/* ─── Helpers ─── */
const pct = (v, dec = 1) => v != null ? `${(v * 100).toFixed(dec)}%` : '—';
const num = (v, dec = 2) => v != null ? v.toFixed(dec) : '—';
const fmtDate = (iso) => {
  if (!iso) return '—';
  try {
    const d = new Date(iso);
    return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
  } catch { return '—'; }
};

const VERDICT_STYLES = {
  STRONG: 'bg-emerald-50 text-emerald-700 border-emerald-200',
  WEAK: 'bg-red-50 text-red-700 border-red-200',
  MODERATE: 'bg-amber-50 text-amber-700 border-amber-200',
};

const ACTION_STYLES = {
  BUY_YES: 'bg-emerald-500 text-white',
  BUY_NO: 'bg-red-500 text-white',
  WATCH: 'bg-amber-100 text-amber-800',
  AVOID: 'bg-gray-100 text-gray-500',
};

/* ─── Main Component ─── */
export default function LabTab() {
  const [overview, setOverview] = useState(null);
  const [loading, setLoading] = useState(true);
  const [resolving, setResolving] = useState(false);
  const [recalculating, setRecalculating] = useState(false);
  const [section, setSection] = useState('overview');

  const fetchOverview = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API}/api/prediction-lab/overview`);
      if (res.ok) setOverview(await res.json());
    } catch (e) { console.error('Lab fetch error:', e); }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { fetchOverview(); }, [fetchOverview]);

  const handleResolve = async () => {
    setResolving(true);
    try {
      await fetch(`${API}/api/prediction-lab/resolve`, { method: 'POST' });
      await fetchOverview();
    } catch (e) { console.error(e); }
    finally { setResolving(false); }
  };

  const handleRecalculate = async () => {
    setRecalculating(true);
    try {
      await fetch(`${API}/api/prediction-lab/recalculate`, { method: 'POST' });
      await fetchOverview();
    } catch (e) { console.error(e); }
    finally { setRecalculating(false); }
  };

  if (loading && !overview) {
    return (
      <div className="flex items-center justify-center h-64 text-gray-400 text-sm" data-testid="lab-loading">
        <RefreshCw className="w-4 h-4 animate-spin mr-2" /> Loading Prediction Lab...
      </div>
    );
  }

  if (!overview) return null;
  const d = overview;

  const SECTIONS = [
    { id: 'overview', label: 'Overview' },
    { id: 'calibration', label: 'Calibration' },
    { id: 'families', label: 'Families' },
    { id: 'dimensions', label: 'Dimensions' },
    { id: 'results', label: 'Results' },
  ];

  return (
    <div className="p-6 space-y-5 max-w-[1400px] mx-auto" data-testid="lab-tab">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div className="flex items-center gap-3">
          <FlaskConical className="w-5 h-5 text-indigo-500" />
          <div>
            <h2 className="text-lg font-bold text-gray-900">Prediction Lab</h2>
            <p className="text-xs text-gray-400">Truth Engine — Model Validation & Calibration</p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={handleResolve}
            disabled={resolving}
            data-testid="lab-resolve-btn"
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium bg-indigo-50 text-indigo-700 rounded-lg hover:bg-indigo-100 transition-all disabled:opacity-50"
          >
            <Crosshair className={`w-3.5 h-3.5 ${resolving ? 'animate-spin' : ''}`} />
            Resolve
          </button>
          <button
            onClick={handleRecalculate}
            disabled={recalculating}
            data-testid="lab-recalculate-btn"
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200 transition-all disabled:opacity-50"
          >
            <BarChart3 className={`w-3.5 h-3.5 ${recalculating ? 'animate-spin' : ''}`} />
            Recalculate
          </button>
          <button
            onClick={fetchOverview}
            disabled={loading}
            data-testid="lab-refresh-btn"
            className="p-1.5 rounded-lg hover:bg-gray-100 transition-all disabled:opacity-50"
          >
            <RefreshCw className={`w-4 h-4 text-gray-400 ${loading ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </div>

      {/* Section tabs */}
      <div className="flex items-center gap-1 bg-gray-100 rounded-lg p-1 w-fit" data-testid="lab-sections">
        {SECTIONS.map((s) => (
          <button
            key={s.id}
            onClick={() => setSection(s.id)}
            data-testid={`lab-section-${s.id}`}
            className={`px-3 py-1.5 text-sm font-medium rounded-md transition-all ${
              section === s.id ? 'bg-white text-gray-900 shadow-sm' : 'text-gray-500 hover:text-gray-700'
            }`}
          >
            {s.label}
          </button>
        ))}
      </div>

      {section === 'overview' && <OverviewSection d={d} />}
      {section === 'calibration' && <CalibrationSection buckets={d.calibration} />}
      {section === 'families' && <FamiliesSection best={d.best_families} worst={d.worst_families} />}
      {section === 'dimensions' && <DimensionsSection dims={d.dimensions} />}
      {section === 'results' && <ResultsSection correct={d.recent_correct} mistakes={d.recent_mistakes} />}
    </div>
  );
}


/* ─── Overview Section ─── */
function OverviewSection({ d }) {
  const hasData = d.validated_results > 0;

  return (
    <div className="space-y-4" data-testid="lab-overview-section">
      {/* KPI row */}
      <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-3">
        <KpiCard
          label="Forecasts"
          value={d.total_forecasts}
          sub={`${d.pending_forecasts} pending`}
          icon={FlaskConical}
          color="text-indigo-500"
        />
        <KpiCard
          label="Resolved"
          value={d.resolved_forecasts}
          sub={d.stale_forecasts > 0 ? `${d.stale_forecasts} stale` : 'tracking'}
          icon={Target}
          color="text-blue-500"
        />
        <KpiCard
          label="Accuracy"
          value={hasData ? pct(d.accuracy, 1) : '—'}
          sub={hasData ? `${d.validated_results} validated` : 'awaiting resolution'}
          icon={CheckCircle2}
          color={hasData && d.accuracy >= 0.55 ? 'text-emerald-500' : hasData ? 'text-amber-500' : 'text-gray-400'}
          highlight={hasData}
        />
        <KpiCard
          label="Avg Brier"
          value={hasData ? num(d.avg_brier, 3) : '—'}
          sub={hasData ? (d.avg_brier < 0.2 ? 'Good' : d.avg_brier < 0.3 ? 'Fair' : 'Poor') : 'no data'}
          icon={Gauge}
          color={hasData && d.avg_brier < 0.2 ? 'text-emerald-500' : hasData && d.avg_brier < 0.3 ? 'text-amber-500' : 'text-gray-400'}
        />
        <KpiCard
          label="Opportunity"
          value={d.opportunity_rate != null ? pct(d.opportunity_rate, 0) : '—'}
          sub="price moved our way"
          icon={ArrowUpRight}
          color={d.opportunity_rate >= 0.6 ? 'text-emerald-500' : 'text-gray-400'}
        />
        <KpiCard
          label="Entry Quality"
          value={d.avg_entry_quality != null ? num(d.avg_entry_quality, 3) : '—'}
          sub="lower is better"
          icon={Activity}
          color="text-blue-500"
        />
      </div>

      {/* Calibration verdict card */}
      <div className="bg-white border border-gray-200 rounded-xl p-4" data-testid="lab-calibration-verdict">
        <div className="flex items-center gap-3">
          <div className={`w-10 h-10 rounded-lg flex items-center justify-center ${
            d.calibration_verdict === 'Well calibrated' ? 'bg-emerald-50' :
            d.calibration_verdict.includes('Slightly') ? 'bg-amber-50' :
            d.calibration_verdict.includes('Overconfident') ? 'bg-red-50' : 'bg-gray-50'
          }`}>
            <Shield className={`w-5 h-5 ${
              d.calibration_verdict === 'Well calibrated' ? 'text-emerald-500' :
              d.calibration_verdict.includes('Slightly') ? 'text-amber-500' :
              d.calibration_verdict.includes('Overconfident') ? 'text-red-500' : 'text-gray-400'
            }`} />
          </div>
          <div>
            <div className="text-sm font-semibold text-gray-900">
              Calibration: {d.calibration_verdict}
            </div>
            <div className="text-xs text-gray-400">
              {d.avg_realized_edge != null
                ? `Avg Realized Edge: ${d.avg_realized_edge > 0 ? '+' : ''}${pct(d.avg_realized_edge, 2)}`
                : 'No resolution data yet — forecasts are being tracked'
              }
            </div>
          </div>
        </div>
      </div>

      {/* Quick family preview */}
      {(d.best_families?.length > 0 || d.worst_families?.length > 0) && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {d.best_families?.length > 0 && (
            <div className="bg-white border border-gray-200 rounded-xl p-4" data-testid="lab-best-families-preview">
              <div className="flex items-center gap-2 mb-3">
                <TrendingUp className="w-4 h-4 text-emerald-500" />
                <span className="text-sm font-semibold text-gray-900">Best Families</span>
              </div>
              {d.best_families.slice(0, 3).map((f, i) => (
                <div key={i} className="flex items-center justify-between py-1.5 border-b border-gray-50 last:border-0">
                  <span className="text-xs text-gray-600 font-mono truncate max-w-[200px]">{f.family_key}</span>
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-semibold text-emerald-600">{pct(f.correct_rate, 0)}</span>
                    <span className={`text-[10px] px-1.5 py-0.5 rounded border ${VERDICT_STYLES[f.verdict]}`}>{f.verdict}</span>
                  </div>
                </div>
              ))}
            </div>
          )}
          {d.worst_families?.length > 0 && (
            <div className="bg-white border border-gray-200 rounded-xl p-4" data-testid="lab-worst-families-preview">
              <div className="flex items-center gap-2 mb-3">
                <TrendingDown className="w-4 h-4 text-red-500" />
                <span className="text-sm font-semibold text-gray-900">Worst Families</span>
              </div>
              {d.worst_families.slice(0, 3).map((f, i) => (
                <div key={i} className="flex items-center justify-between py-1.5 border-b border-gray-50 last:border-0">
                  <span className="text-xs text-gray-600 font-mono truncate max-w-[200px]">{f.family_key}</span>
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-semibold text-red-600">{pct(f.correct_rate, 0)}</span>
                    <span className={`text-[10px] px-1.5 py-0.5 rounded border ${VERDICT_STYLES[f.verdict]}`}>{f.verdict}</span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Empty state */}
      {!hasData && (
        <div className="bg-gray-50 border border-dashed border-gray-200 rounded-xl p-8 text-center" data-testid="lab-empty-state">
          <FlaskConical className="w-8 h-8 text-gray-300 mx-auto mb-3" />
          <div className="text-sm font-medium text-gray-500">
            {d.total_forecasts > 0
              ? `${d.total_forecasts} forecasts recording. Awaiting market resolution...`
              : 'No forecasts yet. Browse the Feed to start generating predictions.'
            }
          </div>
          <div className="text-xs text-gray-400 mt-1">
            The Truth Engine validates predictions automatically when markets close.
          </div>
        </div>
      )}
    </div>
  );
}


/* ─── KPI Card ─── */
function KpiCard({ label, value, sub, icon: Icon, color, highlight }) {
  return (
    <div className={`bg-white border rounded-xl p-3.5 transition-all ${highlight ? 'border-gray-300 shadow-sm' : 'border-gray-200'}`}>
      <div className="flex items-center gap-2 mb-1">
        <Icon className={`w-3.5 h-3.5 ${color}`} />
        <span className="text-xs text-gray-400 font-medium">{label}</span>
      </div>
      <div className="text-xl font-bold text-gray-900">{value}</div>
      <div className="text-[10px] text-gray-400 mt-0.5">{sub}</div>
    </div>
  );
}


/* ─── Calibration Section ─── */
function CalibrationSection({ buckets }) {
  if (!buckets || buckets.length === 0) {
    return (
      <div className="bg-gray-50 border border-dashed border-gray-200 rounded-xl p-8 text-center" data-testid="lab-calibration-empty">
        <Gauge className="w-8 h-8 text-gray-300 mx-auto mb-3" />
        <div className="text-sm text-gray-500">No calibration data yet. Run Recalculate after some forecasts resolve.</div>
      </div>
    );
  }

  return (
    <div className="space-y-4" data-testid="lab-calibration-section">
      <div className="text-sm font-semibold text-gray-900">Global Calibration</div>

      {/* Chart-like horizontal bars */}
      <div className="bg-white border border-gray-200 rounded-xl overflow-hidden">
        <div className="grid grid-cols-5 gap-0 text-[10px] text-gray-400 font-medium px-4 pt-3 pb-1 border-b border-gray-100">
          <div>Bucket</div>
          <div className="text-right">Predicted</div>
          <div className="text-right">Actual</div>
          <div className="text-right">Cal Error</div>
          <div className="text-right">Samples</div>
        </div>
        {buckets.map((b, i) => {
          const predicted = b.avg_predicted || 0;
          const actual = b.actual_hit_rate || 0;
          const calErr = b.calibration_error || 0;
          const overconfident = predicted > actual;

          return (
            <div key={i} className="grid grid-cols-5 gap-0 px-4 py-2.5 border-b border-gray-50 last:border-0 items-center hover:bg-gray-50/50">
              <div className="text-xs font-mono text-gray-700">{b.bucket}</div>
              <div className="text-right">
                <span className="text-xs font-semibold text-gray-700">{pct(predicted, 1)}</span>
              </div>
              <div className="text-right">
                <span className={`text-xs font-semibold ${actual > 0 ? 'text-indigo-600' : 'text-gray-400'}`}>
                  {pct(actual, 1)}
                </span>
              </div>
              <div className="text-right">
                <span className={`text-xs font-mono px-1.5 py-0.5 rounded ${
                  calErr < 0.05 ? 'bg-emerald-50 text-emerald-700' :
                  calErr < 0.10 ? 'bg-amber-50 text-amber-700' :
                  'bg-red-50 text-red-700'
                }`}>
                  {pct(calErr, 1)}
                  {b.sample_size > 0 && (
                    <span className="text-[9px] ml-1 opacity-60">
                      {overconfident ? 'OC' : 'UC'}
                    </span>
                  )}
                </span>
              </div>
              <div className="text-right text-xs text-gray-400">{b.sample_size}</div>
            </div>
          );
        })}
      </div>

      {/* Visual bars */}
      <div className="bg-white border border-gray-200 rounded-xl p-4">
        <div className="text-xs text-gray-400 font-medium mb-3">Predicted vs Actual Hit Rate</div>
        <div className="space-y-2">
          {buckets.filter(b => b.sample_size > 0).map((b, i) => (
            <div key={i} className="flex items-center gap-3">
              <div className="w-20 text-[10px] font-mono text-gray-500 shrink-0">{b.bucket}</div>
              <div className="flex-1 relative h-5">
                <div className="absolute inset-y-0 left-0 bg-gray-200 rounded-full"
                     style={{ width: `${(b.avg_predicted || 0) * 100}%` }} />
                <div className="absolute inset-y-0 left-0 bg-indigo-400 rounded-full opacity-70"
                     style={{ width: `${(b.actual_hit_rate || 0) * 100}%` }} />
              </div>
            </div>
          ))}
        </div>
        <div className="flex items-center gap-4 mt-2 text-[10px] text-gray-400">
          <div className="flex items-center gap-1"><div className="w-3 h-2 bg-gray-200 rounded" /> Predicted</div>
          <div className="flex items-center gap-1"><div className="w-3 h-2 bg-indigo-400 rounded opacity-70" /> Actual</div>
        </div>
      </div>
    </div>
  );
}


/* ─── Families Section ─── */
function FamiliesSection({ best, worst }) {
  const allFamilies = [...(best || []), ...(worst || [])];
  if (allFamilies.length === 0) {
    return (
      <div className="bg-gray-50 border border-dashed border-gray-200 rounded-xl p-8 text-center" data-testid="lab-families-empty">
        <BarChart3 className="w-8 h-8 text-gray-300 mx-auto mb-3" />
        <div className="text-sm text-gray-500">No family data yet. Needs resolved forecasts + recalculation.</div>
      </div>
    );
  }

  return (
    <div className="space-y-4" data-testid="lab-families-section">
      {best?.length > 0 && <FamilyTable title="Strong Families" families={best} icon={TrendingUp} iconColor="text-emerald-500" />}
      {worst?.length > 0 && <FamilyTable title="Weak Families" families={worst} icon={TrendingDown} iconColor="text-red-500" />}
    </div>
  );
}


function FamilyTable({ title, families, icon: Icon, iconColor }) {
  return (
    <div className="bg-white border border-gray-200 rounded-xl overflow-hidden">
      <div className="px-4 py-3 border-b border-gray-100 flex items-center gap-2">
        <Icon className={`w-4 h-4 ${iconColor}`} />
        <span className="text-sm font-semibold text-gray-900">{title}</span>
        <span className="text-xs text-gray-400 ml-1">({families.length})</span>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-xs">
          <thead>
            <tr className="text-gray-400 font-medium border-b border-gray-100">
              <th className="text-left px-4 py-2">Family</th>
              <th className="text-right px-3 py-2">Accuracy</th>
              <th className="text-right px-3 py-2">Brier</th>
              <th className="text-right px-3 py-2">Edge</th>
              <th className="text-right px-3 py-2">Samples</th>
              <th className="text-right px-4 py-2">Verdict</th>
            </tr>
          </thead>
          <tbody>
            {families.map((f, i) => (
              <tr key={i} className="border-b border-gray-50 last:border-0 hover:bg-gray-50/50">
                <td className="px-4 py-2.5 font-mono text-gray-700 max-w-[250px] truncate">{f.family_key}</td>
                <td className="text-right px-3 py-2.5 font-semibold text-gray-800">{pct(f.correct_rate, 0)}</td>
                <td className="text-right px-3 py-2.5 text-gray-600">{num(f.avg_brier, 3)}</td>
                <td className={`text-right px-3 py-2.5 font-medium ${f.avg_realized_edge > 0 ? 'text-emerald-600' : 'text-red-500'}`}>
                  {f.avg_realized_edge > 0 ? '+' : ''}{pct(f.avg_realized_edge, 1)}
                </td>
                <td className="text-right px-3 py-2.5 text-gray-400">{f.sample_size}</td>
                <td className="text-right px-4 py-2.5">
                  <span className={`text-[10px] px-2 py-0.5 rounded-full border font-medium ${VERDICT_STYLES[f.verdict]}`}>
                    {f.verdict}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}


/* ─── Dimensions Section ─── */
function DimensionsSection({ dims }) {
  const dimEntries = Object.entries(dims || {});
  if (dimEntries.length === 0) {
    return (
      <div className="bg-gray-50 border border-dashed border-gray-200 rounded-xl p-8 text-center" data-testid="lab-dimensions-empty">
        <BarChart3 className="w-8 h-8 text-gray-300 mx-auto mb-3" />
        <div className="text-sm text-gray-500">No dimension data yet.</div>
      </div>
    );
  }

  const dimLabels = {
    market_type: 'Market Type',
    asset: 'Asset',
    expiry_bucket: 'Expiry',
    liquidity_bucket: 'Liquidity',
  };

  return (
    <div className="space-y-4" data-testid="lab-dimensions-section">
      <div className="text-sm font-semibold text-gray-900">Performance by Dimension</div>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        {dimEntries.map(([dimName, items]) => (
          <div key={dimName} className="bg-white border border-gray-200 rounded-xl p-4">
            <div className="text-xs font-semibold text-gray-700 mb-3">{dimLabels[dimName] || dimName}</div>
            <div className="space-y-2">
              {items.sort((a, b) => (b.correct_rate || 0) - (a.correct_rate || 0)).map((item, i) => (
                <div key={i} className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-mono text-gray-600">{item.dimension_value || item.family_key?.split(':')[1] || '?'}</span>
                    <span className="text-[10px] text-gray-400">n={item.sample_size}</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <div className="w-16 h-1.5 bg-gray-100 rounded-full overflow-hidden">
                      <div
                        className={`h-full rounded-full ${item.correct_rate >= 0.55 ? 'bg-emerald-400' : item.correct_rate >= 0.45 ? 'bg-amber-400' : 'bg-red-400'}`}
                        style={{ width: `${(item.correct_rate || 0) * 100}%` }}
                      />
                    </div>
                    <span className={`text-xs font-semibold w-10 text-right ${
                      item.correct_rate >= 0.55 ? 'text-emerald-600' : item.correct_rate >= 0.45 ? 'text-amber-600' : 'text-red-500'
                    }`}>
                      {pct(item.correct_rate, 0)}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}


/* ─── Results Section ─── */
function ResultsSection({ correct, mistakes }) {
  return (
    <div className="space-y-4" data-testid="lab-results-section">
      {/* Tab-like toggle */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        <div>
          <div className="flex items-center gap-2 mb-3">
            <XCircle className="w-4 h-4 text-red-500" />
            <span className="text-sm font-semibold text-gray-900">Recent Mistakes</span>
            <span className="text-xs text-gray-400">({mistakes?.length || 0})</span>
          </div>
          {(!mistakes || mistakes.length === 0) ? (
            <div className="bg-gray-50 border border-dashed border-gray-200 rounded-xl p-6 text-center text-xs text-gray-400">
              No mistakes recorded yet
            </div>
          ) : (
            <div className="space-y-2">
              {mistakes.map((r, i) => <ResultCard key={i} result={r} type="mistake" />)}
            </div>
          )}
        </div>

        <div>
          <div className="flex items-center gap-2 mb-3">
            <CheckCircle2 className="w-4 h-4 text-emerald-500" />
            <span className="text-sm font-semibold text-gray-900">Recent Correct</span>
            <span className="text-xs text-gray-400">({correct?.length || 0})</span>
          </div>
          {(!correct || correct.length === 0) ? (
            <div className="bg-gray-50 border border-dashed border-gray-200 rounded-xl p-6 text-center text-xs text-gray-400">
              No correct predictions yet
            </div>
          ) : (
            <div className="space-y-2">
              {correct.map((r, i) => <ResultCard key={i} result={r} type="correct" />)}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}


function ResultCard({ result, type }) {
  const r = result;
  const isMistake = type === 'mistake';

  // Build root-cause hints for mistakes
  const hints = [];
  if (isMistake) {
    if (r.confidence === 'high') hints.push('Overconfidence');
    if (r.confidence === 'low') hints.push('Low conviction');
    if (r.brier_score > 0.4) hints.push('High Brier');
    if (r.entry_quality > 0.1) hints.push('Poor timing');
    if (!r.opportunity_captured) hints.push('No opportunity window');
    if (r.edge_pct && Math.abs(r.edge_pct) < 3) hints.push('Thin edge');
  }

  return (
    <div className={`bg-white border rounded-xl p-3 ${isMistake ? 'border-red-100' : 'border-emerald-100'}`}>
      <div className="flex items-start justify-between gap-2 mb-1.5">
        <div className="text-xs font-medium text-gray-800 leading-tight line-clamp-2 flex-1">
          {r.question || r.event_id}
        </div>
        <span className={`text-[10px] px-2 py-0.5 rounded-full font-semibold shrink-0 ${ACTION_STYLES[r.action] || 'bg-gray-100 text-gray-500'}`}>
          {r.action}
        </span>
      </div>

      <div className="flex items-center gap-3 text-[10px] text-gray-400">
        <span>Edge: {r.edge_pct != null ? `${r.edge_pct > 0 ? '+' : ''}${r.edge_pct.toFixed(1)}%` : '—'}</span>
        <span>Conf: {r.confidence}</span>
        <span>Brier: {num(r.brier_score, 3)}</span>
        <span>Size: {r.size_label || '—'}</span>
        {r.opportunity_captured != null && (
          <span className={r.opportunity_captured ? 'text-emerald-500' : 'text-red-400'}>
            {r.opportunity_captured ? 'Opp captured' : 'No opp'}
          </span>
        )}
      </div>

      {hints.length > 0 && (
        <div className="flex items-center gap-1 mt-1.5 flex-wrap">
          {hints.map((h, i) => (
            <span key={i} className="text-[9px] px-1.5 py-0.5 bg-red-50 text-red-600 rounded border border-red-100">{h}</span>
          ))}
        </div>
      )}

      <div className="text-[10px] text-gray-300 mt-1">{fmtDate(r.resolved_at)}</div>
    </div>
  );
}
