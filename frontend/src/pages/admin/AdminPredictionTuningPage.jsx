/**
 * Admin Prediction Tuning Page
 *
 * Self-Improvement Engine — admin console.
 * Sections: Overview | Drift | Patterns | Proposals | Experiments | Parameters
 * All labels in Russian. Wrapped in AdminLayout.
 */
import { useState, useEffect, useCallback } from 'react';
import { useSearchParams } from 'react-router-dom';
import AdminLayout from '../../components/admin/AdminLayout';
import { Button } from '../../components/ui/button';
import {
  RefreshCw, Settings2, Activity, AlertTriangle, CheckCircle2,
  XCircle, Loader2, Shield, Zap, TrendingUp, TrendingDown, Minus,
  FlaskConical, BarChart3, Award,
} from 'lucide-react';

const API_URL = process.env.REACT_APP_BACKEND_URL;

const pct = (v, dec = 1) => v != null ? `${(v * 100).toFixed(dec)}%` : '\u2014';
const num = (v, dec = 4) => v != null ? v.toFixed(dec) : '\u2014';
const fmtDate = (iso) => {
  if (!iso) return '\u2014';
  try {
    const d = new Date(iso);
    return d.toLocaleDateString('ru-RU', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' });
  } catch { return '\u2014'; }
};

const SEVERITY_STYLES = {
  HIGH: 'bg-red-50 text-red-700 border-red-200',
  MEDIUM: 'bg-amber-50 text-amber-700 border-amber-200',
  LOW: 'bg-gray-50 text-gray-500 border-gray-200',
};

const STATUS_STYLES = {
  DEGRADING: 'bg-red-50 text-red-700 border-red-200',
  UNSTABLE: 'bg-amber-50 text-amber-700 border-amber-200',
  STABLE: 'bg-gray-50 text-gray-600 border-gray-200',
  IMPROVING: 'bg-emerald-50 text-emerald-700 border-emerald-200',
};

const PROPOSAL_STYLES = {
  SUGGESTED: 'bg-blue-50 text-blue-700 border-blue-200',
  APPROVED: 'bg-indigo-50 text-indigo-700 border-indigo-200',
  EXPERIMENT: 'bg-purple-50 text-purple-700 border-purple-200',
  ACTIVE: 'bg-emerald-50 text-emerald-700 border-emerald-200',
  REJECTED: 'bg-red-50 text-red-600 border-red-200',
  REJECTED_BY_GOVERNANCE: 'bg-red-50 text-red-600 border-red-200',
  REVERTED: 'bg-gray-50 text-gray-500 border-gray-200',
};

const EXP_STYLES = {
  RUNNING: 'bg-blue-50 text-blue-700 border-blue-200',
  COMPLETED: 'bg-emerald-50 text-emerald-700 border-emerald-200',
  FAILED: 'bg-red-50 text-red-600 border-red-200',
};

const ISSUE_TYPE_RU = {
  OVERCONFIDENCE: 'Сверхуверенность',
  UNDERCONFIDENCE: 'Недостаточная уверенность',
  LATE_SIGNAL: 'Поздний сигнал',
  WEAK_STRUCTURE: 'Слабая структура',
  STRONG_STRUCTURE: 'Сильная структура',
  SHORT_EXPIRY_NOISE: 'Шум коротких экспираций',
};

const STATUS_RU = {
  DEGRADING: 'Деградация',
  UNSTABLE: 'Нестабильно',
  STABLE: 'Стабильно',
  IMPROVING: 'Улучшение',
};

const SEVERITY_RU = {
  HIGH: 'Высокая',
  MEDIUM: 'Средняя',
  LOW: 'Низкая',
};

const PROPOSAL_STATUS_RU = {
  SUGGESTED: 'Предложено',
  APPROVED: 'Одобрено',
  EXPERIMENT: 'Эксперимент',
  ACTIVE: 'Активно',
  REJECTED: 'Отклонено',
  REJECTED_BY_GOVERNANCE: 'Отклонено (governance)',
  REVERTED: 'Отменено',
};

const SECTIONS = [
  { id: 'overview', label: 'Обзор', icon: BarChart3 },
  { id: 'drift', label: 'Дрифт', icon: Activity },
  { id: 'patterns', label: 'Паттерны', icon: TrendingUp },
  { id: 'proposals', label: 'Предложения', icon: Zap },
  { id: 'experiments', label: 'Эксперименты', icon: FlaskConical },
  { id: 'params', label: 'Параметры', icon: Settings2 },
];

/* ─── Section Card (admin style) ─── */
const SectionCard = ({ icon: Icon, iconColor, title, extra, children, testId }) => (
  <div className="p-4 rounded-lg bg-gray-50/70" data-testid={testId}>
    <div className="flex items-center justify-between mb-3">
      <div className="flex items-center gap-2">
        {Icon && <Icon className={`w-4 h-4 ${iconColor || 'text-gray-600'}`} />}
        <span className="text-sm font-semibold text-slate-900">{title}</span>
      </div>
      {extra}
    </div>
    {children}
  </div>
);

export default function AdminPredictionTuningPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [scanning, setScanning] = useState(false);
  const [proposing, setProposing] = useState(false);

  const section = searchParams.get('section') || 'overview';
  const setSection = (id) => setSearchParams({ section: id }, { replace: true });

  const fetchData = useCallback(async () => {
    try {
      const res = await fetch(`${API_URL}/api/self-improvement/overview`);
      if (res.ok) {
        const d = await res.json();
        setData(d);
      }
    } catch (e) { console.error('Tuning fetch error:', e); }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { fetchData(); }, [fetchData]);

  const handleScan = async () => {
    setScanning(true);
    try {
      await fetch(`${API_URL}/api/self-improvement/scan`, { method: 'POST' });
      await fetchData();
    } catch (e) { console.error(e); }
    finally { setScanning(false); }
  };

  const handlePropose = async () => {
    setProposing(true);
    try {
      await fetch(`${API_URL}/api/self-improvement/propose`, { method: 'POST' });
      await fetchData();
    } catch (e) { console.error(e); }
    finally { setProposing(false); }
  };

  const handleApprove = async (proposalId) => {
    try {
      await fetch(`${API_URL}/api/self-improvement/approve`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ proposal_id: proposalId }),
      });
      await fetchData();
    } catch (e) { console.error(e); }
  };

  const handleReject = async (proposalId) => {
    try {
      await fetch(`${API_URL}/api/self-improvement/reject`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ proposal_id: proposalId, reason: 'Manual rejection' }),
      });
      await fetchData();
    } catch (e) { console.error(e); }
  };

  const handleSeedDefaults = async () => {
    try {
      await fetch(`${API_URL}/api/self-improvement/seed-defaults`, { method: 'POST' });
      await fetchData();
    } catch (e) { console.error(e); }
  };

  const [simulating, setSimulating] = useState(false);
  const [simResult, setSimResult] = useState(null);

  const handleFullCycle = async () => {
    setSimulating(true);
    setSimResult(null);
    try {
      const res = await fetch(`${API_URL}/api/self-improvement/simulate/full-cycle`, { method: 'POST' });
      if (res.ok) {
        const d = await res.json();
        setSimResult(d.cycle);
      }
      await fetchData();
    } catch (e) { console.error(e); }
    finally { setSimulating(false); }
  };

  const handleClearSynthetic = async () => {
    try {
      await fetch(`${API_URL}/api/self-improvement/simulate/clear`, { method: 'POST' });
      await fetchData();
    } catch (e) { console.error(e); }
  };

  if (loading) {
    return (
      <AdminLayout>
        <div className="space-y-6">
          <div className="flex items-center gap-3">
            <Settings2 className="w-5 h-5 text-violet-600" />
            <h1 className="text-xl font-semibold text-slate-900">Self-Improvement Engine</h1>
          </div>
          <div className="flex items-center justify-center h-32">
            <Loader2 className="w-8 h-8 text-violet-600 animate-spin" />
          </div>
        </div>
      </AdminLayout>
    );
  }

  const s = data?.summary || {};

  return (
    <AdminLayout>
      <div className="px-4 py-5 lg:px-6 space-y-6" data-testid="admin-prediction-tuning">
        {/* Header */}
        <div className="flex items-center justify-between flex-wrap gap-3">
          <div className="flex items-center gap-3">
            <Settings2 className="w-5 h-5 text-violet-600" />
            <div>
              <h1 className="text-xl font-semibold text-slate-900">Self-Improvement Engine</h1>
              <p className="text-xs text-gray-400">Обучение на паттернах, детекция дрифта, управляемый автотюнинг</p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={handleScan}
              disabled={scanning}
              data-testid="admin-scan-btn"
            >
              <Activity className={`w-3.5 h-3.5 mr-1.5 ${scanning ? 'animate-spin' : ''}`} />
              {scanning ? 'Сканирование...' : 'Запустить скан'}
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={handlePropose}
              disabled={proposing}
              data-testid="admin-propose-btn"
            >
              <Zap className={`w-3.5 h-3.5 mr-1.5 ${proposing ? 'animate-pulse' : ''}`} />
              {proposing ? 'Генерация...' : 'Генерировать предложения'}
            </Button>
            <Button
              variant="ghost"
              size="sm"
              onClick={fetchData}
              data-testid="admin-refresh-btn"
            >
              <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={handleFullCycle}
              disabled={simulating}
              data-testid="admin-simulate-btn"
              className="border-amber-200 text-amber-700 hover:bg-amber-50"
            >
              <FlaskConical className={`w-3.5 h-3.5 mr-1.5 ${simulating ? 'animate-spin' : ''}`} />
              {simulating ? 'Симуляция...' : 'Полный цикл'}
            </Button>
          </div>
        </div>

        {/* Section tabs — unified style */}
        <div className="flex gap-1 p-1 rounded-xl" style={{ backgroundColor: '#f8fafc' }} data-testid="admin-tuning-sections">
          {SECTIONS.map((sec) => {
            const Icon = sec.icon;
            const isActive = section === sec.id;
            return (
              <button
                key={sec.id}
                onClick={() => setSection(sec.id)}
                data-testid={`admin-section-${sec.id}`}
                className="flex items-center gap-2 px-4 py-2.5 rounded-lg text-sm font-medium transition-all"
                style={{
                  backgroundColor: isActive ? 'white' : 'transparent',
                  color: isActive ? '#6366f1' : '#475569',
                  boxShadow: isActive ? '0 1px 3px rgba(0,0,0,0.1)' : 'none',
                }}
              >
                <Icon size={16} />
                {sec.label}
              </button>
            );
          })}
        </div>

        {/* Simulation result banner */}
        {simResult && (
          <div className="p-3 rounded-lg bg-amber-50 border border-amber-200 flex items-center justify-between" data-testid="admin-sim-result">
            <div className="flex items-center gap-4 text-xs">
              <span className="font-semibold text-amber-800">Симуляция завершена:</span>
              <span>Записей: {simResult.synthetic_records}</span>
              <span>Паттернов: {simResult.patterns_found}</span>
              <span>Дрифт: {simResult.drift_states}</span>
              <span>Предложений: {simResult.proposals_suggested}</span>
            </div>
            <Button variant="ghost" size="sm" onClick={handleClearSynthetic} className="text-xs text-amber-600" data-testid="admin-clear-synthetic-btn">
              Очистить синтетику
            </Button>
          </div>
        )}

        {/* Section content */}
        {section === 'overview' && <OverviewSection summary={s} />}
        {section === 'drift' && <DriftSection states={data?.drift_states || []} />}
        {section === 'patterns' && <PatternsSection patterns={data?.patterns || []} />}
        {section === 'proposals' && <ProposalsSection proposals={data?.proposals || []} onApprove={handleApprove} onReject={handleReject} />}
        {section === 'experiments' && <ExperimentsSection experiments={data?.experiments || []} />}
        {section === 'params' && <ParamsSection params={data?.active_params || []} onSeedDefaults={handleSeedDefaults} />}
      </div>
    </AdminLayout>
  );
}

/* ─── Overview Section ─── */
function OverviewSection({ summary }) {
  const cards = [
    { label: 'Активные паттерны', value: summary.active_patterns || 0, icon: Activity, color: 'text-violet-600' },
    { label: 'Деградация метрик', value: summary.degrading_metrics || 0, icon: AlertTriangle, color: summary.degrading_metrics > 0 ? 'text-red-600' : 'text-gray-400' },
    { label: 'Ожидающие предложения', value: summary.pending_proposals || 0, icon: Zap, color: summary.pending_proposals > 0 ? 'text-blue-600' : 'text-gray-400' },
    { label: 'Активные эксперименты', value: summary.running_experiments || 0, icon: FlaskConical, color: summary.running_experiments > 0 ? 'text-purple-600' : 'text-gray-400' },
    { label: 'Настраиваемые параметры', value: summary.tunable_params_count || 0, icon: Settings2, color: 'text-gray-600' },
    { label: 'Активных (настроено)', value: summary.active_params_count || 0, icon: CheckCircle2, color: 'text-emerald-600' },
  ];

  return (
    <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3" data-testid="admin-tuning-overview">
      {cards.map((c) => {
        const Icon = c.icon;
        return (
          <SectionCard
            key={c.label}
            icon={Icon}
            iconColor={c.color}
            title={c.label}
            testId={`admin-kpi-${c.label}`}
          >
            <div className="text-2xl font-bold text-slate-900 -mt-1">{c.value}</div>
          </SectionCard>
        );
      })}
    </div>
  );
}

/* ─── Drift Section ─── */
function DriftSection({ states }) {
  if (!states.length) {
    return <EmptyState icon={Activity} text="Данных о дрифте пока нет. Запустите скан для обнаружения дрифта метрик." />;
  }

  const grouped = {};
  for (const s of states) {
    const scope = `${s.scope_type}: ${s.scope_value}`;
    if (!grouped[scope]) grouped[scope] = [];
    grouped[scope].push(s);
  }

  return (
    <div className="space-y-4" data-testid="admin-drift-section">
      {Object.entries(grouped).map(([scope, items]) => (
        <SectionCard
          key={scope}
          icon={Activity}
          iconColor="text-blue-600"
          title={scope}
          testId={`admin-drift-scope-${scope}`}
        >
          <div className="divide-y divide-gray-200/60">
            {items.map((d) => (
              <div key={d.drift_key} className="py-2.5 flex items-center justify-between gap-4" data-testid={`admin-drift-row-${d.drift_key}`}>
                <div className="flex items-center gap-3 min-w-0">
                  {d.delta > 0 ? <TrendingUp className="w-4 h-4 text-emerald-500 flex-shrink-0" /> :
                   d.delta < -0.02 ? <TrendingDown className="w-4 h-4 text-red-500 flex-shrink-0" /> :
                   <Minus className="w-4 h-4 text-gray-400 flex-shrink-0" />}
                  <div>
                    <div className="text-sm font-medium text-slate-800">{d.metric}</div>
                    <div className="text-xs text-gray-400">
                      Базовое: {num(d.baseline_value)} | EWMA: {num(d.ewma_current)} | Дельта: {num(d.delta)}
                    </div>
                  </div>
                </div>
                <div className="flex items-center gap-2 flex-shrink-0">
                  <span className={`text-xs px-2 py-0.5 rounded-full border font-medium ${STATUS_STYLES[d.status] || STATUS_STYLES.STABLE}`}>
                    {STATUS_RU[d.status] || d.status}
                  </span>
                  <span className={`text-xs px-2 py-0.5 rounded-full border font-medium ${SEVERITY_STYLES[d.severity] || SEVERITY_STYLES.LOW}`}>
                    {SEVERITY_RU[d.severity] || d.severity}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </SectionCard>
      ))}
    </div>
  );
}

/* ─── Patterns Section ─── */
function PatternsSection({ patterns }) {
  if (!patterns.length) {
    return <EmptyState icon={FlaskConical} text="Активных паттернов не обнаружено. Системе необходимо 30+ разрешённых прогнозов для начала обучения." />;
  }

  return (
    <div className="space-y-3" data-testid="admin-patterns-section">
      {patterns.map((p, i) => (
        <SectionCard
          key={p.pattern_key || i}
          icon={Activity}
          iconColor={p.effect_direction === 'POSITIVE' ? 'text-emerald-600' : 'text-red-600'}
          title={ISSUE_TYPE_RU[p.issue_type] || p.issue_type}
          extra={
            <div className="flex items-center gap-2">
              <span className={`text-xs font-semibold ${p.effect_direction === 'POSITIVE' ? 'text-emerald-600' : 'text-red-600'}`}>
                {p.effect_direction === 'POSITIVE' ? '+' : '-'}{pct(p.effect_size, 1)}
              </span>
              <span className="text-xs text-gray-400">n={p.sample_size}</span>
            </div>
          }
          testId={`admin-pattern-${p.pattern_key}`}
        >
          <p className="text-sm text-gray-600">{p.summary}</p>
          <div className="mt-1.5 flex items-center gap-3 text-xs text-gray-400">
            <span>Семейство: {p.family_key}</span>
            <span>Уверенность: {pct(p.confidence, 0)}</span>
            <span>Обнаружено: {fmtDate(p.detected_at)}</span>
          </div>
        </SectionCard>
      ))}
    </div>
  );
}

/* ─── Proposals Section ─── */
function ProposalsSection({ proposals, onApprove, onReject }) {
  if (!proposals.length) {
    return <EmptyState icon={Zap} text="Предложений по тюнингу нет. Сгенерируйте предложения на основе обнаруженных паттернов." />;
  }

  return (
    <div className="space-y-3" data-testid="admin-proposals-section">
      {proposals.map((p, i) => (
        <SectionCard
          key={p.proposal_id || i}
          icon={Zap}
          iconColor="text-blue-600"
          title={p.param_key}
          extra={
            <div className="flex items-center gap-2">
              <span className={`text-xs px-2 py-0.5 rounded-full border font-medium ${PROPOSAL_STYLES[p.status] || PROPOSAL_STYLES.SUGGESTED}`}>
                {PROPOSAL_STATUS_RU[p.status] || p.status}
              </span>
              {p.status === 'SUGGESTED' && (
                <div className="flex items-center gap-1.5">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => onApprove(p.proposal_id)}
                    data-testid={`admin-approve-${p.proposal_id}`}
                    className="h-7 text-xs text-emerald-700 border-emerald-200 hover:bg-emerald-50"
                  >
                    <CheckCircle2 className="w-3 h-3 mr-1" /> Одобрить
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => onReject(p.proposal_id)}
                    data-testid={`admin-reject-${p.proposal_id}`}
                    className="h-7 text-xs text-red-600 border-red-200 hover:bg-red-50"
                  >
                    <XCircle className="w-3 h-3 mr-1" /> Отклонить
                  </Button>
                </div>
              )}
            </div>
          }
          testId={`admin-proposal-${p.proposal_id}`}
        >
          <div className="grid grid-cols-3 gap-3 text-xs mb-2">
            <div>
              <span className="text-gray-400">Текущее:</span>{' '}
              <span className="font-mono font-semibold text-slate-700">{num(p.current_value)}</span>
            </div>
            <div>
              <span className="text-gray-400">Предложено:</span>{' '}
              <span className="font-mono font-semibold text-blue-700">{num(p.proposed_value)}</span>
            </div>
            <div>
              <span className="text-gray-400">Дельта:</span>{' '}
              <span className={`font-mono font-semibold ${p.delta >= 0 ? 'text-emerald-600' : 'text-red-600'}`}>
                {p.delta >= 0 ? '+' : ''}{num(p.delta)}
              </span>
            </div>
          </div>
          <p className="text-xs text-gray-500">{p.reason}</p>
          {p.governance_check && (
            <div className="mt-1.5 flex items-center gap-1.5 text-xs">
              {p.governance_check.approved ? (
                <><Shield className="w-3 h-3 text-emerald-500" /><span className="text-emerald-600">Governance: Пройдено</span></>
              ) : (
                <><AlertTriangle className="w-3 h-3 text-red-500" /><span className="text-red-600">Governance: {p.governance_check.reason}</span></>
              )}
            </div>
          )}
          <div className="mt-1 text-xs text-gray-400">Создано: {fmtDate(p.created_at)}</div>
        </SectionCard>
      ))}
    </div>
  );
}

/* ─── Experiments Section ─── */
function ExperimentsSection({ experiments }) {
  if (!experiments.length) {
    return <EmptyState icon={FlaskConical} text="Экспериментов пока нет. Одобрите предложение для запуска A/B эксперимента." />;
  }

  return (
    <div className="space-y-3" data-testid="admin-experiments-section">
      {experiments.map((e, i) => (
        <SectionCard
          key={e.experiment_id || i}
          icon={FlaskConical}
          iconColor="text-purple-600"
          title={e.param_key}
          extra={
            <div className="flex items-center gap-2">
              <span className={`text-xs px-2 py-0.5 rounded-full border font-medium ${EXP_STYLES[e.status] || EXP_STYLES.RUNNING}`}>
                {e.status}
              </span>
              {e.winner && (
                <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${
                  e.winner === 'TREATMENT' ? 'bg-emerald-50 text-emerald-700' : 'bg-gray-100 text-gray-600'
                }`}>
                  Победитель: {e.winner === 'TREATMENT' ? 'Лечение' : 'Контроль'}
                </span>
              )}
              <span className="text-xs text-gray-400">
                {e.split?.control * 100}/{e.split?.treatment * 100}
              </span>
            </div>
          }
          testId={`admin-experiment-${e.experiment_id}`}
        >
          <div className="grid grid-cols-2 gap-4">
            <MetricCard
              title="Контроль"
              value={e.control_value}
              accuracy={e.control_metrics?.accuracy}
              brier={e.control_metrics?.brier}
              samples={e.control_metrics?.sample_size}
              highlight={e.winner === 'CONTROL'}
            />
            <MetricCard
              title="Лечение (Treatment)"
              value={e.treatment_value}
              accuracy={e.treatment_metrics?.accuracy}
              brier={e.treatment_metrics?.brier}
              samples={e.treatment_metrics?.sample_size}
              highlight={e.winner === 'TREATMENT'}
            />
          </div>
          <div className="mt-2 text-xs text-gray-400">
            Начало: {fmtDate(e.started_at)}
            {e.ended_at && <> | Завершение: {fmtDate(e.ended_at)}</>}
          </div>
        </SectionCard>
      ))}
    </div>
  );
}

function MetricCard({ title, value, accuracy, brier, samples, highlight }) {
  return (
    <div className={`rounded-lg border p-3 ${highlight ? 'border-emerald-300 bg-emerald-50/50' : 'border-gray-200 bg-white'}`}>
      <div className="text-xs font-semibold text-gray-600 mb-1">{title}</div>
      <div className="text-sm font-mono font-bold text-slate-800">{num(value)}</div>
      <div className="mt-1 grid grid-cols-3 gap-2 text-xs text-gray-500">
        <div>Точн: {accuracy != null ? pct(accuracy, 1) : '\u2014'}</div>
        <div>Brier: {brier != null ? num(brier, 3) : '\u2014'}</div>
        <div>n={samples || 0}</div>
      </div>
    </div>
  );
}

/* ─── Params Section ─── */
function ParamsSection({ params, onSeedDefaults }) {
  return (
    <div className="space-y-4" data-testid="admin-params-section">
      {!params.length && (
        <div className="flex flex-col items-center justify-center py-12 text-gray-400">
          <Settings2 className="w-8 h-8 mb-3 opacity-40" />
          <p className="text-sm mb-3">Активных параметров нет. Инициализируйте значения по умолчанию.</p>
          <Button
            onClick={onSeedDefaults}
            data-testid="admin-seed-defaults-btn"
            className="bg-violet-600 hover:bg-violet-700"
          >
            <Zap className="w-4 h-4 mr-1.5" /> Инициализировать параметры
          </Button>
        </div>
      )}

      {params.length > 0 && (
        <SectionCard
          icon={Settings2}
          iconColor="text-gray-600"
          title="Активные параметры модели"
          extra={<span className="text-xs text-gray-400">{params.length} параметров</span>}
          testId="admin-params-table"
        >
          <div className="divide-y divide-gray-200/60">
            {params.map((p) => (
              <div key={p.param_key} className="py-2.5 flex items-center justify-between gap-4" data-testid={`admin-param-${p.param_key}`}>
                <span className="text-sm font-mono text-slate-700">{p.param_key}</span>
                <div className="flex items-center gap-3 flex-shrink-0">
                  <span className="text-sm font-mono font-bold text-slate-900">{num(p.value)}</span>
                  <span className={`text-xs px-2 py-0.5 rounded-full border font-medium ${
                    p.source === 'tuned' ? 'bg-emerald-50 text-emerald-700 border-emerald-200' : 'bg-gray-50 text-gray-500 border-gray-200'
                  }`}>
                    {p.source === 'tuned' ? 'Настроено' : 'По умолчанию'}
                  </span>
                  <span className="text-xs text-gray-400">{fmtDate(p.updated_at)}</span>
                </div>
              </div>
            ))}
          </div>
        </SectionCard>
      )}
    </div>
  );
}

/* ─── Shared Empty State ─── */
function EmptyState({ icon: Icon, text }) {
  return (
    <div className="flex flex-col items-center justify-center py-16 text-gray-400">
      <Icon className="w-8 h-8 mb-3 opacity-40" />
      <p className="text-sm text-center max-w-md">{text}</p>
    </div>
  );
}
