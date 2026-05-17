import React, { useState, useEffect, useCallback } from 'react';
import AdminLayout from '../../components/admin/AdminLayout';
import {
  FlaskConical, RefreshCw, AlertCircle, Database,
  GitCompare, Gauge, PieChart, ArrowUp, ArrowDown, Minus,
  CheckCircle, XCircle, AlertTriangle, ArrowRight,
} from 'lucide-react';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../../components/ui/tabs';
import { api } from '../../api/client';
import { Link } from 'react-router-dom';

const TABS = [
  { id: 'datasets', label: 'Датасеты', icon: Database },
  { id: 'ablation', label: 'Ablation', icon: GitCompare },
  { id: 'stability', label: 'Стабильность', icon: Gauge },
  { id: 'attribution', label: 'Attribution', icon: PieChart },
];

export default function AdminResearchPage() {
  const [tab, setTab] = useState('datasets');
  const [data, setData] = useState({ datasets: [], ablation: [], stability: [], attribution: [] });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const loadAll = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [datasetsRes, ablationRes, stabilityRes, attrRes] = await Promise.allSettled([
        api.get('/api/admin/ml/v3/dataset/list'),
        api.get('/api/admin/ml/v3/ablation/history'),
        api.get('/api/admin/ml/v3/stability/history?network=ethereum'),
        api.get('/api/admin/ml/v3/attribution/history?network=ethereum'),
      ]);
      setData({
        datasets: datasetsRes.status === 'fulfilled' ? datasetsRes.value.data?.data?.datasets || [] : [],
        ablation: ablationRes.status === 'fulfilled' ? ablationRes.value.data?.data?.rows || [] : [],
        stability: stabilityRes.status === 'fulfilled' ? stabilityRes.value.data?.data?.results || [] : [],
        attribution: attrRes.status === 'fulfilled' ? attrRes.value.data?.data?.results || [] : [],
      });
    } catch {
      setError('Не удалось загрузить данные исследований');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadAll(); }, [loadAll]);

  const totalDatasets = data.datasets.length;
  const totalExperiments = data.ablation.length + data.stability.length + data.attribution.length;

  return (
    <AdminLayout>
      <div className="px-4 py-5 lg:px-6 space-y-6">
        {/* Header — MetaBrain style */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <FlaskConical className="w-5 h-5 text-purple-600" />
            <div>
              <h1 className="text-xl font-semibold text-slate-900">Исследования</h1>
              <p className="text-xs text-gray-500">Экспериментальные ML инструменты. Не используются в production</p>
            </div>
          </div>
          <button
            onClick={loadAll}
            disabled={loading}
            className="flex items-center gap-2 px-3 py-1.5 text-sm text-gray-600 hover:bg-gray-100 rounded-lg transition-colors"
            data-testid="research-refresh"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
            Обновить
          </button>
        </div>

        {/* Error */}
        {error && (
          <div className="flex items-center gap-3 p-4 bg-amber-50 rounded-lg">
            <AlertCircle className="w-5 h-5 text-amber-600" />
            <span className="text-sm text-amber-800">{error}</span>
          </div>
        )}

        {/* Tabs — identical to MetaBrain */}
        <Tabs value={tab} onValueChange={setTab}>
          <TabsList className="bg-gray-100 flex-wrap h-auto gap-1 p-1" data-testid="research-tabs">
            {TABS.map(t => (
              <TabsTrigger key={t.id} value={t.id}
                className="data-[state=active]:bg-white data-[state=active]:shadow-sm text-xs gap-1.5"
                data-testid={`research-tab-${t.id}`}>
                <t.icon className="w-3.5 h-3.5" /> {t.label}
              </TabsTrigger>
            ))}
          </TabsList>

          {/* Tab content */}
          {loading ? (
            <div className="flex items-center justify-center py-16">
              <RefreshCw className="w-6 h-6 text-gray-400 animate-spin" />
            </div>
          ) : (
            <>
              <TabsContent value="datasets"><DatasetsTab datasets={data.datasets} /></TabsContent>
              <TabsContent value="ablation"><AblationTab reports={data.ablation} /></TabsContent>
              <TabsContent value="stability"><StabilityTab reports={data.stability} /></TabsContent>
              <TabsContent value="attribution"><AttributionTab reports={data.attribution} /></TabsContent>
            </>
          )}
        </Tabs>
      </div>
    </AdminLayout>
  );
}

/* ── Status card ─────────────────────────────── */

function StatusCard({ label, value, isText, active }) {
  return (
    <div className="bg-gray-50/70 rounded-lg p-4">
      <div className="text-xs text-gray-500 mb-1">{label}</div>
      {isText ? (
        <div className={`text-sm font-semibold ${active ? 'text-emerald-600' : 'text-gray-400'}`}>
          {value}
        </div>
      ) : (
        <div className="text-2xl font-bold text-gray-900">{value}</div>
      )}
    </div>
  );
}

/* ── Empty state ─────────────────────────────── */

function EmptyState({ icon: Icon, title, description }) {
  return (
    <div className="text-center py-16" data-testid="research-empty">
      <Icon className="w-10 h-10 mx-auto mb-4 text-gray-300" />
      <p className="text-sm font-medium text-gray-600 mb-1">{title}</p>
      <p className="text-sm text-gray-400 mb-4">{description}</p>
      <Link
        to="/admin/auto-retrain"
        className="inline-flex items-center gap-1.5 text-sm text-purple-600 hover:text-purple-700 font-medium"
      >
        Retrain Policies <ArrowRight className="w-3.5 h-3.5" />
      </Link>
    </div>
  );
}

/* ── Datasets tab ────────────────────────────── */

function DatasetsTab({ datasets }) {
  if (!datasets.length) {
    return <EmptyState icon={Database} title="Dataset pipeline неактивен" description="Датасеты не были сгенерированы. Включите Auto-Retrain для начала сбора данных." />;
  }
  return (
    <div className="bg-gray-50/70 rounded-lg overflow-hidden">
      <table className="w-full text-sm">
        <thead className="bg-gray-50 border-b border-gray-100">
          <tr>
            <th className="px-4 py-3 text-left text-xs font-medium text-gray-500">ID</th>
            <th className="px-4 py-3 text-left text-xs font-medium text-gray-500">Сеть</th>
            <th className="px-4 py-3 text-left text-xs font-medium text-gray-500">Задача</th>
            <th className="px-4 py-3 text-right text-xs font-medium text-gray-500">Строки</th>
            <th className="px-4 py-3 text-right text-xs font-medium text-gray-500">Создан</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-50">
          {datasets.map(ds => (
            <tr key={ds._id} className="hover:bg-gray-50">
              <td className="px-4 py-3 text-xs text-gray-400">{ds._id?.slice(-8)}</td>
              <td className="px-4 py-3 capitalize">{ds.network || '-'}</td>
              <td className="px-4 py-3">{ds.task || '-'}</td>
              <td className="px-4 py-3 text-right">{ds.rowCount?.toLocaleString() || '-'}</td>
              <td className="px-4 py-3 text-right text-gray-400">{ds.createdAt ? new Date(ds.createdAt).toLocaleDateString() : '-'}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/* ── Ablation tab ────────────────────────────── */

function AblationTab({ reports }) {
  if (!reports.length) {
    return <EmptyState icon={GitCompare} title="Эксперименты не проводились" description="Ablation тесты сравнивают варианты моделей. Требуются обученные модели." />;
  }
  return (
    <div className="space-y-4">
      {reports.map(r => (
        <div key={r._id} className="bg-gray-50/70 rounded-lg p-4">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-3 text-sm">
              <span className="text-xs font-bold text-blue-600">{r.modelA?.featurePack || 'A'}</span>
              <span className="text-gray-300">vs</span>
              <span className="text-xs font-bold text-purple-600">{r.modelB?.featurePack || 'B'}</span>
            </div>
            <VerdictBadge verdict={r.verdict} />
          </div>
          <div className="grid grid-cols-3 gap-3">
            <DeltaCell label="F1" value={r.deltas?.deltaF1} />
            <DeltaCell label="Accuracy" value={r.deltas?.deltaAccuracy} />
            <DeltaCell label="Recall" value={r.deltas?.deltaRecall} />
          </div>
        </div>
      ))}
    </div>
  );
}

/* ── Stability tab ───────────────────────────── */

function StabilityTab({ reports }) {
  if (!reports.length) {
    return <EmptyState icon={Gauge} title="Требуются обученные модели" description="Анализ стабильности запускается после обучения модели с несколькими seeds." />;
  }
  return (
    <div className="space-y-4">
      {reports.map(r => {
        const verdict = r.verdict || 'INSUFFICIENT_DATA';
        const cfg = verdict === 'STABLE'
          ? { icon: CheckCircle, color: 'text-emerald-600', bg: 'bg-emerald-50' }
          : verdict === 'UNSTABLE'
            ? { icon: XCircle, color: 'text-red-600', bg: 'bg-red-50' }
            : { icon: AlertTriangle, color: 'text-amber-600', bg: 'bg-amber-50' };
        const VIcon = cfg.icon;
        return (
          <div key={r._id} className="bg-gray-50/70 rounded-lg p-4">
            <div className="flex items-center justify-between mb-3">
              <span className="text-sm capitalize text-gray-600">{r.network || 'ethereum'}</span>
              <div className={`flex items-center gap-1.5`}>
                <VIcon className={`w-3.5 h-3.5 ${cfg.color}`} />
                <span className={`text-xs font-medium ${cfg.color}`}>{verdict}</span>
              </div>
            </div>
            <div className="grid grid-cols-4 gap-3">
              <MetricCell label="F1 std" value={r.stats?.stdF1?.toFixed(4)} />
              <MetricCell label="Acc std" value={r.stats?.stdAccuracy?.toFixed(4)} />
              <MetricCell label="CV" value={r.stats?.cv?.toFixed(4)} />
              <MetricCell label="Seeds" value={r.seeds?.length || r.stats?.seedCount} />
            </div>
          </div>
        );
      })}
    </div>
  );
}

/* ── Attribution tab ─────────────────────────── */

const GROUP_LABELS = {
  cex: 'CEX Flows', CEX: 'CEX Flows',
  zones: 'Accumulation Zones', ZONES: 'Accumulation Zones',
  corridors: 'Corridors', CORRIDORS: 'Corridors',
  dex: 'DEX Liquidity', DEX: 'DEX Liquidity',
  actors: 'Smart Actors', ACTORS: 'Smart Actors',
  events: 'Events', EVENTS: 'Events',
};

function AttributionTab({ reports }) {
  if (!reports.length) {
    return <EmptyState icon={PieChart} title="Требуются обученные модели" description="Анализ влияния групп признаков запускается после ablation тестов." />;
  }
  return (
    <div className="space-y-6">
      {reports.map(r => {
        const groups = Array.isArray(r.groups)
          ? r.groups
          : Object.entries(r.groups || {}).map(([k, v]) => ({ group: k, ...v }));
        const maxImpact = Math.max(...groups.map(g => Math.abs(g.deltaF1 || g.avgDeltaF1 || g.impact || 0)), 0.01);
        return (
          <div key={r._id} className="bg-gray-50/70 rounded-lg p-4">
            <div className="flex items-center justify-between mb-4">
              <span className="text-sm capitalize text-gray-600">{r.network || 'ethereum'}</span>
              <span className="text-xs text-gray-400">{groups.length} groups</span>
            </div>
            <div className="space-y-3">
              {groups.map((g, i) => {
                const name = g.group || `Group ${i}`;
                const impact = g.deltaF1 || g.avgDeltaF1 || g.impact || 0;
                const w = Math.abs(impact) / maxImpact * 100;
                return (
                  <div key={name}>
                    <div className="flex items-center justify-between text-sm mb-1">
                      <span className="text-gray-600">{GROUP_LABELS[name] || name}</span>
                      <span className={`font-medium ${impact >= 0 ? 'text-emerald-600' : 'text-red-600'}`}>
                        {impact >= 0 ? '+' : ''}{(impact * 100).toFixed(2)}%
                      </span>
                    </div>
                    <div className="h-1.5 bg-gray-100 rounded-full overflow-hidden">
                      <div
                        className={`h-full rounded-full ${impact >= 0 ? 'bg-emerald-500' : 'bg-red-400'}`}
                        style={{ width: `${Math.max(w, 2)}%` }}
                      />
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        );
      })}
    </div>
  );
}

/* ── Shared small components ─────────────────── */

function Row({ label, value }) {
  return (
    <div className="flex justify-between">
      <span className="text-gray-400">{label}</span>
      <span className="font-medium text-gray-700">{value}</span>
    </div>
  );
}

function MetricCell({ label, value }) {
  return (
    <div className="text-center p-2 bg-gray-50 rounded">
      <div className="font-medium text-sm text-gray-800">{value ?? '-'}</div>
      <div className="text-[11px] text-gray-400 mt-0.5">{label}</div>
    </div>
  );
}

function DeltaCell({ label, value }) {
  const Icon = !value || value === 0 ? Minus : value > 0 ? ArrowUp : ArrowDown;
  const color = !value || value === 0 ? 'text-gray-400' : value > 0 ? 'text-emerald-600' : 'text-red-600';
  return (
    <div className="text-center p-2 bg-gray-50 rounded">
      <div className="flex items-center justify-center gap-1">
        <Icon className={`w-3 h-3 ${color}`} />
        <span className={`font-medium text-sm ${color}`}>{value ? `${(value * 100).toFixed(2)}%` : '0%'}</span>
      </div>
      <div className="text-[11px] text-gray-400 mt-0.5">{label}</div>
    </div>
  );
}

function VerdictBadge({ verdict }) {
  const v = verdict || 'INCONCLUSIVE';
  const cls = v === 'IMPROVES' ? 'text-emerald-600'
    : v === 'DEGRADES' ? 'text-red-600'
    : v === 'NEUTRAL' ? 'text-gray-500'
    : 'text-amber-600';
  return <span className={`text-xs font-bold uppercase ${cls}`}>{v}</span>;
}
