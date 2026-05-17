/**
 * Intelligence Console — Block 4 + Block 6 UI Dashboard
 * =====================================================
 * Операционный дашборд для мониторинга системы Market Intelligence.
 * 6 секций на одном экране. Русский язык.
 *
 * Sections:
 *  1. Здоровье системы (System Health)
 *  2. Производительность фаз (Phase Performance)
 *  3. Производительность режимов (Regime Performance)
 *  4. Сценарный движок (Scenario Engine)
 *  5. Drift Intelligence
 *  6. Тактика + Execution Impact
 */

import { useState, useEffect, useCallback } from 'react';
import AdminLayout from '../../components/admin/AdminLayout';
import {
  Activity, TrendingUp, TrendingDown, Minus, ArrowUp, ArrowDown,
  Shield, AlertTriangle, Zap, BarChart3, Crosshair, Radar,
  RefreshCw, Loader2, ChevronDown,
} from 'lucide-react';

const API = process.env.REACT_APP_BACKEND_URL;

const RANGES = [
  { key: '7d', label: '7 дней' },
  { key: '30d', label: '30 дней' },
  { key: '90d', label: '90 дней' },
  { key: 'all', label: 'Все время' },
];

/* ── Utility ─────────────────────────────────────────── */
function pct(v) { return `${(v * 100).toFixed(1)}%`; }
function signed(v) {
  if (typeof v !== 'number') return '—';
  const s = v > 0 ? '+' : '';
  return `${s}${(v * 100).toFixed(1)}%`;
}

function DeltaBadge({ value }) {
  if (typeof value !== 'number' || value === 0) return null;
  const pos = value > 0;
  return (
    <span className={`inline-flex items-center gap-0.5 text-[10px] font-semibold ${
      pos ? 'text-emerald-600' : 'text-red-500'
    }`}>
      {pos ? <ArrowUp className="w-2.5 h-2.5" /> : <ArrowDown className="w-2.5 h-2.5" />}
      {Math.abs(value * 100).toFixed(1)}%
    </span>
  );
}

function val(v) {
  if (v && typeof v === 'object' && 'current' in v) return v.current;
  return v;
}

function delta(v) {
  if (v && typeof v === 'object' && 'delta' in v) return v.delta;
  return null;
}

/* ── Color helpers ───────────────────────────────────── */
function accColor(v) {
  if (v >= 0.5) return 'text-emerald-600';
  if (v >= 0.35) return 'text-amber-600';
  return 'text-red-500';
}
function catColor(v) {
  if (v <= 0.1) return 'text-emerald-600';
  if (v <= 0.2) return 'text-amber-600';
  return 'text-red-500';
}
function pnlColor(v) { return v >= 0 ? 'text-emerald-600' : 'text-red-500'; }

function driftBadge(level) {
  const c = { low: 'bg-emerald-100 text-emerald-700', medium: 'bg-amber-100 text-amber-700', high: 'bg-red-100 text-red-700' };
  return c[level] || 'bg-gray-100 text-gray-700';
}

function modeBadge(mode) {
  const c = { normal: 'bg-emerald-100 text-emerald-700', cautious: 'bg-amber-100 text-amber-700', defensive: 'bg-red-100 text-red-700' };
  return c[mode] || 'bg-gray-100 text-gray-700';
}

/* ══════════════════════════════════════════════════════
   MAIN COMPONENT
═══════════════════════════════════════════════════════ */
export default function IntelligenceConsolePage() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [range, setRange] = useState('all');
  const [error, setError] = useState(null);

  const fetchData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API}/api/admin/intelligence/console?range=${range}&asset=BTC`);
      const json = await res.json();
      if (json.ok) {
        setData(json.data);
      } else {
        setError(json.error || 'Ошибка загрузки');
      }
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, [range]);

  useEffect(() => { fetchData(); }, [fetchData]);

  return (
    <AdminLayout>
      <div className="px-4 py-5 lg:px-6 space-y-5" data-testid="intelligence-console">
        {/* ── Sticky Header ── */}
        <StickyHeader data={data} range={range} setRange={setRange} onRefresh={fetchData} loading={loading} />

        {loading && !data ? (
          <div className="flex items-center justify-center py-20">
            <Loader2 className="w-6 h-6 animate-spin text-gray-400" />
          </div>
        ) : error ? (
          <div className="text-red-500 text-sm py-10 text-center">{error}</div>
        ) : data ? (
          <div className="space-y-5">
            <Section1Health data={data.overview} />
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
              <Section2Phases data={data.phases} />
              <Section3Regimes data={data.regimes} />
            </div>
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
              <Section4Scenarios data={data.scenarios} />
              <Section5Drift data={data.drift} />
            </div>
            <Section6Tactical data={data.tactical} />
            <Section7MLDataset data={data.ml_dataset} />
          </div>
        ) : null}
      </div>
    </AdminLayout>
  );
}

/* ══════════════════════════════════════════════════════
   STICKY HEADER — KPI Bar
═══════════════════════════════════════════════════════ */
function StickyHeader({ data, range, setRange, onRefresh, loading }) {
  const ov = data?.overview;
  const stats = ov?.stats || {};
  const drift = data?.drift || {};

  return (
    <div className="sticky top-0 z-20 bg-white border-b border-gray-200 -mx-4 px-4 pb-3 pt-2" data-testid="intel-sticky-header">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <Radar className="w-5 h-5 text-gray-600" />
          <h1 className="text-lg font-bold text-gray-900">Intelligence Console</h1>
        </div>
        <div className="flex items-center gap-2">
          {RANGES.map(r => (
            <button
              key={r.key}
              onClick={() => setRange(r.key)}
              className={`px-3 py-1 rounded-lg text-xs font-medium transition-all ${
                range === r.key
                  ? 'bg-gray-900 text-white'
                  : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
              }`}
              data-testid={`range-${r.key}`}
            >
              {r.label}
            </button>
          ))}
          <button onClick={onRefresh} className="ml-2 p-1.5 rounded-lg hover:bg-gray-100 transition-all" data-testid="refresh-console">
            <RefreshCw className={`w-4 h-4 text-gray-500 ${loading ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </div>

      {/* KPI Bar */}
      <div className="grid grid-cols-5 gap-3">
        <KpiChip label="Accuracy" value={pct(val(stats.accuracy) || 0)} delta={delta(stats.accuracy)} colorFn={accColor} />
        <KpiChip label="PnL" value={`${(val(stats.pnl) || 0).toFixed(1)}%`} delta={delta(stats.pnl)} colorFn={pnlColor} />
        <KpiChip label="Catastrophic" value={pct(val(stats.catastrophic_rate) || 0)} delta={delta(stats.catastrophic_rate)} colorFn={v => catColor(v)} invert />
        <KpiChip label="Drift" value={drift.level || '—'} badge={driftBadge(drift.level)} />
        <KpiChip label="System Mode" value={ov?.system_mode || '—'} badge={modeBadge(ov?.system_mode)} />
      </div>
    </div>
  );
}

function KpiChip({ label, value, delta: d, colorFn, badge, invert }) {
  const displayVal = typeof value === 'string' ? value : '—';
  const numVal = parseFloat(displayVal) / 100;
  const color = colorFn ? colorFn(invert ? numVal : numVal) : 'text-gray-900';

  return (
    <div className="bg-gray-50 border border-gray-200 rounded-xl px-3 py-2">
      <p className="text-[10px] text-gray-500 uppercase tracking-wider">{label}</p>
      <div className="flex items-center gap-2 mt-0.5">
        {badge ? (
          <span className={`px-2 py-0.5 rounded text-xs font-bold capitalize ${badge}`}>{displayVal}</span>
        ) : (
          <span className={`text-lg font-bold ${color}`}>{displayVal}</span>
        )}
        {d != null && <DeltaBadge value={d} />}
      </div>
    </div>
  );
}

/* ══════════════════════════════════════════════════════
   SECTION 1 — Здоровье системы
═══════════════════════════════════════════════════════ */
function Section1Health({ data }) {
  if (!data) return null;
  const stats = data.stats || {};
  const unc = data.uncertainty || {};
  const exec = data.execution_modes || {};

  return (
    <div className="bg-white border border-gray-200 rounded-2xl p-5" data-testid="section-health">
      <SectionTitle icon={Activity} title="Здоровье системы" />
      <div className="grid grid-cols-1 md:grid-cols-3 gap-5 mt-4">
        {/* Main KPIs */}
        <div className="space-y-3">
          <StatRow label="Accuracy" value={pct(val(stats.accuracy) || 0)} delta={delta(stats.accuracy)} color={accColor(val(stats.accuracy) || 0)} />
          <StatRow label="PnL" value={`${(val(stats.pnl) || 0).toFixed(1)}%`} delta={delta(stats.pnl)} color={pnlColor(val(stats.pnl) || 0)} />
          <StatRow label="Catastrophic Rate" value={pct(val(stats.catastrophic_rate) || 0)} delta={delta(stats.catastrophic_rate)} color={catColor(val(stats.catastrophic_rate) || 0)} />
          <StatRow label="Средняя ошибка" value={`${stats.avg_error || 0}%`} color="text-gray-700" />
          <StatRow label="Всего прогнозов" value={stats.n || 0} color="text-gray-700" />
        </div>

        {/* Uncertainty Distribution */}
        <div>
          <p className="text-xs text-gray-500 font-medium mb-3">Распределение неопределённости</p>
          <BarDistribution items={[
            { label: 'Низкая', value: unc.low || 0, color: '#16a34a' },
            { label: 'Средняя', value: unc.mid || 0, color: '#d97706' },
            { label: 'Высокая', value: unc.high || 0, color: '#dc2626' },
          ]} />
        </div>

        {/* Execution Modes */}
        <div>
          <p className="text-xs text-gray-500 font-medium mb-3">Режимы исполнения</p>
          <BarDistribution items={[
            { label: 'Normal', value: exec.normal || 0, color: '#16a34a' },
            { label: 'Reduced', value: exec.reduced || 0, color: '#d97706' },
            { label: 'Minimal', value: exec.minimal || 0, color: '#dc2626' },
          ]} />
          <div className="mt-3 flex items-center gap-2">
            <span className="text-[10px] text-gray-500 uppercase">Режим системы</span>
            <span className={`px-2 py-0.5 rounded text-[10px] font-bold capitalize ${modeBadge(data.system_mode)}`}>
              {data.system_mode}
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}

/* ══════════════════════════════════════════════════════
   SECTION 2 — Производительность фаз
═══════════════════════════════════════════════════════ */
function Section2Phases({ data }) {
  if (!data?.phases) return null;
  const phases = data.phases;
  const rows = Object.entries(phases).sort((a, b) => (val(b[1].accuracy) || 0) - (val(a[1].accuracy) || 0));

  return (
    <div className="bg-white border border-gray-200 rounded-2xl p-5" data-testid="section-phases">
      <SectionTitle icon={Zap} title="Производительность фаз" />
      <div className="mt-3 overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-[10px] text-gray-500 uppercase tracking-wider border-b border-gray-100">
              <th className="text-left py-2 px-2">Фаза</th>
              <th className="text-right py-2 px-2">N</th>
              <th className="text-right py-2 px-2">Accuracy</th>
              <th className="text-right py-2 px-2">PnL</th>
              <th className="text-right py-2 px-2">Catastrophic</th>
            </tr>
          </thead>
          <tbody>
            {rows.map(([name, s], i) => {
              const isTop = i === 0 && rows.length > 1;
              const isBottom = i === rows.length - 1 && rows.length > 1;
              return (
                <tr key={name} className={`border-b border-gray-50 ${isTop ? 'bg-emerald-50/50' : isBottom ? 'bg-red-50/50' : ''}`}>
                  <td className="py-2 px-2 font-medium text-gray-800 capitalize">{name.replace(/_/g, ' ')}</td>
                  <td className="py-2 px-2 text-right text-gray-600">{s.n || 0}</td>
                  <td className="py-2 px-2 text-right">
                    <span className={accColor(val(s.accuracy) || 0)}>{pct(val(s.accuracy) || 0)}</span>
                    {delta(s.accuracy) != null && <DeltaBadge value={delta(s.accuracy)} />}
                  </td>
                  <td className={`py-2 px-2 text-right ${pnlColor(val(s.pnl) || 0)}`}>
                    {(val(s.pnl) || 0).toFixed(1)}%
                  </td>
                  <td className={`py-2 px-2 text-right ${catColor(val(s.catastrophic_rate) || 0)}`}>
                    {pct(val(s.catastrophic_rate) || 0)}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

/* ══════════════════════════════════════════════════════
   SECTION 3 — Производительность режимов
═══════════════════════════════════════════════════════ */
function Section3Regimes({ data }) {
  if (!data?.regimes) return null;
  const regimes = data.regimes;
  const rows = Object.entries(regimes).sort((a, b) => (val(b[1].accuracy) || 0) - (val(a[1].accuracy) || 0));

  return (
    <div className="bg-white border border-gray-200 rounded-2xl p-5" data-testid="section-regimes">
      <SectionTitle icon={BarChart3} title="Производительность режимов" />
      <div className="mt-3 overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-[10px] text-gray-500 uppercase tracking-wider border-b border-gray-100">
              <th className="text-left py-2 px-2">Режим</th>
              <th className="text-right py-2 px-2">N</th>
              <th className="text-right py-2 px-2">Accuracy</th>
              <th className="text-right py-2 px-2">Entropy</th>
              <th className="text-right py-2 px-2">Confidence</th>
            </tr>
          </thead>
          <tbody>
            {rows.map(([name, s], i) => {
              const isTop = i === 0 && rows.length > 1;
              const isBottom = i === rows.length - 1 && rows.length > 1;
              return (
                <tr key={name} className={`border-b border-gray-50 ${isTop ? 'bg-emerald-50/50' : isBottom ? 'bg-red-50/50' : ''}`}>
                  <td className="py-2 px-2 font-medium text-gray-800 capitalize">{name}</td>
                  <td className="py-2 px-2 text-right text-gray-600">{s.n || 0}</td>
                  <td className="py-2 px-2 text-right">
                    <span className={accColor(val(s.accuracy) || 0)}>{pct(val(s.accuracy) || 0)}</span>
                    {delta(s.accuracy) != null && <DeltaBadge value={delta(s.accuracy)} />}
                  </td>
                  <td className="py-2 px-2 text-right text-gray-600">{s.avg_entropy?.toFixed(3) || '—'}</td>
                  <td className="py-2 px-2 text-right text-gray-600">{s.avg_confidence?.toFixed(3) || '—'}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

/* ══════════════════════════════════════════════════════
   SECTION 4 — Сценарный движок
═══════════════════════════════════════════════════════ */
function Section4Scenarios({ data }) {
  if (!data?.scenarios) return null;
  const sc = data.scenarios;

  return (
    <div className="bg-white border border-gray-200 rounded-2xl p-5" data-testid="section-scenarios">
      <SectionTitle icon={Radar} title="Сценарный движок" />
      <div className="mt-4 space-y-4">
        {/* Coverage Bar */}
        <div>
          <div className="flex items-center justify-between mb-1">
            <span className="text-xs text-gray-500">Покрытие сценариями</span>
            <span className="text-sm font-bold text-gray-800">{pct(val(sc.coverage) || 0)}</span>
          </div>
          <div className="w-full h-2 bg-gray-100 rounded-full">
            <div className="h-full rounded-full bg-indigo-500 transition-all" style={{ width: `${(val(sc.coverage) || 0) * 100}%` }} />
          </div>
        </div>

        <div className="grid grid-cols-3 gap-3">
          <MiniStat label="Direction Accuracy" value={pct(val(sc.direction_accuracy) || 0)} color={accColor(val(sc.direction_accuracy) || 0)} delta={delta(sc.direction_accuracy)} />
          <MiniStat label="PnL" value={`${(val(sc.pnl) || 0).toFixed(1)}%`} color={pnlColor(val(sc.pnl) || 0)} delta={delta(sc.pnl)} />
          <MiniStat label="Catastrophic" value={pct(val(sc.catastrophic_rate) || 0)} color={catColor(val(sc.catastrophic_rate) || 0)} delta={delta(sc.catastrophic_rate)} />
        </div>

        <p className="text-[10px] text-gray-400">
          Всего прогнозов: {sc.n || 0} | Со сценариями: {sc.scenario_cases || 0}
        </p>
      </div>
    </div>
  );
}

/* ══════════════════════════════════════════════════════
   SECTION 5 — Drift Intelligence
═══════════════════════════════════════════════════════ */
function Section5Drift({ data }) {
  if (!data) return null;

  return (
    <div className="bg-white border border-gray-200 rounded-2xl p-5" data-testid="section-drift">
      <SectionTitle icon={Shield} title="Drift Intelligence" />
      <div className="mt-4">
        {/* Badge + Score */}
        <div className="flex items-center gap-3 mb-4">
          <span className={`px-3 py-1 rounded-lg text-sm font-bold capitalize ${driftBadge(data.level)}`}>
            {data.level || 'unknown'}
          </span>
          <span className="text-sm text-gray-600">Score: <strong>{(data.drift_score || 0).toFixed(3)}</strong></span>
          {data.has_drift && <span className="text-xs text-red-500 font-semibold">DRIFT DETECTED</span>}
        </div>

        {/* Top Issues */}
        {data.top_issues?.length > 0 && (
          <div className="space-y-2 mb-4">
            <p className="text-[10px] text-gray-500 uppercase tracking-wider">Проблемные зоны</p>
            {data.top_issues.map((issue, i) => (
              <div key={i} className="flex items-center justify-between bg-red-50 rounded-lg px-3 py-2">
                <div>
                  <span className="text-xs font-semibold text-gray-800 capitalize">{issue.zone}</span>
                  <span className="text-[10px] text-gray-500 ml-2">n={issue.cases}</span>
                </div>
                <div className="flex items-center gap-3">
                  <span className={`text-xs font-semibold ${accColor(issue.accuracy)}`}>acc: {pct(issue.accuracy)}</span>
                  <span className={`text-xs font-semibold ${catColor(issue.catastrophic_rate)}`}>cat: {pct(issue.catastrophic_rate)}</span>
                  <span className={`text-xs ${pnlColor(issue.pnl_impact)}`}>pnl: {issue.pnl_impact?.toFixed(1) || 0}%</span>
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Recommendations */}
        {data.recommendations?.length > 0 && (
          <div className="space-y-1">
            <p className="text-[10px] text-gray-500 uppercase tracking-wider">Рекомендации</p>
            {data.recommendations.map((r, i) => (
              <p key={i} className="text-xs text-gray-600">
                {r.priority && <span className={`font-bold mr-1 ${r.priority === 'high' ? 'text-red-500' : 'text-amber-500'}`}>[{r.priority}]</span>}
                {r.action || r.recommendation || JSON.stringify(r)}
              </p>
            ))}
          </div>
        )}

        {/* Global metrics */}
        {data.global_metrics && (
          <div className="mt-3 pt-3 border-t border-gray-100 grid grid-cols-4 gap-2">
            <MiniStat label="N" value={data.global_metrics.n || 0} color="text-gray-700" />
            <MiniStat label="Accuracy" value={pct(data.global_metrics.accuracy || 0)} color={accColor(data.global_metrics.accuracy || 0)} />
            <MiniStat label="PnL" value={`${(data.global_metrics.pnl || 0).toFixed(1)}`} color={pnlColor(data.global_metrics.pnl || 0)} />
            <MiniStat label="Avg Error" value={`${data.global_metrics.avg_error || 0}%`} color="text-gray-700" />
          </div>
        )}
      </div>
    </div>
  );
}

/* ══════════════════════════════════════════════════════
   SECTION 6 — Тактика + Execution Impact
═══════════════════════════════════════════════════════ */
function Section6Tactical({ data }) {
  if (!data) return null;
  const bias = data.bias_distribution || {};
  const advice = data.advice_distribution || {};

  return (
    <div className="bg-white border border-gray-200 rounded-2xl p-5" data-testid="section-tactical">
      <SectionTitle icon={Crosshair} title="Тактика + Execution Impact" />
      <div className="grid grid-cols-1 md:grid-cols-3 gap-5 mt-4">
        {/* Bias Distribution */}
        <div>
          <p className="text-xs text-gray-500 font-medium mb-3">Распределение Tactical Bias</p>
          <BarDistribution items={[
            { label: 'Bullish', value: bias.bullish || 0, color: '#16a34a' },
            { label: 'Neutral', value: bias.neutral || 0, color: '#6b7280' },
            { label: 'Bearish', value: bias.bearish || 0, color: '#dc2626' },
          ]} />
        </div>

        {/* Advice Distribution */}
        <div>
          <p className="text-xs text-gray-500 font-medium mb-3">Execution Advice</p>
          <BarDistribution items={[
            { label: 'Normal', value: advice.normal || 0, color: '#16a34a' },
            { label: 'Cautious', value: advice.avoid_aggressive || 0, color: '#f59e0b' },
            { label: 'Reduced', value: advice.reduced || 0, color: '#f97316' },
            { label: 'Wait', value: advice.wait || 0, color: '#dc2626' },
          ]} />
        </div>

        {/* Impact Stats */}
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-xs text-gray-500">Caution Ratio</span>
            <span className="text-sm font-bold text-gray-800">{data.caution_ratio || 0}</span>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-xs text-gray-500">Средняя сила сигнала</span>
            <span className="text-sm font-bold text-gray-800">{((data.avg_signal_strength || 0) * 100).toFixed(1)}%</span>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-xs text-gray-500">Наблюдений</span>
            <span className="text-sm font-bold text-gray-800">{(data.observations || 0).toLocaleString()}</span>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-xs text-gray-500">Аудитов</span>
            <span className="text-sm font-bold text-gray-800">{data.audits || 0}</span>
          </div>
          <div className="text-[10px] text-gray-400 mt-2 pt-2 border-t border-gray-100">
            Tactical слой влияет на размер позиции через Execution Impact. Reduction: ~{pct(data.impact?.avg_size_reduction || 0)}
          </div>
        </div>
      </div>
    </div>
  );
}

/* ══════════════════════════════════════════════════════
   SECTION 7 — ML Dataset Accumulation
═══════════════════════════════════════════════════════ */
function Section7MLDataset({ data }) {
  if (!data) return null;
  const r = data.readiness || {};
  const q = data.quality || {};

  return (
    <div className="bg-white border border-gray-200 rounded-2xl p-5" data-testid="section-ml-dataset">
      <SectionTitle icon={Radar} title="ML Dataset — Накопление данных" />
      <div className="grid grid-cols-1 md:grid-cols-3 gap-5 mt-4">
        {/* Progress */}
        <div>
          <p className="text-xs text-gray-500 font-medium mb-3">Прогресс накопления</p>
          <div className="flex items-center justify-between mb-1">
            <span className="text-xs text-gray-500">Готовых строк</span>
            <span className="text-sm font-bold text-gray-800">{data.usable_for_ml || 0} / {data.minimum_threshold || 100}</span>
          </div>
          <div className="w-full h-2 bg-gray-100 rounded-full">
            <div className={`h-full rounded-full transition-all ${data.progress_pct >= 100 ? 'bg-emerald-500' : 'bg-indigo-500'}`}
              style={{ width: `${Math.min(data.progress_pct || 0, 100)}%` }} />
          </div>
          <p className="text-[10px] text-gray-400 mt-1">{(data.progress_pct || 0).toFixed(0)}% • {r.eta || 'расчёт...'}</p>

          <div className="mt-4 space-y-2">
            <StatRow label="Всего evaluated" value={data.total_evaluated || 0} color="text-gray-700" />
            <StatRow label="v4+ модели" value={data.v4_total || 0} color="text-gray-700" />
            <StatRow label="С полным audit" value={data.with_full_audit || 0} color={data.with_full_audit > 0 ? 'text-emerald-600' : 'text-red-500'} />
            <StatRow label="Дней покрыто" value={data.days_covered || 0} color="text-gray-700" />
          </div>
        </div>

        {/* Readiness */}
        <div>
          <p className="text-xs text-gray-500 font-medium mb-3">Статус готовности</p>
          <span className={`px-3 py-1 rounded-lg text-sm font-bold ${
            r.ready ? 'bg-emerald-100 text-emerald-700' : 'bg-red-100 text-red-700'
          }`}>
            {r.status || 'UNKNOWN'}
          </span>

          {r.blockers?.length > 0 && (
            <div className="mt-3 space-y-2">
              <p className="text-[10px] text-gray-500 uppercase">Блокеры</p>
              {r.blockers.map((b, i) => (
                <div key={i} className="bg-red-50 rounded-lg px-3 py-2">
                  <span className="text-xs text-red-700">{b.message}</span>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Quality */}
        <div>
          <p className="text-xs text-gray-500 font-medium mb-3">Качество данных</p>
          {q.reason === 'no_usable_data' ? (
            <p className="text-xs text-gray-400">Нет данных для анализа качества</p>
          ) : (
            <div className="space-y-2">
              <StatRow label="Variance entropy" value={q.entropy_variance?.toFixed(4) || 0} color={q.entropy_variance > 0.01 ? 'text-emerald-600' : 'text-red-500'} />
              <StatRow label="Variance uncertainty" value={q.uncertainty_variance?.toFixed(4) || 0} color={q.uncertainty_variance > 0.01 ? 'text-emerald-600' : 'text-red-500'} />
              <StatRow label="Режимов" value={q.regime_diversity || 0} color={q.regime_diversity >= 3 ? 'text-emerald-600' : 'text-amber-600'} />
              <StatRow label="Направлений" value={q.direction_diversity || 0} color={q.direction_diversity >= 2 ? 'text-emerald-600' : 'text-amber-600'} />
              {q.issues?.length > 0 && (
                <div className="mt-2 pt-2 border-t border-gray-100">
                  {q.issues.map((issue, i) => (
                    <p key={i} className="text-[10px] text-red-500">{issue.replace(/_/g, ' ')}</p>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

/* ══════════════════════════════════════════════════════
   SHARED COMPONENTS
═══════════════════════════════════════════════════════ */
function SectionTitle({ icon: Icon, title }) {
  return (
    <div className="flex items-center gap-2">
      <Icon className="w-4 h-4 text-gray-500" />
      <h2 className="text-sm font-semibold text-gray-800">{title}</h2>
    </div>
  );
}

function StatRow({ label, value, delta: d, color }) {
  return (
    <div className="flex items-center justify-between">
      <span className="text-xs text-gray-500">{label}</span>
      <div className="flex items-center gap-2">
        <span className={`text-sm font-bold ${color || 'text-gray-800'}`}>{value}</span>
        {d != null && <DeltaBadge value={d} />}
      </div>
    </div>
  );
}

function MiniStat({ label, value, color, delta: d }) {
  return (
    <div>
      <p className="text-[10px] text-gray-500">{label}</p>
      <div className="flex items-center gap-1">
        <p className={`text-sm font-bold ${color || 'text-gray-800'}`}>{value}</p>
        {d != null && <DeltaBadge value={d} />}
      </div>
    </div>
  );
}

function BarDistribution({ items }) {
  const total = items.reduce((s, i) => s + (i.value || 0), 0);
  return (
    <div className="space-y-2">
      {items.map((item, i) => (
        <div key={i}>
          <div className="flex items-center justify-between mb-0.5">
            <span className="text-[11px] text-gray-600">{item.label}</span>
            <span className="text-[11px] font-semibold text-gray-700">{pct(item.value)}</span>
          </div>
          <div className="w-full h-1.5 bg-gray-100 rounded-full">
            <div
              className="h-full rounded-full transition-all duration-300"
              style={{ width: `${Math.max((item.value / Math.max(total, 0.01)) * 100, 1)}%`, background: item.color }}
            />
          </div>
        </div>
      ))}
    </div>
  );
}
