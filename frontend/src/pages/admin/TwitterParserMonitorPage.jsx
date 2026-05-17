/**
 * Twitter Parser — Мониторинг
 * Общее здоровье системы парсинга и ёмкость
 */

import { useState, useEffect, useCallback } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import AdminLayout from '../../components/admin/AdminLayout';
import {
  getParserMonitor,
  getEgressSlots,
  runFreezeValidation,
  getFreezeStatus,
  getFreezeLast,
  abortFreezeValidation,
} from '../../api/twitterParserAdmin.api';
import { Button } from '../../components/ui/button';
import {
  RefreshCw,
  Activity,
  Server,
  Users,
  Gauge,
  AlertTriangle,
  CheckCircle,
  XCircle,
  Zap,
  Globe,
  Play,
  Square,
  FlaskConical,
  Loader2,
} from 'lucide-react';

const HEALTH_CFG = {
  UNKNOWN:  { label: 'Неизвестно', cls: 'text-slate-400' },
  HEALTHY:  { label: 'Здорова',    cls: 'text-emerald-700' },
  DEGRADED: { label: 'Деградация', cls: 'text-amber-700' },
  ERROR:    { label: 'Ошибка',     cls: 'text-red-500' },
};

/* ── Slot card (compact, no borders) ── */
function SlotCard({ slot }) {
  const health = HEALTH_CFG[slot.health?.status] || HEALTH_CFG.UNKNOWN;
  const usage = slot.usage?.usedInWindow || 0;
  const limit = slot.limits?.requestsPerHour || 200;
  const percent = Math.round((usage / limit) * 100);
  const barCls = percent > 90 ? 'bg-red-500' : percent > 70 ? 'bg-amber-500' : 'bg-emerald-500';

  return (
    <div className="p-4 rounded-lg bg-slate-50" data-testid={`slot-card-${slot.label}`}>
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          {slot.type === 'REMOTE_WORKER' ? <Server className="w-4 h-4 text-slate-500" /> :
           slot.type === 'PROXY' ? <Globe className="w-4 h-4 text-slate-500" /> :
           <Zap className="w-4 h-4 text-slate-500" />}
          <span className="text-sm font-medium text-slate-800">{slot.label}</span>
        </div>
        <span className={`text-xs font-medium ${health.cls}`}>{health.label}</span>
      </div>
      <div className="grid grid-cols-2 gap-4 text-sm mb-3">
        <div>
          <p className="text-xs text-slate-400">Тип</p>
          <p className="text-sm font-semibold text-slate-800">{slot.type}</p>
        </div>
        <div>
          <p className="text-xs text-slate-400">Нагрузка</p>
          <p className="text-sm font-semibold text-slate-800">{usage} / {limit}</p>
        </div>
      </div>
      <div className="h-1.5 bg-slate-200/60 rounded-full overflow-hidden">
        <div className={`h-full rounded-full transition-all ${barCls}`} style={{ width: `${percent}%` }} />
      </div>
      <p className="text-xs text-slate-400 text-right mt-1">{percent}%</p>
    </div>
  );
}

export default function TwitterParserMonitorPage() {
  const navigate = useNavigate();

  const [monitor, setMonitor] = useState(null);
  const [slots, setSlots] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [lastUpdate, setLastUpdate] = useState(null);

  const [freezeStatus, setFreezeStatus] = useState(null);
  const [freezeResult, setFreezeResult] = useState(null);
  const [freezeLoading, setFreezeLoading] = useState(false);

  const fetchData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [monitorRes, slotsRes] = await Promise.all([
        getParserMonitor(),
        getEgressSlots(),
      ]);
      if (monitorRes.ok) setMonitor(monitorRes.data);
      if (slotsRes.ok) setSlots(slotsRes.data || []);
      setLastUpdate(new Date());

      try {
        const statusRes = await getFreezeStatus();
        if (statusRes.ok) setFreezeStatus(statusRes.data);
      } catch {}
      try {
        const resultRes = await getFreezeLast();
        if (resultRes.ok) setFreezeResult(resultRes.data);
      } catch {}
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, []);

  const handleRunFreeze = async (profile) => {
    setFreezeLoading(true);
    try {
      await runFreezeValidation(profile);
      const pollInterval = setInterval(async () => {
        try {
          const statusRes = await getFreezeStatus();
          if (statusRes.ok) {
            setFreezeStatus(statusRes.data);
            if (statusRes.data.status !== 'RUNNING') {
              clearInterval(pollInterval);
              const resultRes = await getFreezeLast();
              if (resultRes.ok) setFreezeResult(resultRes.data);
            }
          }
        } catch {}
      }, 2000);
      setTimeout(() => clearInterval(pollInterval), 3600000);
    } catch (err) {
      setError(err.message);
    } finally {
      setFreezeLoading(false);
    }
  };

  const handleAbortFreeze = async () => {
    try {
      await abortFreezeValidation();
      const statusRes = await getFreezeStatus();
      if (statusRes.ok) setFreezeStatus(statusRes.data);
    } catch (err) {
      setError(err.message);
    }
  };

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 30000);
    return () => clearInterval(interval);
  }, [fetchData]);


  const systemHealth = monitor ? (
    monitor.errorSlots > 0 ? 'ERROR' :
    monitor.degradedSlots > 0 ? 'DEGRADED' :
    monitor.healthySlots > 0 ? 'HEALTHY' : 'UNKNOWN'
  ) : 'UNKNOWN';

  const hCfg = HEALTH_CFG[systemHealth];

  return (
    <AdminLayout>
      <div className="px-4 py-5 lg:px-6 space-y-6" data-testid="admin-monitor-page">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-xl font-semibold text-slate-900" data-testid="monitor-page-title">Мониторинг</h1>
            <p className="text-sm text-slate-400 mt-0.5">
              Здоровье и ёмкость системы
              {lastUpdate && <span className="ml-2">· Обновлено {lastUpdate.toLocaleTimeString()}</span>}
            </p>
          </div>
          <div className="flex items-center gap-3">
            <span className={`text-sm font-medium ${hCfg.cls}`} data-testid="system-health-label">Система: {hCfg.label}</span>
            <button onClick={fetchData} disabled={loading} className="flex items-center gap-1.5 px-3 py-1.5 text-sm text-slate-500 hover:text-slate-800 hover:bg-slate-100 rounded transition-colors" data-testid="btn-refresh">
              <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
              Обновить
            </button>
          </div>
        </div>

        {/* Tab Navigation */}
        <div className="flex gap-1 bg-slate-100/80 p-1 rounded-lg w-fit" data-testid="parser-tabs">
          <Link to="/admin/twitter-parser/accounts" className="px-3 py-1.5 text-sm text-slate-500 hover:text-slate-800 rounded transition-colors">Аккаунты</Link>
          <Link to="/admin/twitter-parser/sessions" className="px-3 py-1.5 text-sm text-slate-500 hover:text-slate-800 rounded transition-colors">Сессии</Link>
          <Link to="/admin/twitter-parser/slots" className="px-3 py-1.5 text-sm text-slate-500 hover:text-slate-800 rounded transition-colors">Слоты</Link>
          <Link to="/admin/twitter-parser/monitor" className="px-3 py-1.5 text-sm font-medium text-slate-900 bg-white rounded shadow-sm">Мониторинг</Link>
        </div>

        {/* Error */}
        {error && (
          <div className="flex items-center gap-3 p-4 rounded-lg bg-red-50 text-red-700 text-sm" data-testid="error-banner">
            <AlertTriangle className="w-5 h-5 flex-shrink-0" />
            {error}
          </div>
        )}

        {/* Overview Stats */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div className="p-4 rounded-lg bg-emerald-50" data-testid="stat-accounts">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-xs text-slate-400">Активных аккаунтов</p>
                <p className="text-2xl font-bold text-slate-900 mt-1">{monitor?.activeAccounts || 0}</p>
                <p className="text-xs text-slate-400">из {monitor?.totalAccounts || 0}</p>
              </div>
              <Users className="w-5 h-5 text-emerald-500" />
            </div>
          </div>
          <div className="p-4 rounded-lg bg-blue-50" data-testid="stat-slots">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-xs text-slate-400">Включённых слотов</p>
                <p className="text-2xl font-bold text-slate-900 mt-1">{monitor?.enabledSlots || 0}</p>
                <p className="text-xs text-slate-400">из {monitor?.totalSlots || 0}</p>
              </div>
              <Server className="w-5 h-5 text-blue-500" />
            </div>
          </div>
          <div className="p-4 rounded-lg bg-purple-50" data-testid="stat-capacity">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-xs text-slate-400">Ёмкость/ч</p>
                <p className="text-2xl font-bold text-slate-900 mt-1">{monitor?.totalCapacityPerHour || 0}</p>
                <p className="text-xs text-slate-400">запросов</p>
              </div>
              <Gauge className="w-5 h-5 text-purple-500" />
            </div>
          </div>
          <div className="p-4 rounded-lg bg-slate-100" data-testid="stat-available">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-xs text-slate-400">Доступно сейчас</p>
                <p className="text-2xl font-bold text-slate-900 mt-1">{monitor?.availableThisHour || 0}</p>
                <p className="text-xs text-slate-400">{monitor?.usedThisHour || 0} использовано</p>
              </div>
              <Zap className="w-5 h-5 text-slate-500" />
            </div>
          </div>
        </div>

        {/* Capacity & Health */}
        <div className="p-5 rounded-2xl bg-slate-50/60">
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="lg:col-span-2 space-y-4">
            <div className="flex items-center gap-2">
              <Activity className="w-4 h-4 text-slate-500" />
              <span className="text-sm font-semibold text-slate-800">Обзор ёмкости</span>
            </div>
            <div>
              <div className="flex justify-between text-sm mb-2">
                <span className="text-slate-400">Часовая ёмкость</span>
                <span className="font-medium text-slate-700">{monitor?.usedThisHour || 0} / {monitor?.totalCapacityPerHour || 0}</span>
              </div>
              <div className="h-3 bg-slate-200/60 rounded-full overflow-hidden">
                <div
                  className="h-full bg-emerald-500 rounded-full transition-all"
                  style={{ width: `${monitor?.totalCapacityPerHour ? ((monitor.usedThisHour || 0) / monitor.totalCapacityPerHour) * 100 : 0}%` }}
                />
              </div>
            </div>
            <div className="grid grid-cols-3 gap-4 pt-2">
              <div className="text-center">
                <p className="text-xl font-bold text-emerald-700">{monitor?.healthySlots || 0}</p>
                <p className="text-xs text-slate-400">Здоровых</p>
              </div>
              <div className="text-center">
                <p className="text-xl font-bold text-amber-700">{monitor?.degradedSlots || 0}</p>
                <p className="text-xs text-slate-400">Деградация</p>
              </div>
              <div className="text-center">
                <p className="text-xl font-bold text-red-500">{monitor?.errorSlots || 0}</p>
                <p className="text-xs text-slate-400">Ошибки</p>
              </div>
            </div>
          </div>

          <div className="space-y-3">
            <span className="text-sm font-semibold text-slate-800">Быстрые действия</span>
            <Link to="/admin/twitter-parser/accounts" className="flex items-center gap-2 px-3 py-2 text-sm text-slate-600 hover:text-slate-800 hover:bg-slate-100 rounded transition-colors" data-testid="link-manage-accounts">
              <Users className="w-4 h-4" />
              Управление аккаунтами
            </Link>
            <Link to="/admin/twitter-parser/slots" className="flex items-center gap-2 px-3 py-2 text-sm text-slate-600 hover:text-slate-800 hover:bg-slate-100 rounded transition-colors" data-testid="link-manage-slots">
              <Server className="w-4 h-4" />
              Управление слотами
            </Link>
          </div>
        </div>
        </div>

        {/* FREEZE Validation */}
        <div className="p-5 rounded-2xl bg-slate-50/60 space-y-4" data-testid="freeze-validation-card">
          <div className="flex items-center gap-2">
            <FlaskConical className="w-4 h-4 text-slate-500" />
            <span className="text-sm font-semibold text-slate-800">FREEZE-валидация</span>
            {freezeStatus?.status === 'RUNNING' && <span className="text-xs font-medium text-blue-700">Выполняется</span>}
            {freezeResult?.verdict === 'APPROVED' && <span className="text-xs font-medium text-emerald-700">v4.0 APPROVED</span>}
            {freezeResult?.verdict === 'BLOCKED' && <span className="text-xs font-medium text-red-500">BLOCKED</span>}
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Controls */}
            <div className="space-y-4">
              <p className="text-xs text-slate-400">Запустите валидацию для проверки стабильности перед заморозкой архитектуры v4.0.</p>
              <div className="flex flex-wrap gap-2">
                <button
                  onClick={() => handleRunFreeze('SMOKE')}
                  disabled={freezeLoading || freezeStatus?.status === 'RUNNING'}
                  className="flex items-center gap-1.5 px-3 py-1.5 text-sm font-semibold text-slate-800 bg-slate-100 hover:bg-slate-200 rounded transition-colors disabled:opacity-40"
                  data-testid="run-smoke-btn"
                >
                  <Play className="w-3.5 h-3.5" />
                  SMOKE (10 мин)
                </button>
                <button
                  onClick={() => handleRunFreeze('STRESS')}
                  disabled={freezeLoading || freezeStatus?.status === 'RUNNING'}
                  className="flex items-center gap-1.5 px-3 py-1.5 text-sm text-slate-500 hover:text-slate-800 hover:bg-slate-100 rounded transition-colors disabled:opacity-40"
                  data-testid="run-stress-btn"
                >
                  <Play className="w-3.5 h-3.5" />
                  STRESS (30 мин)
                </button>
                {freezeStatus?.status === 'RUNNING' && (
                  <button onClick={handleAbortFreeze} className="flex items-center gap-1.5 px-3 py-1.5 text-sm text-red-500 hover:text-red-700 hover:bg-red-50 rounded transition-colors" data-testid="abort-freeze-btn">
                    <Square className="w-3.5 h-3.5" />
                    Прервать
                  </button>
                )}
              </div>

              {/* Progress */}
              {freezeStatus?.status === 'RUNNING' && freezeStatus?.progress && (
                <div className="p-4 rounded-lg bg-blue-50">
                  <div className="flex justify-between text-xs mb-2">
                    <span className="text-blue-700">Прогресс: {freezeStatus.profile}</span>
                    <span className="font-medium text-blue-900">
                      {freezeStatus.progress.tasksGenerated} / {freezeStatus.progress.tasksTotal}
                    </span>
                  </div>
                  <div className="h-1.5 bg-blue-100 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-blue-500 rounded-full transition-all"
                      style={{ width: `${(freezeStatus.progress.tasksGenerated / freezeStatus.progress.tasksTotal) * 100}%` }}
                    />
                  </div>
                  <p className="text-xs text-blue-700 mt-2">
                    Время: {Math.round(freezeStatus.progress.elapsedMs / 1000)}с / {freezeStatus.progress.durationMs / 1000}с
                  </p>
                </div>
              )}
            </div>

            {/* Results */}
            <div>
              {freezeResult && (
                <div className={`p-4 rounded-lg ${freezeResult.verdict === 'APPROVED' ? 'bg-emerald-50' : 'bg-red-50'}`}>
                  <div className="flex items-center gap-2 mb-3">
                    {freezeResult.verdict === 'APPROVED' ? (
                      <CheckCircle className="w-5 h-5 text-emerald-700" />
                    ) : (
                      <XCircle className="w-5 h-5 text-red-500" />
                    )}
                    <span className={`text-sm font-bold ${freezeResult.verdict === 'APPROVED' ? 'text-emerald-700' : 'text-red-700'}`}>
                      {freezeResult.verdict}
                    </span>
                    <span className="text-xs text-slate-500">({freezeResult.profile})</span>
                  </div>

                  <div className="grid grid-cols-2 gap-3 text-sm mb-3">
                    <div>
                      <p className="text-xs text-slate-400">Успешность</p>
                      <p className="font-medium text-slate-700">{(freezeResult.rates?.successRate * 100 || 0).toFixed(1)}%</p>
                    </div>
                    <div>
                      <p className="text-xs text-slate-400">Ошибки</p>
                      <p className="font-medium text-slate-700">{(freezeResult.rates?.errorRate * 100 || 0).toFixed(1)}%</p>
                    </div>
                    <div>
                      <p className="text-xs text-slate-400">Retry</p>
                      <p className="font-medium text-slate-700">{(freezeResult.rates?.retryRate * 100 || 0).toFixed(1)}%</p>
                    </div>
                    <div>
                      <p className="text-xs text-slate-400">Runtime P95</p>
                      <p className="font-medium text-slate-700">{freezeResult.stats?.latency?.runtimeP95 || 0}ms</p>
                    </div>
                  </div>

                  {freezeResult.reasons?.length > 0 && (
                    <div className="mt-3 pt-3 border-t border-red-200/40">
                      <p className="text-xs font-medium text-red-700 mb-1">Блокеры:</p>
                      <ul className="text-xs text-red-600 space-y-0.5">
                        {freezeResult.reasons.map((reason, i) => <li key={i}>· {reason}</li>)}
                      </ul>
                    </div>
                  )}

                  <p className="text-xs text-slate-400 mt-3">
                    Завершено: {new Date(freezeResult.completedAt).toLocaleString()}
                  </p>
                </div>
              )}

              {!freezeResult && !freezeStatus?.status && (
                <div className="p-4 rounded-lg bg-slate-50 text-center">
                  <FlaskConical className="w-8 h-8 mx-auto mb-2 text-slate-300" />
                  <p className="text-xs text-slate-400">Нет результатов валидации</p>
                  <p className="text-xs text-slate-400">Запустите SMOKE для проверки</p>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Slots Grid */}
        <div className="p-5 rounded-2xl bg-slate-50/60 space-y-4">
          <span className="text-sm font-semibold text-slate-800">Egress-слоты ({slots.length})</span>
          {slots.length === 0 ? (
            <div className="text-center py-12 text-slate-400">
              <Server className="w-10 h-10 mx-auto mb-3 opacity-40" />
              <p className="text-sm">Слоты не настроены</p>
              <Link to="/admin/twitter-parser/slots" className="text-sm text-slate-600 hover:text-slate-900 underline mt-2 inline-block">
                Добавить слот
              </Link>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {slots.map(slot => <SlotCard key={slot._id} slot={slot} />)}
            </div>
          )}
        </div>
      </div>
    </AdminLayout>
  );
}
